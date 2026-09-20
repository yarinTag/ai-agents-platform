"""
Tests for Global SSE Stream endpoint and API event emissions.
ZERO MOCKS: All tests use real FastAPI app, real EventBus, real EventService, and real SQLite.
"""

import asyncio
import json
import pytest
import pytest_asyncio
import httpx
from datetime import datetime, timedelta

from backend.main import app
from backend.dependencies import (
    init_services, shutdown_services, get_db_manager,
    get_event_bus, get_event_service, get_runtime_adapter
)
from runtime.claude_adapter import ClaudeCodeAdapter
from events import EventType, PlatformEvent, EventBus, EventService


@pytest_asyncio.fixture(autouse=True)
async def setup_services():
    """Ensure backend services are initialized before each test."""
    await init_services()
    yield
    await shutdown_services()


def test_dependency_singletons():
    """Verify EventBus, EventService, and ClaudeCodeAdapter singletons in dependencies."""
    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert isinstance(bus1, EventBus)
    assert bus1 is bus2

    service1 = get_event_service()
    service2 = get_event_service()
    assert isinstance(service1, EventService)
    assert service1 is service2
    assert service1.event_bus is bus1

    adapter = get_runtime_adapter()
    assert isinstance(adapter, ClaudeCodeAdapter)
    assert get_runtime_adapter() is adapter


@pytest.mark.asyncio
async def test_sse_stream_headers_and_historical_replay():
    """Verify GET /api/v1/events/stream returns correct headers and replays historical events."""
    event_service = get_event_service()

    # Emit historical events
    e1 = event_service.emit(
        event_type=EventType.AGENT_CREATED,
        payload={"agent_name": "Test Agent A"},
        agent_id="agent-sse-1"
    )
    e2 = event_service.emit(
        event_type=EventType.TASK_CREATED,
        payload={"task_name": "Task 1"},
        agent_id="agent-sse-1",
        task_id="task-sse-1"
    )
    e3 = event_service.emit(
        event_type=EventType.TASK_STARTED,
        payload={"task_name": "Task 2"},
        agent_id="agent-sse-2",
        task_id="task-sse-2"
    )

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Replay with after_sequence filter (live=false to cleanly test replay stream)
        async with client.stream(
            "GET",
            f"/api/v1/events/stream?after_sequence={e1.sequence_number}&agent_id=agent-sse-1&live=false"
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"
            assert response.headers["x-accel-buffering"] == "no"

            # Read chunks of historical replay
            combined = ""
            async for line in response.aiter_lines():
                combined += line + "\n"
                if "task-sse-1" in combined:
                    break

            assert f"event: {EventType.TASK_CREATED.value}" in combined
            assert "task-sse-1" in combined


@pytest.mark.asyncio
async def test_sse_stream_live_events_and_disconnect():
    """Verify live events are streamed through SSE and subscriber queue cleans up on disconnect."""
    event_bus = get_event_bus()
    event_service = get_event_service()
    initial_sub_count = event_bus.subscriber_count

    async def emit_later():
        await asyncio.sleep(0.05)
        event_service.emit(
            event_type=EventType.EXECUTION_OUTPUT,
            payload={"output": "Processing live task..."},
            agent_id="live-agent-1",
            task_id="live-task-1"
        )

    emit_task = asyncio.create_task(emit_later())

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        async with client.stream(
            "GET",
            "/api/v1/events/stream?agent_id=live-agent-1&limit=1"
        ) as response:
            assert response.status_code == 200
            # Read the live event from the stream
            combined = ""
            async for line in response.aiter_lines():
                combined += line + "\n"
                if "Processing live task..." in combined:
                    break

            assert f"event: {EventType.EXECUTION_OUTPUT.value}" in combined
            assert "Processing live task..." in combined

    await emit_task
    await asyncio.sleep(0.05)
    assert event_bus.subscriber_count == initial_sub_count


@pytest.mark.asyncio
async def test_agents_api_emits_events():
    """Verify create_agent, update_agent, and delete_agent emit typed events."""
    event_bus = get_event_bus()
    queue, unsubscribe = event_bus.subscribe()

    try:
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            agent_payload = {
                "name": "Event Emission Test Agent",
                "description": "Tests agent events",
                "system_prompt": "You are a test agent.",
                "skills": ["read"],
                "model": "sonnet",
                "effort": "low",
                "max_tokens": 2048,
                "temperature": 0.5,
                "department": "Engineering"
            }

            # 1. Create Agent -> AGENT_CREATED
            resp = await client.post("/api/v1/agents/", json=agent_payload)
            assert resp.status_code == 201
            agent_id = resp.json()["id"]

            created_ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert created_ev.event_type == EventType.AGENT_CREATED.value
            assert created_ev.agent_id == agent_id
            assert created_ev.payload["name"] == "Event Emission Test Agent"

            # 2. Update Agent -> AGENT_UPDATED
            update_payload = {"description": "Updated description for events test"}
            resp = await client.put(f"/api/v1/agents/{agent_id}", json=update_payload)
            assert resp.status_code == 200

            updated_ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert updated_ev.event_type == EventType.AGENT_UPDATED.value
            assert updated_ev.agent_id == agent_id
            assert updated_ev.payload["description"] == "Updated description for events test"

            # 3. Delete Agent -> AGENT_DELETED
            resp = await client.delete(f"/api/v1/agents/{agent_id}")
            assert resp.status_code == 204

            deleted_ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert deleted_ev.event_type == EventType.AGENT_DELETED.value
            assert deleted_ev.agent_id == agent_id
            assert deleted_ev.payload["deleted"] is True

    finally:
        unsubscribe()


@pytest.mark.asyncio
async def test_tasks_api_emits_events():
    """Verify create_task emits TASK_CREATED and TASK_STARTED events."""
    event_bus = get_event_bus()
    queue, unsubscribe = event_bus.subscribe()

    try:
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            # First create an agent to assign the task to
            agent_payload = {
                "name": "Task Event Agent",
                "description": "Agent for task event testing",
                "system_prompt": "You are a test agent.",
                "skills": []
            }
            resp = await client.post("/api/v1/agents/", json=agent_payload)
            assert resp.status_code == 201
            agent_id = resp.json()["id"]

            # Drain the agent.created event
            await asyncio.wait_for(queue.get(), timeout=2.0)

            # Create Task -> TASK_CREATED and TASK_STARTED
            task_payload = {
                "agent_id": agent_id,
                "prompt": "Run automated test task"
            }
            resp = await client.post("/api/v1/tasks/", json=task_payload)
            assert resp.status_code == 201
            run_id = resp.json()["id"]

            # Should receive TASK_CREATED then TASK_STARTED
            ev1 = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert ev1.event_type == EventType.TASK_CREATED.value
            assert ev1.agent_id == agent_id
            assert ev1.task_id == run_id

            ev2 = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert ev2.event_type == EventType.TASK_STARTED.value
            assert ev2.agent_id == agent_id
            assert ev2.task_id == run_id

            # Clean up
            await client.delete(f"/api/v1/agents/{agent_id}")
    finally:
        unsubscribe()
