"""
Comprehensive Test Suite for Enterprise Organization & Department MCP Governance:
Verifies:
1. Multi-tenant Organization CRUD (real SQLite).
2. Department creation with organization linkage and budget controls.
3. Department MCP Access Grants with Tool-Level Filtering (* vs specific tool allowlists).
4. check_department_mcp_permission logic (wildcard, allowlisted tool, blocked tool, unassigned department).
5. WorkflowEngine pre-flight hard-block enforcement (MCPGovernanceViolationError when unapproved MCP is used).
6. WorkflowEngine step-level tool hard-block enforcement (MCPGovernanceViolationError when blocked tool is invoked).
7. Successful workflow execution when department has valid MCP grants and tool permissions.
8. Revocation of department MCP access.
9. FastAPI REST API endpoints for Organizations, Departments, and MCP access management.
10. Execution endpoint 403 Forbidden response on MCP governance violations.
"""

import pytest
import uuid
import json
from datetime import datetime
from fastapi.testclient import TestClient

from persistence import (
    db_manager,
    Organization,
    Department,
    DepartmentMCPAccess,
    Workflow,
    MCPConnector
)
from backend.main import app
from workflows.parser import WorkflowParser
from workflows.engine import WorkflowEngine, MCPGovernanceViolationError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_organization_crud():
    """Verify organization tenant creation, lookup by id and slug, and listing."""
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    slug = f"acme-{uuid.uuid4().hex[:6]}"

    # Create
    org = db_manager.create_organization(
        id=org_id,
        name="Acme Corporation",
        slug=slug,
        domain="acme.internal",
        settings_json=json.dumps({"sso_enabled": True})
    )
    assert org.id == org_id
    assert org.name == "Acme Corporation"
    assert org.slug == slug
    assert org.domain == "acme.internal"
    assert "sso_enabled" in org.settings_json

    # Get by ID
    fetched = db_manager.get_organization(org_id)
    assert fetched is not None
    assert fetched.name == "Acme Corporation"

    # Get by Slug
    by_slug = db_manager.get_organization_by_slug(slug)
    assert by_slug is not None
    assert by_slug.id == org_id

    # List
    all_orgs = db_manager.list_organizations()
    assert any(o.id == org_id for o in all_orgs)

    # Update
    updated = db_manager.update_organization(org_id, name="Acme Corp Global", domain="acme.com")
    assert updated.name == "Acme Corp Global"
    assert updated.domain == "acme.com"


def test_department_organization_linkage():
    """Verify department creation with organization_id foreign linkage."""
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    db_manager.create_organization(id=org_id, name="FinTech Org", slug=f"fintech-{uuid.uuid4().hex[:6]}")

    dept_id = f"dept_eng_{uuid.uuid4().hex[:6]}"
    dept = db_manager.create_department(
        id=dept_id,
        name="Core Engineering",
        monthly_budget_usd=500.0,
        organization_id=org_id
    )
    assert dept.id == dept_id
    assert dept.organization_id == org_id
    assert dept.monthly_budget_usd == 500.0

    fetched = db_manager.get_department(dept_id)
    assert fetched.organization_id == org_id


def test_department_mcp_access_tool_filtering():
    """
    Verify grant creation with specific tool-level filtering.
    E.g. SecOps can only use ['git_diff', 'list_issues', 'search_code'], but not 'git_commit'.
    """
    dept_id = f"dept_qa_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="QA & Security", monthly_budget_usd=200.0)

    # Grant github access with restricted read-only tools
    allowed_tools = ["git_diff", "list_issues", "search_code"]
    grant = db_manager.grant_department_mcp_access(
        department_id=dept_id,
        connector_id="github",
        allowed_tools=allowed_tools,
        granted_by_user_id="admin_01"
    )
    assert grant.department_id == dept_id
    assert grant.connector_id == "github"
    assert grant.is_active is True

    # Check permission for connector
    conn_perm = db_manager.check_department_mcp_permission(dept_id, "github")
    assert conn_perm["allowed"] is True

    # Check permission for allowed tool
    diff_perm = db_manager.check_department_mcp_permission(dept_id, "github", tool_name="git_diff")
    assert diff_perm["allowed"] is True
    assert "git_diff" in diff_perm["allowed_tools"]

    # Check permission for blocked tool (Hard Block)
    commit_perm = db_manager.check_department_mcp_permission(dept_id, "github", tool_name="git_commit")
    assert commit_perm["allowed"] is False
    assert "blocked" in commit_perm["reason"].lower() or "not in allowed" in commit_perm["reason"].lower()

    # Unassigned department (None) -> Always allowed
    unassigned_perm = db_manager.check_department_mcp_permission(None, "github", tool_name="git_commit")
    assert unassigned_perm["allowed"] is True


def test_department_mcp_access_wildcard_grant():
    """Verify grant creation with wildcard '*' (all tools allowed)."""
    dept_id = f"dept_dev_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="DevOps Team", monthly_budget_usd=1000.0)

    # Grant full wildcard access to postgres
    grant = db_manager.grant_department_mcp_access(
        department_id=dept_id,
        connector_id="postgres",
        allowed_tools="*"
    )
    assert grant.allowed_tools == "*"

    perm1 = db_manager.check_department_mcp_permission(dept_id, "postgres", tool_name="execute_query")
    assert perm1["allowed"] is True
    assert perm1["allowed_tools"] == ["*"]

    perm2 = db_manager.check_department_mcp_permission(dept_id, "postgres", tool_name="drop_table")
    assert perm2["allowed"] is True


def test_department_mcp_access_revocation():
    """Verify revocation of MCP access for a department."""
    dept_id = f"dept_mkt_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="Marketing", monthly_budget_usd=50.0)

    # Grant access
    db_manager.grant_department_mcp_access(dept_id, "slack", allowed_tools="*")
    assert db_manager.check_department_mcp_permission(dept_id, "slack")["allowed"] is True

    # Revoke access
    revoked = db_manager.revoke_department_mcp_access(dept_id, "slack")
    assert revoked is True

    # Now permission check must fail
    chk = db_manager.check_department_mcp_permission(dept_id, "slack")
    assert chk["allowed"] is False
    assert "does not have granted access" in chk["reason"]


def test_workflow_engine_hard_block_unauthorized_mcp():
    """Verify WorkflowEngine pre-flight hard block when department lacks MCP grant."""
    dept_id = f"dept_gov1_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="Restricted Dept", monthly_budget_usd=100.0)

    # Workflow requests "jira" and "github" MCPs, but department has NO grants
    wf_id = f"wf_unauth_{uuid.uuid4().hex[:6]}"
    definition = {
        "id": wf_id,
        "name": "Unauthorized MCP Flow",
        "mcp_servers": ["jira"],
        "steps": [
            {
                "key": "step1",
                "name": "Check Jira",
                "agent_id": "test-agent-qa",
                "mcp_servers": ["jira"],
                "prompt_template": "Query Jira ticket"
            }
        ]
    }
    db_manager.create_workflow(
        id=wf_id,
        name="Unauthorized MCP Flow",
        definition_json=json.dumps(definition),
        department_id=dept_id
    )

    engine = WorkflowEngine(db_manager=db_manager)
    with pytest.raises(MCPGovernanceViolationError) as exc_info:
        engine.execute_workflow(wf_id)

    assert "MCP Governance Violation" in str(exc_info.value)
    assert "jira" in str(exc_info.value)

    # Execution record in DB must be recorded as FAILED
    with db_manager._get_connection() as conn:
        row = conn.execute("SELECT * FROM workflow_executions WHERE workflow_id = ? ORDER BY created_at DESC", (wf_id,)).fetchone()
        assert row is not None
        assert row["status"] == "FAILED"
        assert "jira" in row["error_message"]


def test_workflow_engine_hard_block_step_tool_filtering():
    """Verify step-level hard block when a step uses a tool not permitted by department policy."""
    dept_id = f"dept_gov2_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="Junior Devs", monthly_budget_usd=100.0)

    # Grant github access ONLY to git_status and git_diff (commit is forbidden)
    db_manager.grant_department_mcp_access(
        department_id=dept_id,
        connector_id="github",
        allowed_tools=["git_status", "git_diff"]
    )

    # Workflow step explicitly invokes forbidden tool "git_commit"
    wf_id = f"wf_blocked_tool_{uuid.uuid4().hex[:6]}"
    definition = {
        "id": wf_id,
        "name": "Forbidden Commit Step",
        "mcp_servers": ["github"],
        "steps": [
            {
                "key": "commit_step",
                "name": "Direct Git Commit",
                "agent_id": "junior-dev",
                "mcp_servers": ["github"],
                "params": {
                    "tools": ["git_commit"]
                },
                "prompt_template": "Commit changes to main"
            }
        ]
    }
    db_manager.create_workflow(
        id=wf_id,
        name="Forbidden Commit Step",
        definition_json=json.dumps(definition),
        department_id=dept_id
    )

    engine = WorkflowEngine(db_manager=db_manager)
    with pytest.raises(MCPGovernanceViolationError) as exc_info:
        engine.execute_workflow(wf_id)

    assert "git_commit" in str(exc_info.value)
    assert "blocked by department policy" in str(exc_info.value)


def test_workflow_engine_success_with_allowed_tools():
    """Verify successful execution when department has explicit grant matching required tools."""
    dept_id = f"dept_gov3_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="Security Audit", monthly_budget_usd=200.0)

    # Grant github access with git_diff
    db_manager.grant_department_mcp_access(
        department_id=dept_id,
        connector_id="github",
        allowed_tools=["git_diff", "git_status"]
    )

    wf_id = f"wf_allowed_{uuid.uuid4().hex[:6]}"
    definition = {
        "id": wf_id,
        "name": "Security Diff Inspection",
        "mcp_servers": ["github"],
        "steps": [
            {
                "key": "diff_step",
                "name": "Audit Diff",
                "agent_id": "sec-auditor",
                "mcp_servers": ["github"],
                "params": {
                    "tools": ["git_diff"]
                },
                "prompt_template": "Audit diff between HEAD and main"
            }
        ]
    }
    db_manager.create_workflow(
        id=wf_id,
        name="Security Diff Inspection",
        definition_json=json.dumps(definition),
        department_id=dept_id
    )

    engine = WorkflowEngine(db_manager=db_manager)
    exec_res = engine.execute_workflow(wf_id)
    assert exec_res.status == "COMPLETED"
    assert exec_res.error_message is None


def test_api_organization_and_department_mcp_governance(client):
    """Verify REST API endpoints for organization, department, and MCP governance."""
    # 1. Create Organization via API
    org_slug = f"api-org-{uuid.uuid4().hex[:6]}"
    org_resp = client.post("/api/v1/organizations", json={
        "name": "Enterprise Holdings",
        "slug": org_slug,
        "domain": "holdings.com"
    })
    assert org_resp.status_code == 201
    org_data = org_resp.json()
    org_id = org_data["id"]
    assert org_data["slug"] == org_slug

    # 2. Create Department via API
    dept_resp = client.post("/api/v1/departments", json={
        "name": "Infra & Cloud",
        "monthly_budget_usd": 750.0,
        "budget_action": "HARD_STOP",
        "organization_id": org_id
    })
    assert dept_resp.status_code == 201
    dept_data = dept_resp.json()
    dept_id = dept_data["id"]
    assert dept_data["organization_id"] == org_id

    # 3. Grant MCP Access with tool filtering via API
    grant_resp = client.post(f"/api/v1/departments/{dept_id}/mcp-access", json={
        "connector_id": "aws-cloud",
        "allowed_tools": ["describe_instances", "get_metric_data"],
        "granted_by_user_id": "ciso_admin"
    })
    assert grant_resp.status_code == 201
    grant_data = grant_resp.json()
    assert grant_data["connector_id"] == "aws-cloud"
    assert grant_data["parsed_allowed_tools"] == ["describe_instances", "get_metric_data"]

    # 4. List Department Grants via API
    list_resp = client.get(f"/api/v1/departments/{dept_id}/mcp-access")
    assert list_resp.status_code == 200
    grants_list = list_resp.json()
    assert len(grants_list) >= 1
    assert any(g["connector_id"] == "aws-cloud" for g in grants_list)

    # 5. Check Permission via API
    chk_allowed = client.get(f"/api/v1/departments/{dept_id}/mcp-access/aws-cloud/check?tool_name=describe_instances")
    assert chk_allowed.status_code == 200
    assert chk_allowed.json()["allowed"] is True

    chk_blocked = client.get(f"/api/v1/departments/{dept_id}/mcp-access/aws-cloud/check?tool_name=terminate_instance")
    assert chk_blocked.status_code == 200
    assert chk_blocked.json()["allowed"] is False

    # 6. Workflow Execution via API returns 403 Forbidden on governance violation
    wf_id = f"wf_api_gov_{uuid.uuid4().hex[:6]}"
    definition = {
        "id": wf_id,
        "name": "API Governance Test",
        "mcp_servers": ["aws-cloud"],
        "steps": [
            {
                "key": "destroy_step",
                "name": "Terminate EC2",
                "agent_id": "cloud-agent",
                "mcp_servers": ["aws-cloud"],
                "params": {"tools": ["terminate_instance"]},
                "prompt_template": "Terminate idle node"
            }
        ]
    }
    db_manager.create_workflow(
        id=wf_id,
        name="API Governance Test",
        definition_json=json.dumps(definition),
        department_id=dept_id
    )

    exec_resp = client.post(f"/api/v1/workflows/{wf_id}/execute")
    assert exec_resp.status_code == 403
    assert "MCP Governance Violation" in exec_resp.json()["detail"]
    assert "terminate_instance" in exec_resp.json()["detail"]

    # 7. Revoke Grant via API
    del_resp = client.delete(f"/api/v1/departments/{dept_id}/mcp-access/aws-cloud")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "SUCCESS"
