"""Test hierarchical orchestration. Existing cases moved without execution."""
import os
import sys
import uuid
import json
import pytest
from datetime import datetime
from pathlib import Path
from backend.dependencies import get_db_manager, get_event_service, get_orchestration_engine
from config import AgentConfig, AgentRole, ProjectConfig
from runtime_adapter import TaskStatus, AgentRun, ClaudeCodeRuntimeAdapter
from orchestration.engine import OrchestrationEngine, DelegationError, ConcurrencyLimitExceededError
from orchestration.supervisor_resolver import SupervisorResolver
from events import EventType, PlatformEvent, EventBus


from poc.tests.hierarchy_test_support import db, mock_runtime, engine

def test_scenario_a_hierarchical_delegation_and_propagation(db, engine):
    """
    Scenario A: CEO delegates to Software Architect, Architect delegates to Backend and Frontend workers.
    Both workers complete, Architect receives actual results before reporting completion to CEO.
    """
    proj_id = f"proj-a-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Scenario A Project", description="Test", working_directory="."))

    # 1. Root CEO Task
    ceo_task_id = f"ceo-task-{uuid.uuid4().hex[:6]}"
    ceo_task = AgentRun(
        run_id=ceo_task_id,
        agent_id="ceo-orchestrator",
        project_id=proj_id,
        prompt="Lead project development",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(ceo_task)

    # 2. CEO delegates to Software Architect
    arch_subtask = engine.delegate_task(
        parent_task_id=ceo_task_id,
        target_agent_id="software-architect",
        subtask_prompt="Design architecture and supervise engineering"
    )

    # CEO must be suspended in WAITING_FOR_CHILDREN
    ceo_task_reloaded = db.get_task_run(ceo_task_id)
    assert ceo_task_reloaded.status == TaskStatus.WAITING_FOR_CHILDREN

    # 3. Architect delegates to Backend Developer and Frontend Developer
    be_subtask = engine.delegate_task(
        parent_task_id=arch_subtask.run_id,
        target_agent_id="backend-developer",
        subtask_prompt="Implement REST API endpoints"
    )
    fe_subtask = engine.delegate_task(
        parent_task_id=arch_subtask.run_id,
        target_agent_id="frontend-developer",
        subtask_prompt="Implement UI components"
    )

    # Architect must be WAITING_FOR_CHILDREN, not completed!
    arch_reloaded = db.get_task_run(arch_subtask.run_id)
    assert arch_reloaded.status == TaskStatus.WAITING_FOR_CHILDREN

    # 4. Backend completes with actual deliverables
    be_structured = {
        "status": "completed",
        "summary": "Implemented auth and user API",
        "deliverables": ["/api/v1/auth", "/api/v1/users"],
        "errors": None,
        "verification_evidence": "API unit tests passed 100%"
    }
    engine.complete_task(be_subtask.run_id, result="Auth and User API ready", structured_result=be_structured)

    # Architect must STILL be WAITING_FOR_CHILDREN because Frontend is not done yet
    arch_reloaded = db.get_task_run(arch_subtask.run_id)
    assert arch_reloaded.status == TaskStatus.WAITING_FOR_CHILDREN

    # 5. Frontend completes with actual deliverables
    fe_structured = {
        "status": "completed",
        "summary": "Implemented Dashboard and Auth views",
        "deliverables": ["src/components/Auth.tsx", "src/components/Dashboard.tsx"],
        "errors": None,
        "verification_evidence": "Frontend TypeScript build clean"
    }
    engine.complete_task(fe_subtask.run_id, result="UI components ready", structured_result=fe_structured)

    # 6. Both workers done! Architect automatically resumes, verifies, and completes milestone
    arch_done = db.get_task_run(arch_subtask.run_id)
    assert arch_done.status == TaskStatus.COMPLETED
    assert arch_done.structured_result is not None
    assert "Milestone verified by software-architect" in arch_done.structured_result["summary"]
    assert len(arch_done.structured_result["deliverables"]) >= 2

    # 7. Milestone propagated upward to CEO! CEO receives Architect's verified result
    ceo_done = db.get_task_run(ceo_task_id)
    assert ceo_done.status == TaskStatus.COMPLETED
    assert "Milestone verified" in ceo_done.structured_result["summary"]


def test_scenario_c_manager_cannot_complete_with_running_or_failed_child(db, engine):
    """
    Scenario C: A manager cannot report completion while a mandatory child task is
    still running or has failed.
    """
    proj_id = f"proj-c-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Scenario C Project", description="Test", working_directory="."))
    mgr_task_id = f"mgr-task-{uuid.uuid4().hex[:6]}"

    mgr_task = AgentRun(
        run_id=mgr_task_id,
        agent_id="software-architect",
        project_id=proj_id,
        prompt="Coordinate backend delivery",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(mgr_task)

    # Manager delegates child task
    child = engine.delegate_task(
        parent_task_id=mgr_task_id,
        target_agent_id="backend-developer",
        subtask_prompt="Implement database migrations"
    )

    mgr_curr = db.get_task_run(mgr_task_id)
    assert mgr_curr.status == TaskStatus.WAITING_FOR_CHILDREN

    # Child fails
    engine.fail_task(child.run_id, error="Migration syntax error on line 42")

    # Manager must NOT be completed; it must be marked FAILED due to child failure
    mgr_after_fail = db.get_task_run(mgr_task_id)
    assert mgr_after_fail.status == TaskStatus.FAILED
    assert "Mandatory child task(s) failed" in mgr_after_fail.error


def test_scenario_d_worker_failure_propagation_and_manager_retry(db, engine):
    """
    Scenario D: A worker fails, failure propagates upward, and manager initiates retry or remediation.
    """
    proj_id = f"proj-d-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Scenario D Project", description="Test", working_directory="."))
    mgr_task_id = f"mgr-d-{uuid.uuid4().hex[:6]}"

    mgr_task = AgentRun(
        run_id=mgr_task_id,
        agent_id="software-architect",
        project_id=proj_id,
        prompt="Execute QA test suite",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(mgr_task)

    qa_child = engine.delegate_task(
        parent_task_id=mgr_task_id,
        target_agent_id="qa-test-engineer",
        subtask_prompt="Run full regression test suite"
    )

    # QA fails
    engine.fail_task(qa_child.run_id, error="Integration timeout on /api/v1/orders")

    # Manager receives failure
    mgr_reloaded = db.get_task_run(mgr_task_id)
    assert mgr_reloaded.status == TaskStatus.FAILED

    # Manager initiates retry according to policy
    retried_child = engine.retry_task(qa_child.run_id, reason="Transient test runner network glitch")

    assert retried_child.status == TaskStatus.RUNNING
    assert retried_child.retry_count == 1
    assert retried_child.error is None

    # Manager is restored to WAITING_FOR_CHILDREN
    mgr_restored = db.get_task_run(mgr_task_id)
    assert mgr_restored.status == TaskStatus.WAITING_FOR_CHILDREN

    # Retried child now completes successfully
    engine.complete_task(
        qa_child.run_id,
        result="All 48 tests passed on retry",
        structured_result={
            "status": "completed",
            "summary": "100% test pass rate after retry",
            "deliverables": ["test-report.xml"],
            "errors": None,
            "verification_evidence": "48/48 tests green"
        }
    )

    # Manager now verifies and completes successfully
    mgr_final = db.get_task_run(mgr_task_id)
    assert mgr_final.status == TaskStatus.COMPLETED


def test_scenario_e_concurrent_independent_tasks_and_dependent_tasks(db, engine):
    """
    Scenario E: Independent child tasks execute concurrently while dependent tasks wait.
    Backend (T1) and Frontend (T2) run concurrently. QA (T3) depends on T1 and T2.
    """
    proj_id = f"proj-e-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Scenario E Project", description="Test", working_directory="."))
    mgr_task_id = f"mgr-e-{uuid.uuid4().hex[:6]}"

    mgr_task = AgentRun(
        run_id=mgr_task_id,
        agent_id="software-architect",
        project_id=proj_id,
        prompt="Coordinate full stack sprint",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(mgr_task)

    # T1: Backend (independent)
    t1 = engine.delegate_task(
        parent_task_id=mgr_task_id,
        target_agent_id="backend-developer",
        subtask_prompt="Build core API"
    )
    # T2: Frontend (independent)
    t2 = engine.delegate_task(
        parent_task_id=mgr_task_id,
        target_agent_id="frontend-developer",
        subtask_prompt="Build client dashboard"
    )

    # Both independent tasks are immediately RUNNING (concurrent)
    assert t1.status == TaskStatus.RUNNING
    assert t2.status == TaskStatus.RUNNING

    # T3: QA depends on [T1, T2]
    t3 = engine.delegate_task(
        parent_task_id=mgr_task_id,
        target_agent_id="qa-test-engineer",
        subtask_prompt="Run end-to-end integration tests",
        dependencies=[t1.run_id, t2.run_id]
    )

    # T3 must be QUEUED because prerequisites are not completed yet!
    assert t3.status == TaskStatus.QUEUED

    # Complete T1
    engine.complete_task(t1.run_id, result="Core API built")

    # T3 must STILL be QUEUED (T2 is still running!)
    t3_check = db.get_task_run(t3.run_id)
    assert t3_check.status == TaskStatus.QUEUED

    # Complete T2
    engine.complete_task(t2.run_id, result="Client dashboard built")

    # All dependencies met! T3 automatically unblocked and transitioned to RUNNING!
    t3_unblocked = db.get_task_run(t3.run_id)
    assert t3_unblocked.status == TaskStatus.RUNNING

    # Complete T3
    engine.complete_task(t3.run_id, result="E2E tests passed")

    # Manager completes
    mgr_done = db.get_task_run(mgr_task_id)
    assert mgr_done.status == TaskStatus.COMPLETED


def test_scenario_f_server_restart_recovery_and_idempotency(db, engine):
    """
    Scenario F: Server restart preserves pending tasks and resumes suspended parent
    without duplicate execution.
    """
    proj_id = f"proj-f-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Scenario F Project", description="Test", working_directory="."))
    parent_id = f"parent-f-{uuid.uuid4().hex[:6]}"
    child_id = f"child-f-{uuid.uuid4().hex[:6]}"

    # Create parent in WAITING_FOR_CHILDREN and child in COMPLETED
    parent = AgentRun(
        run_id=parent_id,
        agent_id="software-architect",
        project_id=proj_id,
        prompt="Design system",
        status=TaskStatus.WAITING_FOR_CHILDREN,
        created_at=datetime.now()
    )
    db.save_task_run(parent)

    child = AgentRun(
        run_id=child_id,
        agent_id="backend-developer",
        project_id=proj_id,
        prompt="Build endpoints",
        status=TaskStatus.COMPLETED,
        result="Endpoints built",
        created_at=datetime.now(),
        parent_task_id=parent_id
    )
    db.save_task_run(child)

    # Simulate restart with new engine instance
    new_engine = OrchestrationEngine(db_manager=db)

    # First recovery run: parent resumes and completes
    recovered = new_engine.recover_pending_tasks()
    assert recovered >= 1

    parent_after = db.get_task_run(parent_id)
    assert parent_after.status == TaskStatus.COMPLETED

    # Second recovery run: must be completely idempotent (0 additional resumptions)
    second_recovered = new_engine.recover_pending_tasks()
    assert second_recovered == 0

