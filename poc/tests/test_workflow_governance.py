"""Test workflow governance. Existing cases moved without execution."""
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

