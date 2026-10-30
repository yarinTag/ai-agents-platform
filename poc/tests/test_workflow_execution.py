"""Real SQLite contracts for unavailable inference; no provider calls required."""
import uuid
import pytest
from persistence import DatabaseManager
from workflows.parser import WorkflowParser
from workflows.engine import WorkflowEngine


@pytest.fixture
def workflow_database(tmp_path):
    database = DatabaseManager(str(tmp_path / "workflow-execution.db"))
    database.max_agents = 100
    return database


def test_unavailable_runtime_stops_dependent_steps(workflow_database):
    """A fixture without a runtime must fail, never invent completion."""
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
    workflow_database.create_workflow(
        id=wf_id,
        name="Metrics Workflow",
        definition_json=json.dumps(definition)
    )

    engine = WorkflowEngine(db_manager=workflow_database)
    exec_res = engine.execute_workflow(
        workflow_id=wf_id,
        trigger_type="MANUAL",
        trigger_payload={"goal": "Refactor token accounting"}
    )

    assert exec_res.status == "FAILED"
    assert exec_res.workflow_id == wf_id
    assert exec_res.completed_at is not None

    assert "Runtime capability is unavailable" in exec_res.error_message
    assert exec_res.total_input_tokens == 0
    assert exec_res.total_output_tokens == 0
    assert exec_res.total_cost_usd == 0

    # Only the failed first step is persisted; its dependent must not launch.
    with workflow_database._get_connection() as conn:
        rows = conn.execute("SELECT * FROM workflow_step_runs WHERE execution_id = ?", (exec_res.id,)).fetchall()
        assert len(rows) == 1
        assert rows[0]["step_key"] == "step1"
        assert rows[0]["status"] == "FAILED"
        assert "Refactor token accounting" in rows[0]["input_data"]


def test_step_inputs_and_agent_assignment_survive_runtime_unavailability(workflow_database):
    """Retain rendered step input and assigned agent when inference cannot start."""
    raw_yaml = """
name: Feature Flag Injection Workflow
steps:
  - name: Create Flag
    skills:
      - "{{provider_skill}}"
    instructions: "Create feature flag {{flag_key}}"
    params:
      agentId: ff-specialist-worker

  - name: Update Code
    skills:
      - "{{target_repo_skill}}"
    instructions: "Inject flag into codebase: {{create-flag.output}}"
    params:
      agentId: ff-specialist-worker

flow:
  - from: ""
    to: create-flag
  - from: create-flag
    to: update-code
"""
    wf = WorkflowParser.from_yaml(raw_yaml)
    assert wf.id == "feature-flag-injection-workflow"

    # Persist and execute workflow with isolated test ID
    unique_wf_id = f"wf_ff_{uuid.uuid4().hex[:8]}"
    wf.id = unique_wf_id
    wf_record = workflow_database.create_workflow(
        id=unique_wf_id,
        name=wf.name,
        definition_json=wf.to_json()
    )

    engine = WorkflowEngine(db_manager=workflow_database)
    exec_res = engine.execute_workflow(
        workflow_id=wf_record.id,
        trigger_type="MANUAL",
        trigger_payload={
            "flag_key": "enable_new_auth",
            "provider_skill": "launchdarkly-api",
            "target_repo_skill": "repo-auth-sdk"
        }
    )

    assert exec_res.status == "FAILED"
    assert exec_res.workflow_id == wf.id

    # Provision the assigned agent without pretending both steps ran.
    worker = workflow_database.get_agent("ff-specialist-worker")
    assert worker is not None
    assert worker.id == "ff-specialist-worker"

    # The dependent step remains unstarted after the first step fails.
    with workflow_database._get_connection() as conn:
        steps_run = conn.execute(
            "SELECT step_key, agent_id, status, input_data FROM workflow_step_runs WHERE execution_id = ? ORDER BY started_at ASC",
            (exec_res.id,)
        ).fetchall()
        assert len(steps_run) == 1
        assert steps_run[0]["step_key"] == "create-flag"
        assert steps_run[0]["agent_id"] == "ff-specialist-worker"
        assert steps_run[0]["status"] == "FAILED"
        assert "enable_new_auth" in steps_run[0]["input_data"]


def test_parallel_stage_planning_and_unavailable_runtime_dependency_stop(workflow_database):
    """Plan fan-out/fan-in, but never execute dependent stages after failure."""
    fan_out_yaml = """
name: Parallel Multi-Agent Audit Pipeline
steps:
  - name: Setup Workspace
    instructions: "Prepare test environment"
    params:
      agentId: devops-specialist

  - name: Frontend Audit
    instructions: "Audit UI components for accessibility"
    params:
      agentId: frontend-developer
    depends_on:
      - setup-workspace

  - name: Backend Audit
    instructions: "Audit API endpoints for performance"
    params:
      agentId: backend-developer
    depends_on:
      - setup-workspace

  - name: Executive Synthesis
    instructions: "Synthesize Frontend: {{frontend-audit.output}} and Backend: {{backend-audit.output}}"
    params:
      agentId: ceo-orchestrator
    depends_on:
      - frontend-audit
      - backend-audit
"""
    wf = WorkflowParser.from_yaml(fan_out_yaml)
    engine = WorkflowEngine(db_manager=workflow_database)

    # 1. Test stage grouping
    stages = engine._group_steps_into_stages(wf.steps)
    assert len(stages) == 3
    assert len(stages[0]) == 1 # Setup
    assert len(stages[1]) == 2 # Parallel: Frontend + Backend
    assert len(stages[2]) == 1 # Synthesis

    stage1_keys = {s.key for s in stages[1]}
    assert stage1_keys == {"frontend-audit", "backend-audit"}

    # 2. Persist & Execute with isolated test ID
    unique_fan_id = f"wf_fan_{uuid.uuid4().hex[:8]}"
    wf.id = unique_fan_id
    wf_record = workflow_database.create_workflow(
        id=unique_fan_id,
        name=wf.name,
        definition_json=wf.to_json()
    )

    exec_res = engine.execute_workflow(workflow_id=wf_record.id, trigger_type="MANUAL")
    assert exec_res.status == "FAILED"

    # No audit or synthesis may run after workspace preparation fails.
    with workflow_database._get_connection() as conn:
        runs = conn.execute(
            "SELECT step_key, agent_id FROM workflow_step_runs WHERE execution_id = ?",
            (exec_res.id,)
        ).fetchall()
        assert len(runs) == 1
        ran_agents = {r["agent_id"] for r in runs}
        assert ran_agents == {"devops-specialist"}

