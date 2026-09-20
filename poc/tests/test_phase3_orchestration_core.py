"""
Automated tests for Phase 3: Orchestration Core, Persistence Methods, and Delegation Engine.
ZERO MOCKS POLICY: All tests run against live SQLite databases, real EventService/EventBus,
and real OrchestrationEngine instances.
"""

import pytest
import tempfile
import os
import uuid
from datetime import datetime

from config import AgentConfig, AgentRole, ProjectConfig
from runtime_adapter import AgentRun, TaskStatus, ClaudeCodeRuntimeAdapter
from persistence import DatabaseManager
from events import EventBus, EventService, EventType
from orchestration import (
    OrchestrationEngine,
    DelegationError,
    ConcurrencyLimitExceededError,
    validate_agent_hierarchy,
    HierarchyValidationError
)
from backend.dependencies import get_orchestration_engine, init_services


@pytest.fixture
def temp_db():
    """Create an isolated real SQLite DB with default schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    yield db
    if os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.fixture
def real_event_service(temp_db):
    """Create a real EventService with real in-memory EventBus and SQLite persistence."""
    bus = EventBus()
    service = EventService(db_manager=temp_db, event_bus=bus)
    return service


def test_agent_run_dataclass_and_serialization():
    """Test AgentRun dataclass fields, to_dict, and from_dict including parent_task_id, root_task_id, assigned_by."""
    now = datetime.now()
    run = AgentRun(
        run_id="run-101",
        agent_id="agent-worker-1",
        project_id="proj-alpha",
        prompt="Write unit tests",
        status=TaskStatus.PENDING,
        created_at=now,
        parent_task_id="parent-001",
        root_task_id="root-000",
        assigned_by="mgr-lead"
    )

    data = run.to_dict()
    assert data["run_id"] == "run-101"
    assert data["agent_id"] == "agent-worker-1"
    assert data["parent_task_id"] == "parent-001"
    assert data["root_task_id"] == "root-000"
    assert data["assigned_by"] == "mgr-lead"
    assert data["status"] == "pending"
    assert data["created_at"] == now.isoformat()

    restored = AgentRun.from_dict(data)
    assert restored.run_id == "run-101"
    assert restored.parent_task_id == "parent-001"
    assert restored.root_task_id == "root-000"
    assert restored.assigned_by == "mgr-lead"
    assert restored.status == TaskStatus.PENDING

    # Test backward compatibility when fields are missing from dict
    minimal_data = {
        "run_id": "run-legacy",
        "agent_id": "legacy-agent",
        "prompt": "Do legacy work",
        "status": "running",
        "created_at": now.isoformat()
    }
    legacy_run = AgentRun.from_dict(minimal_data)
    assert legacy_run.parent_task_id is None
    assert legacy_run.root_task_id is None
    assert legacy_run.assigned_by is None
    assert legacy_run.status == TaskStatus.RUNNING


def test_persistence_task_run_fields(temp_db):
    """Test SQLite persistence of parent_task_id, root_task_id, assigned_by."""
    # Create agents
    mgr = AgentConfig(id="mgr-1", name="Manager 1", description="desc", system_prompt="prompt", role_type="MANAGER")
    worker = AgentConfig(id="worker-1", name="Worker 1", description="desc", system_prompt="prompt", role_type="WORKER")
    temp_db.save_agent(mgr)
    temp_db.save_agent(worker)

    now = datetime.now()
    run = AgentRun(
        run_id="task-child-1",
        agent_id="worker-1",
        project_id=None,
        prompt="Implement persistence",
        status=TaskStatus.RUNNING,
        created_at=now,
        parent_task_id="task-parent-0",
        root_task_id="task-root-0",
        assigned_by="mgr-1"
    )
    temp_db.save_task_run(run)

    # get_task_run verification
    fetched = temp_db.get_task_run("task-child-1")
    assert fetched is not None
    assert fetched.run_id == "task-child-1"
    assert fetched.parent_task_id == "task-parent-0"
    assert fetched.root_task_id == "task-root-0"
    assert fetched.assigned_by == "mgr-1"
    assert fetched.status == TaskStatus.RUNNING

    # list_task_runs verification
    runs = temp_db.list_task_runs(agent_id="worker-1")
    assert len(runs) == 1
    assert runs[0].parent_task_id == "task-parent-0"
    assert runs[0].root_task_id == "task-root-0"
    assert runs[0].assigned_by == "mgr-1"


def test_persistence_subtasks_and_active_count(temp_db):
    """Test get_subtasks and count_active_subtasks_for_parent."""
    mgr = AgentConfig(id="mgr-eng", name="Manager", description="", system_prompt="", role_type="MANAGER")
    w1 = AgentConfig(id="w1", name="Worker 1", description="", system_prompt="", role_type="WORKER")
    w2 = AgentConfig(id="w2", name="Worker 2", description="", system_prompt="", role_type="WORKER")
    temp_db.save_agent(mgr)
    temp_db.save_agent(w1)
    temp_db.save_agent(w2)

    parent_id = "parent-task-100"
    now = datetime.now()

    # Subtask 1: running
    s1 = AgentRun(
        run_id="sub-1",
        agent_id="w1",
        project_id=None,
        prompt="Subtask 1",
        status=TaskStatus.RUNNING,
        created_at=now,
        parent_task_id=parent_id,
        root_task_id=parent_id,
        assigned_by="mgr-eng"
    )
    # Subtask 2: pending
    s2 = AgentRun(
        run_id="sub-2",
        agent_id="w2",
        project_id=None,
        prompt="Subtask 2",
        status=TaskStatus.PENDING,
        created_at=now,
        parent_task_id=parent_id,
        root_task_id=parent_id,
        assigned_by="mgr-eng"
    )
    # Subtask 3: completed
    s3 = AgentRun(
        run_id="sub-3",
        agent_id="w1",
        project_id=None,
        prompt="Subtask 3",
        status=TaskStatus.COMPLETED,
        created_at=now,
        parent_task_id=parent_id,
        root_task_id=parent_id,
        assigned_by="mgr-eng"
    )
    temp_db.save_task_run(s1)
    temp_db.save_task_run(s2)
    temp_db.save_task_run(s3)

    # get_subtasks
    subtasks = temp_db.get_subtasks(parent_id)
    assert len(subtasks) == 3
    assert [s.run_id for s in subtasks] == ["sub-1", "sub-2", "sub-3"]

    # count_active_subtasks_for_parent (running + pending = 2)
    active_count = temp_db.count_active_subtasks_for_parent("mgr-eng")
    assert active_count == 2

    # Different parent should have 0
    assert temp_db.count_active_subtasks_for_parent("other-agent") == 0


def test_persistence_task_tree_recursive(temp_db):
    """Test get_task_tree builds multi-level nested recursive structure with children."""
    proj = ProjectConfig(id="p1", name="Project 1", description="", working_directory=".")
    temp_db.save_project(proj)
    agent = AgentConfig(id="agent-x", name="Agent", description="", system_prompt="")
    temp_db.save_agent(agent)

    now = datetime.now()
    root_id = "task-tree-root"

    # Root task
    root_run = AgentRun(
        run_id=root_id,
        agent_id="agent-x",
        project_id="p1",
        prompt="Root Prompt",
        status=TaskStatus.RUNNING,
        created_at=now,
        parent_task_id=None,
        root_task_id=root_id
    )
    temp_db.save_task_run(root_run)

    # Child 1
    child1 = AgentRun(
        run_id="child-1",
        agent_id="agent-x",
        project_id="p1",
        prompt="Child 1",
        status=TaskStatus.COMPLETED,
        created_at=now,
        parent_task_id=root_id,
        root_task_id=root_id
    )
    temp_db.save_task_run(child1)

    # Child 2
    child2 = AgentRun(
        run_id="child-2",
        agent_id="agent-x",
        project_id="p1",
        prompt="Child 2",
        status=TaskStatus.RUNNING,
        created_at=now,
        parent_task_id=root_id,
        root_task_id=root_id
    )
    temp_db.save_task_run(child2)

    # Grandchild under Child 2
    grandchild = AgentRun(
        run_id="grandchild-1",
        agent_id="agent-x",
        project_id="p1",
        prompt="Grandchild",
        status=TaskStatus.PENDING,
        created_at=now,
        parent_task_id="child-2",
        root_task_id=root_id
    )
    temp_db.save_task_run(grandchild)

    tree = temp_db.get_task_tree(root_id)
    assert tree is not None
    assert tree["run_id"] == root_id
    assert "children" in tree
    assert len(tree["children"]) == 2

    child_map = {c["run_id"]: c for c in tree["children"]}
    assert "child-1" in child_map
    assert "child-2" in child_map
    assert len(child_map["child-1"]["children"]) == 0
    assert len(child_map["child-2"]["children"]) == 1
    assert child_map["child-2"]["children"][0]["run_id"] == "grandchild-1"


def test_orchestration_engine_delegation_success(temp_db, real_event_service):
    """Test successful task delegation, event emission, and DB persistence."""
    # Setup project
    proj = ProjectConfig(id="proj-core", name="Core Project", description="", working_directory=".")
    temp_db.save_project(proj)

    # Setup agents
    mgr = AgentConfig(
        id="eng-manager",
        name="Engineering Manager",
        description="",
        system_prompt="",
        role_type=AgentRole.MANAGER.value,
        max_concurrent_children=2
    )
    dev = AgentConfig(
        id="frontend-dev",
        name="Frontend Developer",
        description="",
        system_prompt="",
        role_type=AgentRole.WORKER.value,
        parent_id="eng-manager"
    )
    temp_db.save_agent(mgr)
    temp_db.save_agent(dev)

    # Create parent task
    parent_run = AgentRun(
        run_id="parent-task-77",
        agent_id="eng-manager",
        project_id="proj-core",
        prompt="Build feature",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    temp_db.save_task_run(parent_run)

    # Real engine instance
    runtime = ClaudeCodeRuntimeAdapter()
    engine = OrchestrationEngine(
        db_manager=temp_db,
        runtime_adapter=runtime,
        event_service=real_event_service
    )

    # Delegate
    subtask = engine.delegate_task(
        parent_task_id="parent-task-77",
        target_agent_id="frontend-dev",
        subtask_prompt="Create Navigation Bar"
    )

    # Verify returned subtask
    assert subtask.run_id.startswith("subtask-")
    assert subtask.agent_id == "frontend-dev"
    assert subtask.project_id == "proj-core"
    assert subtask.prompt == "Create Navigation Bar"
    assert subtask.status == TaskStatus.PENDING
    assert subtask.parent_task_id == "parent-task-77"
    assert subtask.root_task_id == "parent-task-77"
    assert subtask.assigned_by == "eng-manager"

    # Verify persisted in DB
    db_run = temp_db.get_task_run(subtask.run_id)
    assert db_run is not None
    assert db_run.assigned_by == "eng-manager"
    assert db_run.parent_task_id == "parent-task-77"

    # Verify events persisted in real event_log
    events = real_event_service.get_events(task_id=subtask.run_id)
    event_types = [e.event_type for e in events]
    assert EventType.TASK_DELEGATED.value in event_types
    assert EventType.TASK_CREATED.value in event_types

    # Find the delegation event payload
    delegated_event = next(e for e in events if e.event_type == EventType.TASK_DELEGATED.value)
    assert delegated_event.payload["parent_task_id"] == "parent-task-77"
    assert delegated_event.payload["subtask_id"] == subtask.run_id
    assert delegated_event.payload["parent_agent_id"] == "eng-manager"
    assert delegated_event.payload["target_agent_id"] == "frontend-dev"


def test_orchestration_engine_delegation_errors(temp_db, real_event_service):
    """Test validation errors: parent task missing, agents missing, unauthorized delegation."""
    runtime = ClaudeCodeRuntimeAdapter()
    engine = OrchestrationEngine(
        db_manager=temp_db,
        runtime_adapter=runtime,
        event_service=real_event_service
    )

    # 1. Parent task not found
    with pytest.raises(DelegationError, match="Parent task not found"):
        engine.delegate_task("nonexistent-task", "target-agent", "prompt")

    # Setup parent task with non-existent parent agent
    ghost = AgentConfig(id="ghost-agent", name="Ghost", description="", system_prompt="")
    temp_db.save_agent(ghost)
    bad_parent = AgentRun(
        run_id="orphan-task",
        agent_id="ghost-agent",
        project_id=None,
        prompt="prompt",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    temp_db.save_task_run(bad_parent)
    with temp_db._get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM agents WHERE id = 'ghost-agent'")
        conn.commit()

    # 2. Parent agent not found
    with pytest.raises(DelegationError, match="Parent agent not found"):
        engine.delegate_task("orphan-task", "target-agent", "prompt")

    # Setup worker parent agent
    worker_parent = AgentConfig(
        id="worker-lead",
        name="Worker Lead",
        description="",
        system_prompt="",
        role_type=AgentRole.WORKER.value
    )
    target_worker = AgentConfig(
        id="target-dev",
        name="Target Dev",
        description="",
        system_prompt="",
        role_type=AgentRole.WORKER.value
    )
    temp_db.save_agent(worker_parent)
    temp_db.save_agent(target_worker)

    worker_task = AgentRun(
        run_id="worker-task",
        agent_id="worker-lead",
        project_id=None,
        prompt="prompt",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    temp_db.save_task_run(worker_task)

    # 3. Target agent not found
    with pytest.raises(DelegationError, match="Target agent not found"):
        engine.delegate_task("worker-task", "ghost-target", "prompt")

    # 4. Unauthorized delegation (WORKER cannot delegate to another worker without allowed_child_ids)
    with pytest.raises(DelegationError, match="is not authorized to delegate"):
        engine.delegate_task("worker-task", "target-dev", "prompt")


def test_orchestration_engine_concurrency_limits(temp_db, real_event_service):
    """Test ConcurrencyLimitExceededError when max_concurrent_children is reached."""
    mgr = AgentConfig(
        id="busy-manager",
        name="Busy Manager",
        description="",
        system_prompt="",
        role_type=AgentRole.MANAGER.value,
        max_concurrent_children=2
    )
    dev = AgentConfig(
        id="worker-dev",
        name="Worker Dev",
        description="",
        system_prompt="",
        role_type=AgentRole.WORKER.value,
        parent_id="busy-manager"
    )
    temp_db.save_agent(mgr)
    temp_db.save_agent(dev)

    parent_run = AgentRun(
        run_id="parent-busy",
        agent_id="busy-manager",
        project_id=None,
        prompt="Coordinate",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    temp_db.save_task_run(parent_run)

    runtime = ClaudeCodeRuntimeAdapter()
    engine = OrchestrationEngine(
        db_manager=temp_db,
        runtime_adapter=runtime,
        event_service=real_event_service
    )

    # Delegate subtask 1 (active count = 1)
    sub1 = engine.delegate_task("parent-busy", "worker-dev", "Subtask 1")
    assert sub1 is not None

    # Delegate subtask 2 (active count = 2)
    sub2 = engine.delegate_task("parent-busy", "worker-dev", "Subtask 2")
    assert sub2 is not None

    # Third delegation should exceed limit of 2
    with pytest.raises(ConcurrencyLimitExceededError, match="maximum concurrent subtasks limit"):
        engine.delegate_task("parent-busy", "worker-dev", "Subtask 3")

    # Complete one subtask
    sub1.status = TaskStatus.COMPLETED
    temp_db.save_task_run(sub1)

    # Now active count is 1 < 2, delegating should succeed again
    sub3 = engine.delegate_task("parent-busy", "worker-dev", "Subtask 3")
    assert sub3 is not None


def test_backend_dependencies_orchestration_engine():
    """Verify backend dependency getter returns an OrchestrationEngine instance."""
    engine = get_orchestration_engine()
    assert isinstance(engine, OrchestrationEngine)
    assert engine.db_manager is not None
    assert engine.runtime_adapter is not None
    assert engine.event_service is not None
