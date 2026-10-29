"""Test workflow api. Existing cases moved without execution."""
import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from persistence import db_manager, Department, Workflow
from backend.main import app
from workflows.parser import WorkflowParser, WorkflowDefinition
from workflows.sandbox import SandboxManager
from workflows.engine import WorkflowEngine, BudgetExceededError


from poc.tests.workflow_test_support import client

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

