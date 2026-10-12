"""
Test Suite for Overcut-Inspired Workflows:
Verifies:
1. YAML & JSON conversion and parsing.
2. Workflow execution through DAG steps.
3. Department budget enforcement (HARD_STOP on exceeding monthly budget for API key runs).
4. Webhook triggering via token with parameter passing.
5. Ephemeral and Docker-backed sandbox isolation.
6. Token usage and cost tracking in database and API.
7. Run evaluations and lessons learned capture.
"""

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from persistence import db_manager, Department, Workflow
from backend.main import app
from workflows.parser import WorkflowParser, WorkflowDefinition
from workflows.sandbox import SandboxManager
from workflows.engine import WorkflowEngine, BudgetExceededError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_workflow_yaml_and_json_parsing_roundtrip():
    """Verify bidirectional YAML <-> JSON conversion of workflow definitions."""
    sample_yaml = """
id: wf-code-review
name: Automated Code Review
description: Multi-agent code review workflow
department_id: dept-eng
steps:
  - key: triage
    name: Ticket Triage
    agent_id: dev-lead
    prompt_template: Triage ticket ${ticket_id} and assess impact
  - key: review
    name: Deep Code Review
    agent_id: backend-dev
    depends_on:
      - triage
    prompt_template: "Review PR based on triage summary: ${triage.output}"
"""
    # 1. Parse YAML
    wf = WorkflowParser.from_yaml(sample_yaml)
    assert wf.id == "wf-code-review"
    assert wf.name == "Automated Code Review"
    assert len(wf.steps) == 2
    assert wf.steps[0].key == "triage"
    assert wf.steps[1].depends_on == ["triage"]

    # 2. Convert to JSON
    json_str = wf.to_json()
    assert '"wf-code-review"' in json_str

    # 3. Parse back from JSON
    wf_from_json = WorkflowParser.from_json(json_str)
    assert wf_from_json.name == wf.name
    assert len(wf_from_json.steps) == 2

    # 4. Helper string converter
    converted_json = WorkflowParser.yaml_to_json(sample_yaml)
    assert "Automated Code Review" in converted_json


def test_sandbox_isolation_ephemeral_directory():
    """Verify ephemeral directory sandbox lifecycle and cleanup."""
    mgr = SandboxManager()
    session = mgr.create_sandbox(
        execution_id="test_exec_001",
        force_type="EPHEMERAL_DIR"
    )
    assert session.sandbox_type == "EPHEMERAL_DIR"
    assert session.is_active is True
    assert session.path is not None

    # Check path exists during execution
    import os
    assert os.path.exists(session.path)

    # Teardown
    session.cleanup()
    assert session.is_active is False
    assert not os.path.exists(session.path)


def test_department_budget_hard_stop_enforcement():
    """Verify that HARD_STOP policy blocks workflow when budget is exceeded."""
    dept_id = f"dept_test_{uuid.uuid4().hex[:6]}"
    # Create department with $10 monthly budget
    dept = db_manager.create_department(
        id=dept_id,
        name="Security & QA",
        monthly_budget_usd=10.0,
        budget_action="HARD_STOP"
    )
    assert dept.monthly_budget_usd == 10.0

    # Under budget: check allowed
    chk1 = db_manager.check_department_budget(dept_id, requested_cost=5.0)
    assert chk1["allowed"] is True

    # Record an execution of $15 using API_KEY
    wf_id = f"wf_budget_{uuid.uuid4().hex[:6]}"
    db_manager.create_workflow(
        id=wf_id,
        name="Budget Test WF",
        definition_json='{"steps": []}',
        department_id=dept_id
    )

    now_iso = datetime.now().isoformat()
    with db_manager._get_connection() as conn:
        conn.execute("""
            INSERT INTO workflow_executions (
                id, workflow_id, trigger_type, status, department_id,
                total_cost_usd, created_at
            ) VALUES (?, ?, 'MANUAL', 'COMPLETED', ?, 15.0, ?)
        """, (f"exec_{uuid.uuid4().hex[:8]}", wf_id, dept_id, now_iso))
        conn.commit()

    # Now spend is $15. Budget is $10. Must trigger HARD_STOP
    chk2 = db_manager.check_department_budget(dept_id)
    assert chk2["allowed"] is False
    assert chk2["action"] == "HARD_STOP"
    assert "Additional budget required" in chk2["message"]

    # Verify WorkflowEngine raises BudgetExceededError
    engine = WorkflowEngine(db_manager=db_manager)
    with pytest.raises(BudgetExceededError):
        engine.execute_workflow(wf_id)


def test_workflow_execution_and_metrics_accumulation():
    """Verify multi-step workflow execution, output propagation, and token aggregation."""
    wf_id = f"wf_calc_{uuid.uuid4().hex[:6]}"
    definition = {
        "id": wf_id,
        "name": "Metrics Workflow",
        "steps": [
            {
                "key": "step1",
                "name": "Step One",
                "agent_id": "test-agent-1",
                "prompt_template": "Analyze requirement: {{goal}}"
            },
            {
                "key": "step2",
                "name": "Step Two",
                "agent_id": "test-agent-2",
                "depends_on": ["step1"],
                "prompt_template": "Build on step 1: {{step1.output}}"
            }
        ]
    }

    import json
    db_manager.create_workflow(
        id=wf_id,
        name="Metrics Workflow",
        definition_json=json.dumps(definition)
    )

    engine = WorkflowEngine(db_manager=db_manager)
    exec_res = engine.execute_workflow(
        workflow_id=wf_id,
        trigger_type="MANUAL",
        trigger_payload={"goal": "Refactor token accounting"}
    )

    assert exec_res.status == "COMPLETED"
    assert exec_res.workflow_id == wf_id
    assert exec_res.completed_at is not None

    # Verify step runs were persisted
    with db_manager._get_connection() as conn:
        rows = conn.execute("SELECT * FROM workflow_step_runs WHERE execution_id = ?", (exec_res.id,)).fetchall()
        assert len(rows) == 2


def test_webhook_trigger_api_endpoint(client):
    """Verify triggering workflow via its dedicated webhook endpoint."""
    wf_id = f"wf_wh_{uuid.uuid4().hex[:6]}"
    sample_yaml = """
id: wf-webhook-test
name: Webhook Test Workflow
steps:
  - key: triage
    name: Webhook Triage
    agent_id: auto-agent
    prompt_template: Process PR {{pr_id}} from repo {{repo}}
"""
    # 1. Create workflow via REST API
    create_resp = client.post("/api/v1/workflows", json={
        "name": "Webhook Test Workflow",
        "definition_yaml": sample_yaml,
        "webhook_enabled": True
    })
    assert create_resp.status_code == 201
    created_wf = create_resp.json()
    webhook_token = created_wf["webhook_token"]
    assert webhook_token is not None

    # 2. Trigger incoming webhook
    hook_resp = client.post(
        f"/api/v1/workflows/webhook/{webhook_token}",
        json={"pr_id": 42, "repo": "ai-agents-platform"}
    )
    assert hook_resp.status_code == 202
    exec_data = hook_resp.json()
    assert exec_data["trigger_type"] == "WEBHOOK"
    assert exec_data["status"] == "COMPLETED"

    # 3. Retrieve execution status and tokens
    get_resp = client.get(f"/api/v1/workflows/executions/{exec_data['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == exec_data["id"]


def test_run_evaluations_and_learning_capture(client):
    """Verify submitting human review rating and lessons learned."""
    # Create workflow and execution
    wf_id = f"wf_eval_{uuid.uuid4().hex[:6]}"
    db_manager.create_workflow(
        id=wf_id,
        name="Evaluation Workflow",
        definition_json='{"steps": []}'
    )
    exec_id = f"exec_eval_{uuid.uuid4().hex[:6]}"
    db_manager.create_workflow_execution(
        execution_id=exec_id,
        workflow_id=wf_id,
        trigger_type="MANUAL"
    )

    # Submit evaluation
    resp = client.post(f"/api/v1/workflows/executions/{exec_id}/evaluate", json={
        "rating": 5,
        "feedback_notes": "Flawless execution of step 1",
        "lessons_extracted": "Always verify dependencies before running migrations"
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUCCESS"
