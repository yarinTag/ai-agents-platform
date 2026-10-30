"""Messages persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from .records import AgentMessage
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json
import uuid


class MessagesRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def save_agent_message(self, message: Union[AgentMessage, Dict[str, Any]]) -> AgentMessage:
        """Save a new or updated internal agent message."""
        if isinstance(message, dict):
            msg = AgentMessage.from_dict(message)
        else:
            msg = message

        if not msg.id:
            msg.id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        if not msg.created_at:
            msg.created_at = now

        meta_str = json.dumps(msg.metadata) if msg.metadata else None
        channel_key = msg.channel_key
        if not channel_key and msg.task_id:
            mtype = getattr(msg, "message_type", "QUESTION").upper()
            if mtype == "QUESTION":
                channel_key = f"channel:{msg.to_agent_id}:{msg.from_agent_id}:{msg.task_id}"
            else:
                channel_key = f"channel:{msg.from_agent_id}:{msg.to_agent_id}:{msg.task_id}"

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_messages (
                    id, from_agent_id, to_agent_id, task_id, run_id, parent_message_id,
                    message_type, content, status, metadata, channel_key, created_at, responded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    responded_at=excluded.responded_at,
                    metadata=excluded.metadata,
                    channel_key=excluded.channel_key
            """, (
                msg.id,
                msg.from_agent_id,
                msg.to_agent_id,
                msg.task_id,
                msg.run_id,
                msg.parent_message_id,
                msg.message_type,
                msg.content,
                msg.status,
                meta_str,
                channel_key,
                msg.created_at,
                msg.responded_at
            ))
            conn.commit()

        return self.get_agent_message(msg.id)

    def get_agent_message(self, message_id: str) -> Optional[AgentMessage]:
        """Retrieve an agent message by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_messages WHERE id = ?", (message_id,)).fetchone()
            if not row:
                return None
            return AgentMessage.from_dict(decode_json_columns(row, 'metadata'))

    def list_agent_messages(
        self,
        from_agent_id: Optional[str] = None,
        to_agent_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        channel_key: Optional[str] = None,
        limit: int = 100
    ) -> List[AgentMessage]:
        """List internal messages between agents with optional filters."""
        query = "SELECT * FROM agent_messages WHERE 1=1"
        params: List[Any] = []
        if channel_key:
            query += " AND channel_key = ?"
            params.append(channel_key)
        if agent_id:
            query += " AND (from_agent_id = ? OR to_agent_id = ?)"
            params.extend([agent_id, agent_id])
        else:
            if from_agent_id:
                query += " AND from_agent_id = ?"
                params.append(from_agent_id)
            if to_agent_id:
                query += " AND to_agent_id = ?"
                params.append(to_agent_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if parent_message_id:
            query += " AND parent_message_id = ?"
            params.append(parent_message_id)

        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [AgentMessage.from_dict(decode_json_columns(row, 'metadata')) for row in rows]

    def update_agent_message(
        self,
        message_id: str,
        status: Optional[str] = None,
        responded_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """Update an agent message status and response time."""
        fields = []
        params = []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if responded_at is not None:
            fields.append("responded_at = ?")
            params.append(responded_at)
        if metadata is not None:
            fields.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not fields:
            return self.get_agent_message(message_id)

        params.append(message_id)
        with self._get_connection() as conn:
            conn.execute(f"UPDATE agent_messages SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

        return self.get_agent_message(message_id)
