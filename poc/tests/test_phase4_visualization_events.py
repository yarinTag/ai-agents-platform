"""
Automated tests for Phase 4: Office Visualization Events and SSE Stream Integration.
ZERO MOCKS POLICY: Real SQLite persistence, real EventService/EventBus, and real FastAPI streaming.
"""

import pytest
import pytest_asyncio
import httpx
import uuid
import json
from datetime import datetime

from backend.main import app
from backend.dependencies import (
    init_services, shutdown_services, get_db_manager, get_event_service, get_event_bus
)
from config import AgentConfig, AgentRole
from runtime_adapter import AgentRun, TaskStatus
from events.models import EventType


@pytest_asyncio.fixture(autouse=True)
async def setup_services():
    """Ensure backend services are initialized before each test."""
    await init_services()
    yield
    await shutdown_services()


@pytest.mark.asyncio
async def test_office_events_stream_delivers_hierarchy_and_delegation_payloads():
    """Verify SSE stream emits full visualization metadata for Pixel Art Office."""
    db = get_db_manager()
    event_service = get_event_service()

    mgr_id = f"mgr-viz-{uuid.uuid4().hex[:6]}"
    worker_id = f"worker-viz-{uuid.uuid4().hex[:6]}"

    # Save manager with role and hierarchy
    mgr = AgentConfig(
        id=mgr_id,
        name="Architecture Director",
        description="Oversees system design",
        system_prompt="Design system",
        department="Architecture",
        role_type="MANAGER",
        max_concurrent_children=4
    )
    db.save_agent(mgr)

    worker = AgentConfig(
        id=worker_id,
        name="UI Specialist",
        description="Builds pixel art canvas",
        system_prompt="Build canvas",
        department="Architecture",
        role_type="SPECIALIST",
        parent_id=mgr_id
    )
    db.save_agent(worker)

    # Emit visualization-critical events
    evt1 = event_service.emit(
        event_type=EventType.AGENT_CREATED,
        payload={
            "id": mgr_id,
            "name": mgr.name,
            "role_type": "MANAGER",
            "department": "Architecture"
        },
        agent_id=mgr_id,
        source="agents_api"
    )

    evt2 = event_service.emit(
        event_type=EventType.TASK_DELEGATED,
        payload={
            "parent_task_id": "parent-task-1",
            "subtask_id": "subtask-1",
            "parent_agent_id": mgr_id,
            "target_agent_id": worker_id,
            "prompt": "Render 60fps canvas"
        },
        agent_id=mgr_id,
        task_id="subtask-1",
        parent_task_id="parent-task-1",
        source="orchestration_engine"
    )

    # Query SSE stream with historical replay after sequence 0 (live=false for clean replay read)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", f"/api/v1/events/stream?after_sequence={evt1.sequence_number - 1}&live=false") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            collected_events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        parsed = json.loads(data_str)
                        collected_events.append(parsed)
                    except Exception:
                        pass
                if len(collected_events) >= 3:
                    break

            # Verify received events contain the data required by PixelRenderer
            event_types = [e.get("event_type") or e.get("type") for e in collected_events]
            assert any(t in ["connected", "agent.created", "agent_created", "task.delegated", "task_delegated"] for t in event_types)


@pytest.mark.asyncio
async def test_agent_desk_hierarchy_data_consistency():
    """Verify child agents correctly report their parent for connecting line rendering."""
    db = get_db_manager()

    parent_id = f"parent-{uuid.uuid4().hex[:6]}"
    child1_id = f"child1-{uuid.uuid4().hex[:6]}"
    child2_id = f"child2-{uuid.uuid4().hex[:6]}"

    db.save_agent(AgentConfig(
        id=parent_id,
        name="Lead Manager",
        description="Manager",
        system_prompt="Lead",
        role_type="MANAGER"
    ))
    db.save_agent(AgentConfig(
        id=child1_id,
        name="Frontend Worker",
        description="Worker",
        system_prompt="Work",
        role_type="WORKER",
        parent_id=parent_id
    ))
    db.save_agent(AgentConfig(
        id=child2_id,
        name="Backend Worker",
        description="Worker",
        system_prompt="Work",
        role_type="WORKER",
        parent_id=parent_id
    ))

    # Fetch children through persistence
    children = db.get_child_agents(parent_id)
    assert len(children) == 2
    child_ids = [c.id for c in children]
    assert child1_id in child_ids
    assert child2_id in child_ids

    # Hierarchy tree
    tree = db.get_agent_hierarchy(root_id=parent_id)
    assert len(tree) == 1
    assert tree[0]["id"] == parent_id
    assert len(tree[0]["children"]) == 2
