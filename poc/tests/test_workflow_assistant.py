"""Shared authoring contracts: real SQLite, real FastAPI authentication, no model calls."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.dependencies import get_db_manager
from backend.security.auth import authenticate_request
from backend.security.tokens import create_access_token
from backend.workflow_assistant.models import DraftCreate
from backend.workflow_assistant.router import router
from backend.workflow_assistant.service import WorkflowAssistantService
from config import AgentConfig, ProjectConfig, Skill
from persistence import DatabaseManager


@pytest.fixture
def environment(tmp_path):
    db = DatabaseManager(str(tmp_path / "assistant.sqlite"))
    for suffix in ("a", "b"):
        db.create_organization(id=f"org-{suffix}", name=suffix, slug=suffix)
    for dept, org in (("dev", "a"), ("finance", "a"), ("foreign", "b")):
        db.create_department(id=dept, name=dept, organization_id=f"org-{org}")
    for user, org, role, department, dept_role in (
        ("admin", "a", "ORG_ADMIN", None, None),
        ("operator", "a", "OPERATOR", "dev", "OPERATOR"),
        ("peer", "a", "OPERATOR", "dev", "OPERATOR"),
        ("viewer", "a", "MEMBER", "dev", "VIEWER"),
        ("manager", "a", "MEMBER", "dev", "MANAGER"),
        ("outsider", "b", "ORG_ADMIN", "foreign", "MANAGER"),
    ):
        db.create_user(id=user, organization_id=f"org-{org}", email=f"{user}@example.test",
                       full_name=user, role=role)
        if department:
            db.add_user_to_department(department, user, role=dept_role)
    db.save_project(ProjectConfig(id="project-a", name="Project", description="Project", working_directory=str(tmp_path), organization_id="org-a"))
    db.save_skill(Skill(id="review-skill", name="Review", description="Review", content="Review data", project_id="project-a"))
    for name, org, department in (("engineer", "a", "dev"), ("finance-agent", "a", "finance"), ("foreign-agent", "b", "foreign")):
        db.save_agent(AgentConfig(id=name, name=name, description="Agent",
            system_prompt="PRIVATE_SYSTEM_PROMPT", organization_id=f"org-{org}", department_id=department,
            skills=["review-skill"], mcp_permissions=["github-main", "slack-main"]))
    for connector, provider, org, configuration in (
        ("github-main", "github", "org-a", {"token": "PRIVATE_GITHUB_TOKEN",
            "allowed_repos": ["acme/approved"], "default_repo": "acme/default-only",
            "repositories": ["acme/discovered"]}),
        ("slack-main", "slack", "org-a", {"bot_token": "PRIVATE_SLACK_TOKEN",
            "allowed_channels": ["#dev"], "default_channel": "#default-only"}),
        ("foreign-connector", "github", "org-b", {"allowed_repos": ["foreign/private"]}),
        ("legacy-global", "github", None, {"allowed_repos": ["legacy/private"]}),
    ):
        db.save_mcp_connector({"id": connector, "name": connector, "provider": provider,
            "organization_id": org, "status": "CONNECTED", "configuration": configuration})
    for tool, connector, name in (
        ("gh-read", "github-main", "git_diff"), ("gh-write", "github-main", "git_commit"),
        ("slack-post", "slack-main", "post_chat_message"),
    ):
        db.save_mcp_tool({"id": tool, "connector_id": connector, "name": name, "description": "Tool"})
    db.grant_department_mcp_access("dev", "github-main", allowed_tools=["git_diff"])
    db.grant_department_mcp_access("dev", "slack-main", allowed_tools=["post_chat_message"])
    db.grant_department_mcp_access("dev", "foreign-connector", allowed_tools="*")
    db.grant_department_mcp_access("dev", "legacy-global", allowed_tools="*")
    app = FastAPI()
    app.include_router(router, prefix="/assistant", dependencies=[Depends(authenticate_request)])
    app.dependency_overrides[get_db_manager] = lambda: db
    with TestClient(app) as client:
        yield db, client


def headers(user="operator", org="org-a", **claims):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user, "org_id": org, "role": "ORG_ADMIN",
         "departments": [{"id": "dev"}, {"id": "finance"}], "azp": "test-client", **claims})}


def proposal():
    return {"name": "PR review", "trigger": {"kind": "repository", "connector_id": "github-main",
        "repository": "acme/approved", "event": "pull_request.opened"}, "steps": [
        {"key": "review", "name": "Review", "agent_id": "engineer", "prompt_template": "Review supplied PR",
         "tools": [{"connector_id": "github-main", "tool_name": "git_diff"}],
         "repositories": [{"connector_id": "github-main", "repository": "acme/approved"}],
         "skills": ["review-skill"]},
        {"key": "notify", "name": "Notify", "agent_id": "engineer", "prompt_template": "Summarize review",
         "depends_on": ["review"], "tools": [{"connector_id": "slack-main", "tool_name": "post_chat_message"}],
         "channels": [{"connector_id": "slack-main", "channel_id": "#dev"}]},
    ]}


def create(client, body=None, **extra):
    return client.post("/assistant/drafts", headers=headers(),
        json={"department_id": "dev", "proposal": body or proposal(), **extra})


def validate(client, body):
    return client.post("/assistant/validate", headers=headers(),
        json={"department_id": "dev", "proposal": body})


def test_context_catalog_are_sanitized_and_department_scoped(environment):
    db, client = environment
    context = client.get("/assistant/context", headers=headers()).json()
    assert [item["id"] for item in context["departments"]] == ["dev"]
    response = client.get("/assistant/catalog?department_id=dev", headers=headers())
    assert response.status_code == 200
    catalog = response.json()
    assert [item["id"] for item in catalog["agents"]] == ["engineer"]
    assert {item["id"] for item in catalog["connectors"]} == {"github-main", "slack-main"}
    github = next(item for item in catalog["connectors"] if item["id"] == "github-main")
    assert github["repositories"] == ["acme/approved"]
    assert [item["name"] for item in github["tools"]] == ["git_diff"]
    assert "PRIVATE_" not in response.text
    assert "default-only" not in response.text
    assert "discovered" not in response.text
    assert "foreign/private" not in response.text
    assert client.get("/assistant/proposal-schema", headers=headers()).json()["proposal_schema_version"] == 1


def test_catalog_requires_real_active_user_not_api_identity(environment):
    db, client = environment
    assert client.get("/assistant/context").status_code == 401
    token = create_access_token({"org_id": "org-a", "role": "ORG_ADMIN"})
    assert client.get("/assistant/context", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/assistant/context", headers=headers(org="org-b")).status_code == 403
    db.update_user("operator", status="SUSPENDED")
    assert client.get("/assistant/context", headers=headers()).status_code == 403


def test_membership_revocation_ignores_stale_jwt_roles_and_department_claims(environment):
    db, client = environment
    assert client.get("/assistant/catalog?department_id=finance", headers=headers()).status_code == 403
    db.remove_user_from_department("dev", "operator")
    assert client.get("/assistant/catalog?department_id=dev", headers=headers()).status_code == 403
    assert create(client).status_code == 403


def test_read_only_user_cannot_write_despite_admin_claim_in_token(environment):
    db, client = environment
    response = client.get("/assistant/catalog?department_id=dev", headers=headers("viewer"))
    assert response.status_code == 200
    assert response.json()["can_write_drafts"] is False
    response = client.post("/assistant/drafts", headers=headers("viewer"),
        json={"department_id": "dev", "proposal": proposal()})
    assert response.status_code == 403


def test_valid_proposal_saves_non_executable_draft_and_history(environment):
    db, client = environment
    response = validate(client, proposal())
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["status"] == "READY_FOR_REVIEW"
    created = create(client, intent_text="Review each new PR")
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["revision"] == 1
    assert data["executable"] is False
    assert data["organization_id"] == "org-a"
    assert data["created_by"] == "operator"
    assert db.list_workflows() == []
    history = client.get(f"/assistant/drafts/{data['id']}/revisions", headers=headers()).json()
    assert history[0]["actor_id"] == "operator"
    assert history[0]["source"] == "platform_api"
    assert history[0]["client_id"] == "test-client"
    assert history[0]["snapshot"]["status"] == "READY_FOR_REVIEW"


@pytest.mark.parametrize("target", ["channel", "repo", "tool", "agent", "skill"])
def test_unapproved_resources_are_blocked_without_saving(environment, target):
    db, client = environment
    body = proposal()
    if target == "channel":
        body["steps"][1]["channels"][0]["channel_id"] = "#default-only"
    elif target == "repo":
        body["steps"][0]["repositories"][0]["repository"] = "acme/discovered"
    elif target == "tool":
        body["steps"][0]["tools"][0]["tool_name"] = "git_commit"
    elif target == "agent":
        body["steps"][0]["agent_id"] = "foreign-agent"
    else:
        body["steps"][0]["skills"] = ["unregistered-skill"]
    result = validate(client, body).json()
    assert result["valid"] is False
    assert result["status"] == "BLOCKED"
    response = create(client, body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROPOSAL_INVALID"
    assert client.get("/assistant/drafts?department_id=dev", headers=headers()).json() == []
    assert db.list_workflows() == []


def test_blocked_proposal_requires_explicit_opt_in_and_can_be_repaired(environment):
    db, client = environment
    body = proposal()
    body["steps"][1]["channels"][0]["channel_id"] = "#unapproved"
    data = create(client, body, save_blocked=True, intent_text="Original request").json()
    assert data["status"] == "BLOCKED"
    repaired = client.put(f"/assistant/drafts/{data['id']}", headers=headers(),
        json={"expected_revision": 1, "proposal": proposal()})
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["status"] == "READY_FOR_REVIEW"
    assert repaired.json()["revision"] == 2
    assert repaired.json()["intent_text"] == "Original request"
    history = client.get(f"/assistant/drafts/{data['id']}/revisions", headers=headers()).json()
    assert [item["snapshot"]["status"] for item in history] == ["READY_FOR_REVIEW", "BLOCKED"]


def test_policy_is_rechecked_after_validation_and_while_reading_old_drafts(environment):
    db, client = environment
    data = create(client).json()
    initial_hash = data["validation"]["catalog_version"]
    db.revoke_department_mcp_access("dev", "github-main")
    assert create(client).status_code == 422
    response = client.get(f"/assistant/drafts/{data['id']}", headers=headers())
    assert response.status_code == 200
    current = response.json()
    assert current["status"] == "BLOCKED"
    assert current["saved_status"] == "READY_FOR_REVIEW"
    assert current["catalog_changed"] is True
    assert current["validation"]["catalog_version"] != initial_hash
    saved = client.get(f"/assistant/drafts/{data['id']}/revisions", headers=headers()).json()
    assert saved[0]["snapshot"]["status"] == "READY_FOR_REVIEW"


def test_draft_visibility_is_owner_or_department_reviewer(environment):
    db, client = environment
    data = create(client).json()
    path = f"/assistant/drafts/{data['id']}"
    for suffix in ("", "/revisions"):
        assert client.get(path + suffix, headers=headers("peer")).status_code == 404
        assert client.get(path + suffix, headers=headers("outsider", org="org-b")).status_code == 404
        assert client.get(path + suffix, headers=headers("manager")).status_code == 200
    assert client.get("/assistant/drafts?department_id=dev", headers=headers("peer")).json() == []
    assert len(client.get("/assistant/drafts?department_id=dev", headers=headers("manager")).json()) == 1


def test_model_cannot_supply_actor_tenant_source_or_raw_execution_parameters(environment):
    db, client = environment
    for key, value in (("organization_id", "org-b"), ("created_by", "admin"), ("source", "mcp")):
        assert create(client, **{key: value}).status_code == 422
    body = proposal()
    body["steps"][0]["params"] = {"tools": ["arbitrary"]}
    assert create(client, body).status_code == 422


def test_dependency_cycles_missing_inputs_and_unsupported_approvals(environment):
    db, client = environment
    body = proposal()
    body["steps"][0]["depends_on"] = ["notify"]
    assert "DEPENDENCY_CYCLE" in {error["code"] for error in validate(client, body).json()["errors"]}
    body = proposal()
    body["steps"][0]["repositories"] = []
    result = validate(client, body).json()
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert "MISSING_INPUT" in {error["code"] for error in result["errors"]}
    body = proposal()
    body["steps"][0]["requires_approval"] = True
    assert "APPROVAL_GATE_NOT_SUPPORTED" in {error["code"] for error in validate(client, body).json()["errors"]}


def test_draft_update_conflicts_and_noop_do_not_rewrite_history(environment):
    db, client = environment
    data = create(client).json()
    path = f"/assistant/drafts/{data['id']}"
    assert client.put(path, headers=headers(), json={"expected_revision": 1, "proposal": proposal()}).json()["revision"] == 1
    edited = proposal()
    edited["name"] = "Updated proposal"
    assert client.put(path, headers=headers(), json={"expected_revision": 1, "proposal": edited}).json()["revision"] == 2
    assert client.put(path, headers=headers(), json={"expected_revision": 1, "proposal": proposal()}).status_code == 409
    assert len(client.get(path + "/revisions", headers=headers()).json()) == 2


def test_idempotency_prevents_duplicate_drafts_and_rejects_different_content(environment):
    db, client = environment
    request_headers = {**headers(), "Idempotency-Key": "request-123"}
    body = {"department_id": "dev", "proposal": proposal()}
    first = client.post("/assistant/drafts", headers=request_headers, json=body)
    second = client.post("/assistant/drafts", headers=request_headers, json=body)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["replayed"] is True
    body["proposal"]["name"] = "Different request"
    assert client.post("/assistant/drafts", headers=request_headers, json=body).status_code == 409


def test_concurrent_retries_create_exactly_one_draft_and_one_revision(environment):
    db, client = environment
    barrier = Barrier(2)
    request = DraftCreate(department_id="dev", proposal=proposal())
    def save(_):
        service = WorkflowAssistantService(db, {"sub": "operator", "org_id": "org-a"})
        barrier.wait()
        return service.create_draft(request, idempotency_key="same-request")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, range(2)))
    assert results[0]["id"] == results[1]["id"]
    assert sorted(item["replayed"] for item in results) == [False, True]
    assert len(client.get(f"/assistant/drafts/{results[0]['id']}/revisions", headers=headers()).json()) == 1


def test_schema_and_catalog_do_not_create_orgs_or_connectors(environment):
    db, client = environment
    with db._get_connection() as conn:
        before = conn.execute("SELECT count(*) FROM mcp_connectors").fetchone()[0]
    client.get("/assistant/catalog?department_id=dev", headers=headers())
    client.get("/assistant/proposal-schema", headers=headers())
    with db._get_connection() as conn:
        assert conn.execute("SELECT count(*) FROM mcp_connectors").fetchone()[0] == before


def test_unscoped_or_foreign_project_skills_are_not_advertised(environment, tmp_path):
    db, client = environment
    db.save_project(ProjectConfig(id="foreign-project", name="Foreign", description="Private", working_directory=str(tmp_path), organization_id="org-b"))
    db.save_skill(Skill(id="foreign-skill", name="Private skill", description="Private", content="PRIVATE_CONTENT", project_id="foreign-project"))
    db.save_skill(Skill(id="legacy-global", name="Legacy", description="Unscoped", content="PRIVATE_CONTENT"))
    agent = db.get_agent("engineer")
    agent.skills = ["review-skill", "foreign-skill", "legacy-global", "missing-skill"]
    db.save_agent(agent)
    response = client.get("/assistant/catalog?department_id=dev", headers=headers())
    assert response.json()["skills"] == [{"id": "review-skill"}]
    assert "PRIVATE_CONTENT" not in response.text
    assert "Private skill" not in response.text


def test_explicit_agent_tool_id_grants_are_respected(environment):
    db, client = environment
    agent = db.get_agent("engineer")
    agent.mcp_permissions = []
    db.save_agent(agent)
    db.add_mcp_permission("engineer", "github-main", tool_id="gh-read")
    data = proposal()
    data["steps"] = data["steps"][:1]
    assert validate(client, data).json()["valid"] is True
    data["steps"][0]["tools"][0]["tool_name"] = "git_commit"
    assert validate(client, data).json()["valid"] is False


def test_list_uses_current_policy_and_history_pagination(environment):
    db, client = environment
    created = create(client).json()
    for revision in (1, 2):
        data = proposal()
        data["name"] = f"Revision {revision + 1}"
        assert client.put(f"/assistant/drafts/{created['id']}", headers=headers(),
            json={"expected_revision": revision, "proposal": data}).status_code == 200
    response = client.get(f"/assistant/drafts/{created['id']}/revisions?limit=1&before_revision=3", headers=headers())
    assert [entry["revision"] for entry in response.json()] == [2]
    db.revoke_department_mcp_access("dev", "github-main")
    response = client.get("/assistant/drafts?department_id=dev", headers=headers()).json()
    assert response[0]["status"] == "BLOCKED"
    assert response[0]["saved_status"] == "READY_FOR_REVIEW"


def test_trigger_validation_and_exact_error_paths(environment):
    db, client = environment
    data = proposal()
    data["trigger"] = {"kind": "cron"}
    result = validate(client, data).json()
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert result["errors"][0]["path"] == "trigger.cron_expression"
    data["trigger"] = {"kind": "manual", "repository": "acme/approved"}
    assert "UNEXPECTED_TRIGGER_FIELD" in {error["code"] for error in validate(client, data).json()["errors"]}
    data = proposal()
    data["steps"][1]["channels"][0]["channel_id"] = "#unapproved"
    assert "steps[1].channels[0].channel_id" in {error["path"] for error in validate(client, data).json()["errors"]}


def test_delegated_client_scopes_can_only_reduce_database_permissions(environment):
    db, client = environment
    response = client.get("/assistant/catalog?department_id=dev", headers=headers(scope="workflow-assistant:read"))
    assert response.status_code == 200
    assert response.json()["can_write_drafts"] is False
    response = client.post("/assistant/drafts", headers=headers(scope="workflow-assistant:read"),
        json={"department_id": "dev", "proposal": proposal()})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CLIENT_SCOPE_DENIED"
    assert client.get("/assistant/context", headers=headers(scope="unrelated:scope")).status_code == 403
    with pytest.raises(ValueError, match="verified delegated"):
        WorkflowAssistantService(db, {"sub": "operator", "org_id": "org-a"}, source="mcp")
    mcp_service = WorkflowAssistantService(db, {"sub": "operator", "org_id": "org-a", "azp": "client"},
        source="mcp", granted_scopes={"workflow-assistant:read", "workflow-assistant:write"})
    result = mcp_service.create_draft(DraftCreate(department_id="dev", proposal=proposal()))
    assert mcp_service.history(result["id"])[0]["source"] == "mcp"
    viewer = WorkflowAssistantService(db, {"sub": "viewer", "org_id": "org-a"}, source="mcp",
        granted_scopes={"workflow-assistant:read", "workflow-assistant:write"})
    with pytest.raises(ValueError, match="current role"):
        viewer.create_draft(DraftCreate(department_id="dev", proposal=proposal()))


def test_concurrent_updates_keep_one_winner_and_append_one_revision(environment):
    from backend.workflow_assistant.models import DraftUpdate
    from backend.workflow_assistant.service import AssistantError
    db, client = environment
    draft = create(client).json()
    barrier = Barrier(2)
    def update(name):
        service = WorkflowAssistantService(db, {"sub": "operator", "org_id": "org-a"})
        data = proposal()
        data["name"] = name
        barrier.wait()
        try:
            service.update_draft(draft["id"], DraftUpdate(expected_revision=1, proposal=data))
            return "saved"
        except AssistantError as error:
            assert error.detail["code"] == "REVISION_CONFLICT"
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, ["First", "Second"])) == ["conflict", "saved"]
    history = client.get(f"/assistant/drafts/{draft['id']}/revisions", headers=headers()).json()
    assert [item["revision"] for item in history] == [2, 1]


def test_explicit_resource_revocation_blocks_even_an_idempotent_replay(environment):
    db, client = environment
    request_headers = {**headers(), "Idempotency-Key": "recheck-policy"}
    body = {"department_id": "dev", "proposal": proposal()}
    assert client.post("/assistant/drafts", headers=request_headers, json=body).status_code == 201
    db.revoke_department_mcp_access("dev", "github-main")
    assert client.post("/assistant/drafts", headers=request_headers, json=body).status_code == 422


def test_approval_lists_ignore_wildcards_credential_urls_and_non_id_objects(environment):
    db, client = environment
    connector = db.get_mcp_connector("github-main")
    connector.configuration["allowed_repos"] = ["*", "acme/approved", "https://PRIVATE_VALUE@github.com/acme/private", {"token": "PRIVATE_VALUE"}]
    db.save_mcp_connector(connector)
    connector = db.get_mcp_connector("slack-main")
    connector.configuration["allowed_channels"] = ["*", {"channel_id": "#dev"}, {"token": "PRIVATE_VALUE"}]
    db.save_mcp_connector(connector)
    response = client.get("/assistant/catalog?department_id=dev", headers=headers())
    data = {item["id"]: item for item in response.json()["connectors"]}
    assert data["github-main"]["repositories"] == ["acme/approved"]
    assert data["slack-main"]["channels"] == ["#dev"]
    assert "PRIVATE_VALUE" not in response.text
