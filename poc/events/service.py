"""
EventService coordinating persistent event storage and real-time distribution.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

try:
    from events.models import EventType, PlatformEvent
    from events.bus import EventBus
except ImportError:
    from poc.events.models import EventType, PlatformEvent
    from poc.events.bus import EventBus

if TYPE_CHECKING:
    from persistence import DatabaseManager


class EventService:
    """
    Coordinates event creation, persistence in SQLite with monotonic sequence numbers,
    and immediate publication to the in-memory EventBus.
    """

    def __init__(self, db_manager: "DatabaseManager", event_bus: EventBus) -> None:
        self.db_manager = db_manager
        self.event_bus = event_bus

    def emit(
        self,
        event_type: Union[EventType, str],
        payload: Dict[str, Any],
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        parent_task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source: str = "platform"
    ) -> PlatformEvent:
        """
        Constructs PlatformEvent, saves to SQLite via db_manager.save_event(),
        then publishes to event_bus.publish().
        Returns the persisted event with its monotonic sequence number.
        """
        event_type_str = event_type.value if hasattr(event_type, "value") else str(event_type)

        event = PlatformEvent(
            event_type=event_type_str,
            payload=payload if payload is not None else {},
            agent_id=agent_id,
            task_id=task_id,
            execution_id=execution_id,
            parent_task_id=parent_task_id,
            project_id=project_id,
            correlation_id=correlation_id,
            source=source
        )

        # 1. Save to SQLite database (assigns sequence_number monotonically)
        saved_event = self.db_manager.save_event(event)

        # 2. Publish to event bus for real-time consumers
        self.event_bus.publish(saved_event)

        return saved_event

    def get_events(
        self,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        after_sequence: Optional[int] = None,
        since: Optional[Union[str, datetime]] = None,
        limit: int = 100
    ) -> List[PlatformEvent]:
        """
        Query persisted events by delegating to db_manager.get_events.
        """
        return self.db_manager.get_events(
            agent_id=agent_id,
            task_id=task_id,
            project_id=project_id,
            after_sequence=after_sequence,
            since=since,
            limit=limit
        )
