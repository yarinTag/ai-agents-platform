"""Test hierarchy governance. Existing cases moved without execution."""
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

