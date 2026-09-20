"""
Automated tests for Phase 3: Task Delegation, Subtasks, and Task Trees HTTP Endpoints.
ZERO MOCKS POLICY: Real SQLite database, real FastAPI client, real OrchestrationEngine.
"""

import pytest
import pytest_asyncio
import httpx
import uuid
from datetime import datetime

from backend.main import app
from backend.dependencies import (
    init_services, shutdown_services, get_db_manager, get_orchestration_engine
)
from config import AgentConfig, AgentRole, ProjectConfig
from runtime_adapter import AgentRun, TaskStatus


@pytest_asyncio.fixture(autouse=True)
async def setup_services():
    """Ensure backend services are initialized before each test."""
    await init_services()
    yield
    await shutdown_services()


@pytest.mark.asyncio
async def test_delegate_endpoint_success_and_subtasks():
    db = get_db_manager()

    mgr_id = f"mgr-{uuid.uuid4().hex[:6]}"
    worker_id = f"worker-{uuid.uuid4().hex[:6]}"

    # Save project first to satisfy foreign key
    proj = ProjectConfig(
        id="test-proj",
        name="Test Project",
        description="Testing project",
        working_directory="."
    )
    db.save_project(proj)

    # Save manager agent
    manager_agent = AgentConfig(
        id=mgr_id,
        name="Engineering Manager",
        description="Coordinates work",
        system_prompt="Manage tasks",
        role_type="MANAGER",
        max_concurrent_children=5
    )
    db.save_agent(manager_agent)

    # Save worker agent reporting to manager
    worker_agent = AgentConfig(
        id=worker_id,
        name="Backend Dev",
        description="Executes tasks",
        system_prompt="Build code",
        role_type="WORKER",
        parent_id=mgr_id
    )
    db.save_agent(worker_agent)

    # Create root parent task
    parent_run_id = f"parent-task-{uuid.uuid4().hex[:6]}"
    parent_run = AgentRun(
        run_id=parent_run_id,
        agent_id=mgr_id,
        project_id="test-proj",
        prompt="Lead project feature",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        started_at=datetime.now()
    )
    db.save_task_run(parent_run)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # 1. Delegate task
        delegate_payload = {
            "target_agent_id": worker_id,
            "subtask_prompt": "Implement API endpoint",
            "timeout_seconds": 180,
            "project_id": "test-proj"
        }
        resp = await client.post(f"/api/v1/tasks/{parent_run_id}/delegate", json=delegate_payload)
        assert resp.status_code == 201, resp.text
        subtask = resp.json()

        assert subtask["parent_task_id"] == parent_run_id
        assert subtask["root_task_id"] == parent_run_id
        assert subtask["assigned_by"] == mgr_id
        assert subtask["agent_id"] == worker_id
        assert subtask["prompt"] == "Implement API endpoint"
        subtask_run_id = subtask["run_id"]

        # 2. Get subtasks
        subtasks_resp = await client.get(f"/api/v1/tasks/{parent_run_id}/subtasks")
        assert subtasks_resp.status_code == 200
        subtasks = subtasks_resp.json()
        assert len(subtasks) == 1
        assert subtasks[0]["run_id"] == subtask_run_id
        assert subtasks[0]["parent_task_id"] == parent_run_id

        # 3. Get task tree
        tree_resp = await client.get(f"/api/v1/tasks/{parent_run_id}/tree")
        assert tree_resp.status_code == 200
        tree = tree_resp.json()
        assert tree["run_id"] == parent_run_id
        assert len(tree["children"]) == 1
        assert tree["children"][0]["run_id"] == subtask_run_id
        assert tree["children"][0]["agent_id"] == worker_id


@pytest.mark.asyncio
async def test_delegate_endpoint_concurrency_limit_429():
    db = get_db_manager()

    mgr_id = f"mgr-conc-{uuid.uuid4().hex[:6]}"
    worker_id = f"worker-conc-{uuid.uuid4().hex[:6]}"

    # Save manager with max_concurrent_children = 1
    manager_agent = AgentConfig(
        id=mgr_id,
        name="Constrained Manager",
        description="Coordinates work",
        system_prompt="Manage tasks",
        role_type="MANAGER",
        max_concurrent_children=1
    )
    db.save_agent(manager_agent)

    worker_agent = AgentConfig(
        id=worker_id,
        name="Backend Dev",
        description="Executes tasks",
        system_prompt="Build code",
        role_type="WORKER",
        parent_id=mgr_id
    )
    db.save_agent(worker_agent)

    parent_run_id = f"parent-conc-{uuid.uuid4().hex[:6]}"
    parent_run = AgentRun(
        run_id=parent_run_id,
        agent_id=mgr_id,
        project_id=None,
        prompt="Lead project",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(parent_run)

    # Insert an existing active subtask assigned by mgr_id (reaching max_concurrent_children = 1)
    existing_subtask = AgentRun(
        run_id=f"sub-active-{uuid.uuid4().hex[:6]}",
        agent_id=worker_id,
        project_id=None,
        prompt="Active subtask in progress",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        parent_task_id=parent_run_id,
        root_task_id=parent_run_id,
        assigned_by=mgr_id
    )
    db.save_task_run(existing_subtask)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Attempting to delegate another subtask hits concurrency limit -> 429
        payload = {
            "target_agent_id": worker_id,
            "subtask_prompt": "Second subtask that should be rejected"
        }
        resp = await client.post(f"/api/v1/tasks/{parent_run_id}/delegate", json=payload)
        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delegate_endpoint_unauthorized_400():
    db = get_db_manager()

    worker1_id = f"worker1-{uuid.uuid4().hex[:6]}"
    worker2_id = f"worker2-{uuid.uuid4().hex[:6]}"

    # WORKER cannot delegate to another WORKER
    w1 = AgentConfig(
        id=worker1_id,
        name="Worker 1",
        description="Worker",
        system_prompt="Worker",
        role_type="WORKER"
    )
    w2 = AgentConfig(
        id=worker2_id,
        name="Worker 2",
        description="Worker",
        system_prompt="Worker",
        role_type="WORKER"
    )
    db.save_agent(w1)
    db.save_agent(w2)

    run_id = f"task-w1-{uuid.uuid4().hex[:6]}"
    run = AgentRun(
        run_id=run_id,
        agent_id=worker1_id,
        project_id=None,
        prompt="Worker task",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    )
    db.save_task_run(run)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/tasks/{run_id}/delegate",
            json={"target_agent_id": worker2_id, "subtask_prompt": "Unauthorized"}
        )
        assert resp.status_code == 400
        assert "not authorized" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_task_tree_not_found_404():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/tasks/non-existent-task-9999/tree")
        assert resp.status_code == 404
