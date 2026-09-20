"""
Tests for the Persistent Event Log and Event Bus.
ZERO MOCKS: All tests use real SQLite databases and real asyncio queues.
"""

import asyncio
from datetime import datetime, timedelta
import pytest
from pathlib import Path

from events import EventType, PlatformEvent, EventBus, EventService
from persistence import DatabaseManager


@pytest.fixture
def temp_db(tmp_path) -> DatabaseManager:
    """Provides a fresh real DatabaseManager instance in an isolated temporary directory."""
    db_file = tmp_path / "test_events.db"
    return DatabaseManager(str(db_file))


def test_events_exports():
    """Verify all required classes are exported from the events package."""
    assert EventType is not None
    assert PlatformEvent is not None
    assert EventBus is not None
    assert EventService is not None


def test_database_manager_sequence_number(temp_db: DatabaseManager):
    """Verify monotonic sequence number generation on real SQLite table."""
    # Empty table starts sequence at 1
    assert temp_db.get_next_sequence_number() == 1

    event1 = PlatformEvent(
        event_type=EventType.AGENT_CREATED.value,
        payload={"name": "Architect"},
        agent_id="agent-001"
    )
    saved1 = temp_db.save_event(event1)
    assert saved1.sequence_number == 1
    assert temp_db.get_next_sequence_number() == 2

    event2 = PlatformEvent(
        event_type=EventType.TASK_CREATED.value,
        payload={"title": "Design Database"},
        task_id="task-100"
    )
    saved2 = temp_db.save_event(event2)
    assert saved2.sequence_number == 2
    assert temp_db.get_next_sequence_number() == 3


def test_database_manager_save_and_get_events(temp_db: DatabaseManager):
    """Verify event persistence and querying with various filters against real SQLite."""
    t0 = datetime.now() - timedelta(minutes=5)
    t1 = datetime.now()

    # Save 4 distinct events
    e1 = temp_db.save_event(PlatformEvent(
        event_type=EventType.AGENT_CREATED,
        payload={"role": "Lead"},
        agent_id="agent-1",
        project_id="proj-A",
        timestamp=t0.isoformat()
    ))
    e2 = temp_db.save_event(PlatformEvent(
        event_type=EventType.TASK_CREATED,
        payload={"desc": "Task 1"},
        agent_id="agent-1",
        task_id="task-1",
        project_id="proj-A",
        timestamp=t1.isoformat()
    ))
    e3 = temp_db.save_event(PlatformEvent(
        event_type=EventType.EXECUTION_STARTED,
        payload={"step": 1},
        agent_id="agent-2",
        task_id="task-2",
        project_id="proj-B",
        timestamp=t1.isoformat()
    ))
    e4 = temp_db.save_event(PlatformEvent(
        event_type=EventType.TASK_COMPLETED,
        payload={"output": "Done"},
        agent_id="agent-1",
        task_id="task-1",
        project_id="proj-A",
        timestamp=t1.isoformat()
    ))

    # All events ordered by sequence
    all_events = temp_db.get_events()
    assert len(all_events) == 4
    assert [ev.sequence_number for ev in all_events] == [1, 2, 3, 4]
    assert all_events[0].payload == {"role": "Lead"}
    assert all_events[0].event_id == e1.event_id

    # Filter by agent_id
    agent1_events = temp_db.get_events(agent_id="agent-1")
    assert len(agent1_events) == 3
    assert all(ev.agent_id == "agent-1" for ev in agent1_events)

    # Filter by task_id
    task1_events = temp_db.get_events(task_id="task-1")
    assert len(task1_events) == 2
    assert [ev.sequence_number for ev in task1_events] == [2, 4]

    # Filter by project_id
    proj_b_events = temp_db.get_events(project_id="proj-B")
    assert len(proj_b_events) == 1
    assert proj_b_events[0].task_id == "task-2"

    # Filter by after_sequence
    after_seq_events = temp_db.get_events(after_sequence=2)
    assert len(after_seq_events) == 2
    assert [ev.sequence_number for ev in after_seq_events] == [3, 4]

    # Filter by limit
    limited_events = temp_db.get_events(limit=2)
    assert len(limited_events) == 2
    assert [ev.sequence_number for ev in limited_events] == [1, 2]

    # Filter by since
    since_events = temp_db.get_events(since=t1.isoformat())
    assert len(since_events) == 3
    assert [ev.sequence_number for ev in since_events] == [2, 3, 4]


def test_event_bus_subscription_and_filtering():
    """Verify EventBus delivery, filtering, subscriber counting, and unsubscription."""
    bus = EventBus()
    assert bus.subscriber_count == 0

    # Subscriber 1: all events
    q_all, unsub_all = bus.subscribe()
    assert bus.subscriber_count == 1

    # Subscriber 2: only task completed events
    q_completed, unsub_completed = bus.subscribe(
        filter_fn=lambda e: e.event_type == EventType.TASK_COMPLETED.value
    )
    assert bus.subscriber_count == 2

    # Publish agent event
    ev1 = PlatformEvent(event_type=EventType.AGENT_CREATED.value, payload={})
    bus.publish(ev1)

    assert q_all.qsize() == 1
    assert q_completed.qsize() == 0

    # Publish completed event
    ev2 = PlatformEvent(event_type=EventType.TASK_COMPLETED.value, payload={})
    bus.publish(ev2)

    assert q_all.qsize() == 2
    assert q_completed.qsize() == 1

    # Verify event delivery order
    recv1 = q_all.get_nowait()
    recv2 = q_all.get_nowait()
    assert recv1.event_type == EventType.AGENT_CREATED.value
    assert recv2.event_type == EventType.TASK_COMPLETED.value

    comp_recv = q_completed.get_nowait()
    assert comp_recv.event_type == EventType.TASK_COMPLETED.value

    # Unsubscribe
    unsub_completed()
    assert bus.subscriber_count == 1

    # Publish another completed event
    ev3 = PlatformEvent(event_type=EventType.TASK_COMPLETED.value, payload={})
    bus.publish(ev3)

    assert q_all.qsize() == 1
    assert q_completed.qsize() == 0  # Unsubscribed, so not received

    unsub_all()
    assert bus.subscriber_count == 0


def test_event_bus_queue_drop_protection():
    """Verify queue drop protection when a subscriber queue reaches capacity."""
    # Initialize bus with small default queue size
    bus = EventBus(default_queue_size=3)
    queue, unsubscribe = bus.subscribe()

    # Publish 3 events to fill queue
    for i in range(1, 4):
        bus.publish(PlatformEvent(
            event_type="test.event",
            payload={"index": i},
            sequence_number=i
        ))

    assert queue.qsize() == 3

    # Publish 4th event: should drop oldest (seq=1) and retain seq=2,3,4
    bus.publish(PlatformEvent(
        event_type="test.event",
        payload={"index": 4},
        sequence_number=4
    ))
    assert queue.qsize() == 3

    items = [queue.get_nowait().sequence_number for _ in range(3)]
    assert items == [2, 3, 4], "Oldest item (1) should have been dropped to accommodate newest item (4)"

    unsubscribe()


def test_event_service_coordination(temp_db: DatabaseManager):
    """Verify EventService persists events to SQLite and publishes to EventBus simultaneously with ZERO MOCKS."""
    bus = EventBus()
    service = EventService(db_manager=temp_db, event_bus=bus)

    # Subscribe to the event bus
    queue, unsubscribe = bus.subscribe()

    # Emit event via service
    event = service.emit(
        event_type=EventType.TASK_STARTED,
        payload={"command": "npm test"},
        agent_id="test-agent",
        task_id="task-42",
        execution_id="exec-101",
        parent_task_id="task-parent-1",
        project_id="proj-alpha",
        correlation_id="corr-999",
        source="orchestrator"
    )

    # Check returned PlatformEvent
    assert event.sequence_number == 1
    assert event.event_type == EventType.TASK_STARTED.value
    assert event.agent_id == "test-agent"
    assert event.task_id == "task-42"
    assert event.execution_id == "exec-101"
    assert event.parent_task_id == "task-parent-1"
    assert event.project_id == "proj-alpha"
    assert event.correlation_id == "corr-999"
    assert event.source == "orchestrator"

    # Verify event was published and received on the EventBus queue
    assert queue.qsize() == 1
    bus_event = queue.get_nowait()
    assert bus_event.event_id == event.event_id
    assert bus_event.sequence_number == 1
    assert bus_event.payload == {"command": "npm test"}

    # Verify event was persisted in the SQLite database
    persisted_events = service.get_events(task_id="task-42")
    assert len(persisted_events) == 1
    assert persisted_events[0].event_id == event.event_id
    assert persisted_events[0].sequence_number == 1
    assert persisted_events[0].correlation_id == "corr-999"

    # Emit a second event
    event2 = service.emit(
        event_type=EventType.TASK_COMPLETED,
        payload={"exit_code": 0},
        agent_id="test-agent",
        task_id="task-42"
    )
    assert event2.sequence_number == 2
    assert queue.qsize() == 1

    all_task_events = service.get_events(agent_id="test-agent")
    assert len(all_task_events) == 2
    assert [e.sequence_number for e in all_task_events] == [1, 2]

    unsubscribe()
