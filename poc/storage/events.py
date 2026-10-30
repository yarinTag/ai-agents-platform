"""Events persistence operations; dependencies are injected callbacks."""
from datetime import datetime
from events.models import PlatformEvent
from typing import Any, List, Optional, Union
import json
import uuid


class EventsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def get_next_sequence_number(self) -> int:
        """Query SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM event_log."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COALESCE(MAX(sequence_number), 0) + 1 AS next_seq FROM event_log")
            row = cursor.fetchone()
            return int(row["next_seq"]) if row else 1

    def save_event(self, event: PlatformEvent) -> PlatformEvent:
        """
        Save an event to the persistent event log.
        If event.sequence_number <= 0, assign self.get_next_sequence_number().
        Insert row into event_log. Commit and return event.
        """
        if event.sequence_number <= 0:
            event.sequence_number = self.get_next_sequence_number()

        event_id = getattr(event, "event_id", None) or getattr(event, "id", None) or str(uuid.uuid4())
        event.event_id = event_id

        payload_str = json.dumps(event.payload) if isinstance(event.payload, (dict, list)) else (
            event.payload if isinstance(event.payload, str) else "{}"
        )
        event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        timestamp_str = event.timestamp.isoformat() if isinstance(event.timestamp, datetime) else str(event.timestamp)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO event_log (
                    id, sequence_number, event_type, agent_id, task_id, execution_id,
                    parent_task_id, project_id, correlation_id, payload, source, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.sequence_number,
                event_type_str,
                event.agent_id,
                event.task_id,
                event.execution_id,
                event.parent_task_id,
                event.project_id,
                event.correlation_id,
                payload_str,
                event.source,
                timestamp_str
            ))
            conn.commit()

        return event

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
        Query event_log with appropriate WHERE clauses, order by sequence_number ASC, limit.
        Return list of PlatformEvent.
        """
        with self._get_connection() as conn:
            query = "SELECT * FROM event_log WHERE 1=1"
            params: List[Any] = []

            if agent_id is not None:
                query += " AND agent_id = ?"
                params.append(agent_id)
            if task_id is not None:
                query += " AND task_id = ?"
                params.append(task_id)
            if project_id is not None:
                query += " AND project_id = ?"
                params.append(project_id)
            if after_sequence is not None:
                query += " AND sequence_number > ?"
                params.append(after_sequence)
            if since is not None:
                since_str = since.isoformat() if isinstance(since, datetime) else str(since)
                query += " AND timestamp >= ?"
                params.append(since_str)

            query += " ORDER BY sequence_number ASC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            events: List[PlatformEvent] = []
            for row in cursor.fetchall():
                payload = json.loads(row["payload"]) if row["payload"] else {}
                events.append(PlatformEvent(
                    event_id=row["id"],
                    sequence_number=row["sequence_number"],
                    event_type=row["event_type"],
                    agent_id=row["agent_id"],
                    task_id=row["task_id"],
                    execution_id=row["execution_id"],
                    parent_task_id=row["parent_task_id"],
                    project_id=row["project_id"],
                    correlation_id=row["correlation_id"],
                    payload=payload,
                    source=row["source"],
                    timestamp=str(row["timestamp"])
                ))
            return events
