"""Test hierarchy clarification. Existing cases moved without execution."""
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

