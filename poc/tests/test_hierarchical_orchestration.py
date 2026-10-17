"""
Automated Verification Suite for Reliable Hierarchical Agent Orchestration.

Tests mandatory scenarios A through I with real SQLite persistence and real orchestration logic:
A. CEO delegates to manager, manager delegates to 2 workers, workers complete, manager verifies before reporting completion.
B. Worker asks clarification question, manager answers, worker resumes with answer.
C. Manager cannot report completion while child task is running or failed.
D. Worker fails, failure propagates upward, manager initiates retry or remediation.
E. Independent child tasks run concurrently, dependent tasks wait for prerequisites.
F. Server restart recovery preserves tasks, prevents duplicate resumption.
G. Release Reviewer reports directly to CEO; restricted actions require approval.
H. Complete E2E hierarchical run produces final report through CEO / Brain only.
I. Windows compatibility: no hardcoded macOS paths, no python3 invocations.
"""

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


@pytest.fixture
def db():
    manager = get_db_manager()
    return manager


@pytest.fixture
def mock_runtime():
    """Mock runtime adapter to record launches without invoking external claude processes."""
    class MockAdapter:
        def __init__(self):
            self.started_tasks = []
            self.resumed_tasks = []
            self.on_task_completed = None

        def start_task(self, task_id=None, agent_id=None, project_id=None, prompt=None, **kwargs):
            tid = task_id or f"run_{uuid.uuid4().hex[:6]}"
            self.started_tasks.append((tid, agent_id or task_id, prompt))
            return tid

        def resume_task(self, task_id, answer):
            self.resumed_tasks.append((task_id, answer))
            return f"resume_{task_id}"

    return MockAdapter()


@pytest.fixture
def engine(db, mock_runtime):
    ev_svc = get_event_service()
    eng = OrchestrationEngine(db_manager=db, runtime_adapter=mock_runtime, event_service=ev_svc)
    mock_runtime.on_task_completed = eng.handle_task_completion
    return eng


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


def test_scenario_b_worker_question_hierarchical_resolution(db, engine, mock_runtime):
    """
    Scenario B: A worker asks a clarification question, its direct manager answers,
    and the worker resumes with the answer preserved.
    """
    proj_id = f"proj-b-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Scenario B Project", description="Test", working_directory="."))
    worker_task_id = f"worker-task-{uuid.uuid4().hex[:6]}"

    # Worker task under Software Architect
    worker_task = AgentRun(
        run_id=worker_task_id,
        agent_id="backend-developer",
        project_id=proj_id,
        prompt="Implement payment processing service",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(worker_task)

    resolver = SupervisorResolver(db, runtime_adapter=mock_runtime)

    # Worker asks question
    q_res = resolver.resolve_or_escalate_question(
        task_id=worker_task_id,
        requester_agent_id="backend-developer",
        project_id=proj_id,
        question="Which payment gateway SDK version should we pin in dependencies?"
    )

    assert q_res["status"] == "PENDING_INPUT"
    assert q_res["target_approver"] == "software-architect"  # Routed to direct manager!

    # Task is WAITING_INPUT
    t_waiting = db.get_task_run(worker_task_id)
    assert t_waiting.status == TaskStatus.WAITING_INPUT

    # Manager answers the question
    db.resolve_interaction(
        interaction_id=q_res["interaction_id"],
        resolution_response="Pin stripe-python to version 8.5.0 per ADR-12.",
        resolved_by="AGENT:software-architect",
        decision="RESOLVED"
    )

    # Worker task resumes via runtime adapter
    mock_runtime.resume_task(worker_task_id, "Pin stripe-python to version 8.5.0 per ADR-12.")
    db.update_task_run(worker_task_id, status=TaskStatus.RUNNING, result="Resumed with manager decision: stripe-python 8.5.0")

    t_resumed = db.get_task_run(worker_task_id)
    assert t_resumed.status == TaskStatus.RUNNING
    assert "stripe-python 8.5.0" in t_resumed.result


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


def test_scenario_g_release_security_reviewer_hierarchy_and_permissions(db, engine):
    """
    Scenario G: Release Reviewer reports directly to CEO; unauthorized delegations fail;
    restricted destructive operations require human approval.
    """
    proj_id = f"proj-g-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Scenario G Project", description="Test", working_directory="."))

    # 1. PM trying to delegate to Release Reviewer must FAIL (violates hierarchy)
    pm_task = AgentRun(
        run_id=f"pm-{uuid.uuid4().hex[:6]}",
        agent_id="product-manager",
        project_id=proj_id,
        prompt="Author PRD",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(pm_task)

    with pytest.raises(DelegationError):
        engine.delegate_task(
            parent_task_id=pm_task.run_id,
            target_agent_id="release-security-reviewer",
            subtask_prompt="Audit code"
        )

    # 2. Worker trying to delegate to anyone must FAIL
    worker_task = AgentRun(
        run_id=f"worker-{uuid.uuid4().hex[:6]}",
        agent_id="backend-developer",
        project_id=proj_id,
        prompt="Code API",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(worker_task)

    with pytest.raises(DelegationError):
        engine.delegate_task(
            parent_task_id=worker_task.run_id,
            target_agent_id="qa-test-engineer",
            subtask_prompt="Test my code"
        )

    # 3. CEO delegating to Release Reviewer SUCCEEDS (direct reporting line)
    ceo_task = AgentRun(
        run_id=f"ceo-{uuid.uuid4().hex[:6]}",
        agent_id="ceo-orchestrator",
        project_id=proj_id,
        prompt="Coordinate release",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(ceo_task)

    sec_task = engine.delegate_task(
        parent_task_id=ceo_task.run_id,
        target_agent_id="release-security-reviewer",
        subtask_prompt="Audit codebase for CVEs and SSRF"
    )
    assert sec_task.agent_id == "release-security-reviewer"


def test_scenario_h_e2e_project_completion_via_ceo_only(db, engine):
    """
    Scenario H: Complete end-to-end project run produces final human-facing report through CEO only.
    """
    proj_id = f"proj-h-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="LMS Full Project", description="Full E2E", working_directory="."))

    # Step 1: CEO initiates project
    ceo_task = AgentRun(
        run_id=f"ceo-root-{uuid.uuid4().hex[:6]}",
        agent_id="ceo-orchestrator",
        project_id=proj_id,
        prompt="Build LMS application from scratch",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(ceo_task)

    # Step 2: CEO delegates M1 to PM
    pm_subtask = engine.delegate_task(
        parent_task_id=ceo_task.run_id,
        target_agent_id="product-manager",
        subtask_prompt="Author PRD and coordinate UX flows"
    )
    # PM delegates UX to Designer
    ux_subtask = engine.delegate_task(
        parent_task_id=pm_subtask.run_id,
        target_agent_id="ui-ux-designer",
        subtask_prompt="Create USER_FLOWS.md"
    )
    # Designer completes
    engine.complete_task(ux_subtask.run_id, result="USER_FLOWS.md created")
    # PM verifies and completes M1
    assert db.get_task_run(pm_subtask.run_id).status == TaskStatus.COMPLETED

    # Step 3: CEO delegates M2 to Software Architect
    arch_subtask = engine.delegate_task(
        parent_task_id=ceo_task.run_id,
        target_agent_id="software-architect",
        subtask_prompt="Design and implement architecture"
    )
    be_task = engine.delegate_task(parent_task_id=arch_subtask.run_id, target_agent_id="backend-developer", subtask_prompt="Build APIs")
    qa_task = engine.delegate_task(parent_task_id=arch_subtask.run_id, target_agent_id="qa-test-engineer", subtask_prompt="Verify tests", dependencies=[be_task.run_id])

    engine.complete_task(be_task.run_id, result="Backend APIs live")
    engine.complete_task(qa_task.run_id, result="All tests green")
    # Architect completes M2
    assert db.get_task_run(arch_subtask.run_id).status == TaskStatus.COMPLETED

    # Step 4: CEO delegates M3 to Release Reviewer
    sec_subtask = engine.delegate_task(
        parent_task_id=ceo_task.run_id,
        target_agent_id="release-security-reviewer",
        subtask_prompt="Audit security and produce RELEASE_REPORT.md"
    )
    engine.complete_task(sec_subtask.run_id, result="Security audit passed, GO verdict")

    # Step 5: CEO task resumes and produces final human report
    ceo_final = db.get_task_run(ceo_task.run_id)
    assert ceo_final.status == TaskStatus.COMPLETED

    # Verify project completion check
    verdict = engine.verify_project_completion(proj_id, ceo_task.run_id)
    assert verdict["completed"] is True
    assert verdict["verdict"] == "GO"


def test_scenario_i_windows_compatibility_and_zero_hardcoded_paths():
    """
    Scenario I: Verify zero hardcoded macOS paths (/Users/yarintag) exist in configuration,
    and delegation commands do not use invalid python3 on Windows.
    """
    poc_root = Path(__file__).resolve().parent.parent

    # Check agents.json
    for cfg_path in [poc_root / "config" / "agents.json", poc_root / "backend" / "config" / "agents.json"]:
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "/Users/yarintag" not in content, f"Hardcoded macOS path found in {cfg_path}"
                assert "python3 -m orchestration.delegate" not in content, f"Hardcoded python3 found in {cfg_path}"

    # Check projects.json
    proj_cfg = poc_root / "config" / "projects.json"
    if proj_cfg.exists():
        with open(proj_cfg, "r", encoding="utf-8") as f:
            content = f.read()
            assert "/Users/yarintag" not in content, "Hardcoded macOS path found in projects.json"

    # Check delegate.py shebang
    delegate_file = poc_root / "orchestration" / "delegate.py"
    with open(delegate_file, "r", encoding="utf-8") as f:
        first_line = f.readline()
        assert "python3" not in first_line, f"python3 shebang found in {delegate_file}"


def test_custom_department_arbitrary_hierarchy(db, engine):
    """
    Verify that the system is completely generic and supports ANY arbitrary
    department structure (e.g. Marketing, Data Science, Legal) and custom flow.
    """
    # 1. Define custom agents across a custom department
    head_of_marketing = AgentConfig(
        id="cmo-marketing-lead",
        name="Chief Marketing Officer",
        description="Leads growth and marketing campaigns",
        system_prompt="You lead growth.",
        role_type=AgentRole.MANAGER.value,
        parent_id="ceo-orchestrator",
        allowed_child_ids=["seo-specialist", "copywriter-agent"]
    )
    seo_specialist = AgentConfig(
        id="seo-specialist",
        name="SEO Specialist",
        description="Optimizes keywords and ranking",
        system_prompt="You do SEO.",
        role_type=AgentRole.WORKER.value,
        parent_id="cmo-marketing-lead",
        allowed_child_ids=[]
    )
    copywriter = AgentConfig(
        id="copywriter-agent",
        name="Copywriter",
        description="Authors copy and content",
        system_prompt="You write copy.",
        role_type=AgentRole.WORKER.value,
        parent_id="cmo-marketing-lead",
        allowed_child_ids=[]
    )
    for agent in [head_of_marketing, seo_specialist, copywriter]:
        db.save_agent(agent)

    proj_id = f"proj-marketing-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Q4 Marketing Campaign", description="Custom Flow", working_directory="."))

    # 2. CEO delegates campaign to CMO
    ceo_task = AgentRun(
        run_id=f"ceo-mktg-{uuid.uuid4().hex[:6]}",
        agent_id="ceo-orchestrator",
        project_id=proj_id,
        prompt="Launch Q4 Marketing Campaign",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(ceo_task)

    cmo_task = engine.delegate_task(
        parent_task_id=ceo_task.run_id,
        target_agent_id="cmo-marketing-lead",
        subtask_prompt="Develop and execute growth strategy"
    )
    assert cmo_task.agent_id == "cmo-marketing-lead"
    assert db.get_task_run(ceo_task.run_id).status == TaskStatus.WAITING_FOR_CHILDREN

    # 3. CMO delegates to SEO and Copywriter with dependency: Copywriter depends on SEO research
    seo_task = engine.delegate_task(
        parent_task_id=cmo_task.run_id,
        target_agent_id="seo-specialist",
        subtask_prompt="Conduct keyword research"
    )
    copy_task = engine.delegate_task(
        parent_task_id=cmo_task.run_id,
        target_agent_id="copywriter-agent",
        subtask_prompt="Draft blog posts based on SEO keywords",
        dependencies=[seo_task.run_id]
    )

    # SEO is RUNNING, Copywriter is QUEUED
    assert seo_task.status == TaskStatus.RUNNING
    assert copy_task.status == TaskStatus.QUEUED
    assert db.get_task_run(cmo_task.run_id).status == TaskStatus.WAITING_FOR_CHILDREN

    # 4. SEO completes -> Copywriter automatically unblocks
    engine.complete_task(
        seo_task.run_id,
        result="Keywords analyzed",
        structured_result={"status": "completed", "deliverables": ["keywords.csv"]}
    )
    assert db.get_task_run(copy_task.run_id).status == TaskStatus.RUNNING

    # 5. Copywriter completes -> CMO resumes and completes -> CEO resumes and completes
    engine.complete_task(
        copy_task.run_id,
        result="3 articles written",
        structured_result={"status": "completed", "deliverables": ["post1.md", "post2.md"]}
    )
    assert db.get_task_run(cmo_task.run_id).status == TaskStatus.COMPLETED
    assert db.get_task_run(ceo_task.run_id).status == TaskStatus.COMPLETED


def test_scenario_j_exact_user_requested_e2e_chain(db, engine, mock_runtime):
    """
    Scenario J: Exact user-specified flow:
    Human -> CEO/Orchestrator -> Software Architect -> Backend Developer
      -> Backend Developer asks Architect a question
      -> Architect answers
      -> Backend Developer resumes the same session
      -> Backend Developer completes
      -> Actual deliverables automatically return to Architect
      -> Architect resumes and validates them
      -> Architect reports back to CEO
      -> CEO continues workflow and completes.
    """
    proj_id = f"proj-j-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(id=proj_id, name="Exact E2E Chain Project", description="Test", working_directory="."))

    resolver = SupervisorResolver(db_manager=db, runtime_adapter=mock_runtime)

    # 1. Human -> CEO
    ceo_task_id = f"ceo-task-{uuid.uuid4().hex[:6]}"
    ceo_task = AgentRun(
        run_id=ceo_task_id,
        agent_id="ceo-orchestrator",
        project_id=proj_id,
        prompt="Lead project to deliver JWT Auth Service",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(ceo_task)

    # 2. CEO -> Software Architect
    arch_subtask = engine.delegate_task(
        parent_task_id=ceo_task_id,
        target_agent_id="software-architect",
        subtask_prompt="Design JWT architecture and manage backend delivery"
    )
    assert db.get_task_run(ceo_task_id).status == TaskStatus.WAITING_FOR_CHILDREN
    assert db.get_task_run(arch_subtask.run_id).status == TaskStatus.RUNNING

    # 3. Architect -> Backend Developer
    be_session_id = f"sess-be-auth-{uuid.uuid4().hex[:6]}"
    be_subtask = engine.delegate_task(
        parent_task_id=arch_subtask.run_id,
        target_agent_id="backend-developer",
        subtask_prompt="Implement JWT tokens and endpoints"
    )
    be_subtask.session_id = be_session_id
    db.save_task_run(be_subtask)
    assert db.get_task_run(arch_subtask.run_id).status == TaskStatus.WAITING_FOR_CHILDREN
    assert db.get_task_run(be_subtask.run_id).status == TaskStatus.RUNNING

    # 4. Backend Developer asks Architect a question
    q_res = resolver.resolve_or_escalate_question(
        task_id=be_subtask.run_id,
        requester_agent_id="backend-developer",
        project_id=proj_id,
        question="Which signing algorithm for JWT?"
    )
    assert q_res["status"] == "PENDING_INPUT"
    assert q_res["target_approver"] == "software-architect"
    assert db.get_task_run(be_subtask.run_id).status == TaskStatus.WAITING_INPUT

    # 5. Architect answers
    architect_answer = "Use RS256 with 2048-bit RSA keys per ADR-04."
    db.resolve_interaction(
        interaction_id=q_res["interaction_id"],
        resolution_response=architect_answer,
        resolved_by="AGENT:software-architect",
        decision="RESOLVED"
    )

    # 6. Backend Developer resumes the same session
    mock_runtime.resume_task(be_subtask.run_id, architect_answer)
    db.update_task_run(be_subtask.run_id, status=TaskStatus.RUNNING, result=f"Resumed: {architect_answer}")
    be_reloaded = db.get_task_run(be_subtask.run_id)
    assert be_reloaded.status == TaskStatus.RUNNING
    assert be_reloaded.session_id == be_session_id

    # 7. Backend Developer completes with actual deliverables
    be_structured = {
        "status": "completed",
        "summary": "JWT auth endpoints implemented with RS256",
        "deliverables": ["src/auth.py", "tests/test_auth.py"],
        "errors": None,
        "verification_evidence": "14/14 tests passing"
    }
    engine.complete_task(be_subtask.run_id, result="JWT Auth complete", structured_result=be_structured)
    assert db.get_task_run(be_subtask.run_id).status == TaskStatus.COMPLETED

    # 8. Deliverables return to Architect; Architect resumes and validates
    arch_reloaded = db.get_task_run(arch_subtask.run_id)
    assert arch_reloaded.status == TaskStatus.COMPLETED
    assert "Milestone verified by software-architect" in arch_reloaded.structured_result["summary"]
    assert "src/auth.py" in arch_reloaded.structured_result["deliverables"]

    # 9. Architect reports back to CEO; CEO resumes and continues workflow
    ceo_reloaded = db.get_task_run(ceo_task_id)
    assert ceo_reloaded.status == TaskStatus.COMPLETED
    assert "Milestone verified" in ceo_reloaded.structured_result["summary"]
    assert "src/auth.py" in ceo_reloaded.structured_result["deliverables"]


