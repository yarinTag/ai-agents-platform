"""
Tests for the 3 Advanced Session Isolation Upgrades:
1. Scoped Pairwise Session Keys (channel:manager:worker:task_id)
2. Dual-Track Resolution (Fast Path vs Slow Path)
3. Lean Decision Envelopes (Sanitized Context & Structured Decisions)
"""

import pytest
import uuid
from datetime import datetime

from config import AgentConfig, AgentRole, ProjectConfig
from persistence import DatabaseManager, AgentMessage
from runtime_adapter import TaskStatus, AgentRun
from orchestration.supervisor_resolver import (
    SupervisorResolver,
    DecisionQuestionEnvelope,
    DecisionAnswerEnvelope
)


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_session_isolation.db"
    return DatabaseManager(db_path=str(db_file))


@pytest.fixture
def setup_org(db):
    """
    Setup 1 Manager (Software Architect) and 2 Workers (Backend Dev, Frontend Dev).
    """
    proj_id = f"proj-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(
        id=proj_id,
        name="Session Isolation Test Project",
        description="Test",
        working_directory="."
    ))

    mgr_id = "software-architect"
    be_id = "backend-developer"
    fe_id = "frontend-developer"

    mgr = AgentConfig(
        id=mgr_id,
        name="Software Architect",
        description="Engineering Manager",
        system_prompt="Manage architecture",
        role_type=AgentRole.MANAGER.value,
        allowed_child_ids=[be_id, fe_id]
    )
    be = AgentConfig(
        id=be_id,
        name="Backend Developer",
        description="Backend worker",
        system_prompt="Write backend code",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id
    )
    fe = AgentConfig(
        id=fe_id,
        name="Frontend Developer",
        description="Frontend worker",
        system_prompt="Write frontend code",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id
    )

    db.save_agent(mgr)
    db.save_agent(be)
    db.save_agent(fe)

    return {
        "proj_id": proj_id,
        "mgr": mgr_id,
        "be": be_id,
        "fe": fe_id
    }


def test_upgrade_1_scoped_pairwise_session_channels(db, setup_org):
    """
    Upgrade 1: Verify that two subagents under the same manager have completely
    isolated pairwise channels (channel:manager:worker:task_id) with ZERO cross-talk.
    """
    org = setup_org
    task_be = f"task-be-{uuid.uuid4().hex[:6]}"
    task_fe = f"task-fe-{uuid.uuid4().hex[:6]}"

    # Save task runs to satisfy FK constraints
    db.save_task_run(AgentRun(
        run_id=task_be,
        agent_id=org["be"],
        project_id=org["proj_id"],
        prompt="Backend task",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    ))
    db.save_task_run(AgentRun(
        run_id=task_fe,
        agent_id=org["fe"],
        project_id=org["proj_id"],
        prompt="Frontend task",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    ))

    # Backend Dev channel with Architect
    chan_be = db.get_or_create_channel(
        manager_id=org["mgr"],
        worker_id=org["be"],
        task_id=task_be,
        project_id=org["proj_id"]
    )
    assert chan_be["channel_key"] == f"channel:{org['mgr']}:{org['be']}:{task_be}"

    # Frontend Dev channel with Architect
    chan_fe = db.get_or_create_channel(
        manager_id=org["mgr"],
        worker_id=org["fe"],
        task_id=task_fe,
        project_id=org["proj_id"]
    )
    assert chan_fe["channel_key"] == f"channel:{org['mgr']}:{org['fe']}:{task_fe}"

    # Ensure conversation IDs are completely distinct
    assert chan_be["id"] != chan_fe["id"]

    # Send message on Backend channel
    msg_be = db.save_agent_message(AgentMessage(
        id=f"msg_be_{uuid.uuid4().hex[:6]}",
        from_agent_id=org["be"],
        to_agent_id=org["mgr"],
        task_id=task_be,
        channel_key=chan_be["channel_key"],
        content="PostgreSQL schema question",
        message_type="QUESTION"
    ))

    # Send message on Frontend channel
    msg_fe = db.save_agent_message(AgentMessage(
        id=f"msg_fe_{uuid.uuid4().hex[:6]}",
        from_agent_id=org["fe"],
        to_agent_id=org["mgr"],
        task_id=task_fe,
        channel_key=chan_fe["channel_key"],
        content="Tailwind color palette question",
        message_type="QUESTION"
    ))

    # Query Backend channel messages: Must ONLY contain Backend messages!
    be_msgs = db.list_agent_messages(channel_key=chan_be["channel_key"])
    assert len(be_msgs) == 1
    assert be_msgs[0].content == "PostgreSQL schema question"
    assert be_msgs[0].from_agent_id == org["be"]

    # Query Frontend channel messages: Must ONLY contain Frontend messages!
    fe_msgs = db.list_agent_messages(channel_key=chan_fe["channel_key"])
    assert len(fe_msgs) == 1
    assert fe_msgs[0].content == "Tailwind color palette question"
    assert fe_msgs[0].from_agent_id == org["fe"]


def test_upgrade_2_dual_track_fast_vs_slow_path(db, setup_org):
    """
    Upgrade 2: Verify Dual-Track resolution:
    - Fast Path: Instant resolution from ADR / Shared Memory (<50ms).
    - Slow Path: Escalation to Manager/Human when decision exceeds authority.
    """
    org = setup_org
    resolver = SupervisorResolver(db_manager=db)

    # Configure Super Agent with strict human approval policy for production changes
    from config import SuperAgentConfig
    db.save_super_agent_config(SuperAgentConfig(
        agent_id=org["mgr"],
        project_id=org["proj_id"],
        require_human_approval_for=["production_changes", "destructive_actions"]
    ))

    # Seed an Architectural Decision Record (ADR) in project memory
    db.create_project_memory({
        "project_id": org["proj_id"],
        "category": "ADR",
        "title": "Database Engine Standard",
        "content": "All services must strictly use PostgreSQL 16 with asyncpg drivers.",
        "tags": ["database", "postgresql", "orm"]
    })

    task_id_1 = f"task-fast-{uuid.uuid4().hex[:6]}"
    task_run_1 = AgentRun(
        run_id=task_id_1,
        agent_id=org["be"],
        project_id=org["proj_id"],
        prompt="Design database layer",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(task_run_1)

    # 1. Ask a question answered by ADR memory -> MUST BE FAST PATH
    res_fast = resolver.resolve_or_escalate_question(
        task_id=task_id_1,
        requester_agent_id=org["be"],
        question="Which database engine and driver should we use for the new service?",
        project_id=org["proj_id"]
    )

    assert res_fast["path"] == "FAST_PATH"
    assert res_fast["status"] == "AUTO_RESOLVED"
    assert "PostgreSQL 16" in res_fast["answer"]
    assert res_fast["channel_key"] == f"channel:{org['mgr']}:{org['be']}:{task_id_1}"

    # 2. Ask a question not in memory and involving production deployment -> MUST BE SLOW PATH
    task_id_2 = f"task-slow-{uuid.uuid4().hex[:6]}"
    task_run_2 = AgentRun(
        run_id=task_id_2,
        agent_id=org["be"],
        project_id=org["proj_id"],
        prompt="Deploy to production cluster",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(task_run_2)

    res_slow = resolver.resolve_or_escalate_question(
        task_id=task_id_2,
        requester_agent_id=org["be"],
        question="Should I deploy the production release to the live Kubernetes cluster now?",
        project_id=org["proj_id"]
    )

    assert res_slow["path"] == "SLOW_PATH"
    assert res_slow["status"] == "PENDING_INPUT"
    assert res_slow["target_approver"] == "HUMAN_OPERATOR"  # Production changes require human approval


def test_upgrade_3_lean_decision_envelopes(db, setup_org):
    """
    Upgrade 3: Verify Lean Decision Envelopes sanitize noisy context,
    truncate terminal output to max 500 characters, and structure decisions.
    """
    org = setup_org

    # Simulate noisy terminal log with ANSI colors and 2,000 characters of noise
    noisy_ansi_context = (
        "\x1b[31m[ERROR]\x1b[0m Failed to bind port 8080: Address already in use\n"
        + "Traceback (most recent call last):\n"
        + ("    File '/app/server.py', line 45, in <module>\n" * 50)
        + "\x1b[32m[INFO]\x1b[0m Worker shut down gracefully."
    )
    assert len(noisy_ansi_context) > 1500

    q_env = DecisionQuestionEnvelope.create(
        task_id="task-env-123",
        requester_agent_id=org["be"],
        target_approver_id=org["mgr"],
        question="Which port should the backend bind to if 8080 is occupied?",
        context=noisy_ansi_context,
        suggested_options=["Port 8000", "Port 3001", "Port 5000"]
    )

    # Verify context is sanitized: ANSI codes removed and length truncated to <= 503 chars (500 + '...')
    assert "\x1b[31m" not in q_env.context_summary
    assert "\x1b[0m" not in q_env.context_summary
    assert len(q_env.context_summary) <= 503
    assert q_env.suggested_options == ["Port 8000", "Port 3001", "Port 5000"]
    assert q_env.channel_key == f"channel:{org['mgr']}:{org['be']}:task-env-123"

    # Verify DecisionAnswerEnvelope
    ans_env = DecisionAnswerEnvelope(
        task_id="task-env-123",
        decision="Use port 8000",
        rationale="Standard fallback port per system convention",
        source="SLOW_PATH_MANAGER",
        channel_key=q_env.channel_key,
        unblock=True
    )
    ans_dict = ans_env.to_dict()
    assert ans_dict["decision"] == "Use port 8000"
    assert ans_dict["unblock"] is True
    assert ans_dict["channel_key"] == q_env.channel_key
