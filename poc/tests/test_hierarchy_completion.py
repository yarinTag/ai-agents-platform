"""Test hierarchy completion. Existing cases moved without execution."""
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

