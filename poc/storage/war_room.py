"""War Room persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


class WarRoomRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def create_war_room_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new multi-agent war room session."""
        session_id = session_data.get('id') or f"wr_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        participants = session_data.get('participant_agent_ids', [])
        part_str = json.dumps(participants) if isinstance(participants, list) else participants

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO war_room_sessions (
                    id, title, topic, project_id, moderator_agent_id, participant_agent_ids, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                session_data['title'],
                session_data['topic'],
                session_data.get('project_id'),
                session_data['moderator_agent_id'],
                part_str,
                session_data.get('status', 'GATHERING'),
                now,
                now
            ))
            conn.commit()

        return self.get_war_room_session(session_id)

    def get_war_room_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get war room session details by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM war_room_sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None
            return decode_json_columns(row, 'participant_agent_ids')

    def list_war_room_sessions(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List war room sessions."""
        query = "SELECT * FROM war_room_sessions WHERE 1=1"
        params: List[Any] = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [decode_json_columns(row, 'participant_agent_ids') for row in rows]

    def update_war_room_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update war room status or synthesized plan."""
        fields = []
        params = []
        now = datetime.now().isoformat()

        for k, v in updates.items():
            if k in ['status', 'synthesized_plan', 'topic', 'title']:
                fields.append(f"{k} = ?")
                params.append(v)
            elif k == 'participant_agent_ids':
                fields.append("participant_agent_ids = ?")
                params.append(json.dumps(v) if isinstance(v, list) else v)

        if not fields:
            return self.get_war_room_session(session_id)

        fields.append("updated_at = ?")
        params.append(now)
        params.append(session_id)

        with self._get_connection() as conn:
            conn.execute(f"UPDATE war_room_sessions SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

        return self.get_war_room_session(session_id)

    def add_war_room_message(self, msg_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a dialogue message or proposal to a war room session."""
        msg_id = msg_data.get('id') or f"wrmsg_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO war_room_messages (
                    id, session_id, agent_id, round_number, message_type, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_id,
                msg_data['session_id'],
                msg_data['agent_id'],
                msg_data.get('round_number', 1),
                msg_data.get('message_type', 'PROPOSAL'),
                msg_data['content'],
                now
            ))
            # Touch session
            conn.execute("UPDATE war_room_sessions SET updated_at = ? WHERE id = ?", (now, msg_data['session_id']))
            conn.commit()

        return {
            "id": msg_id,
            "session_id": msg_data['session_id'],
            "agent_id": msg_data['agent_id'],
            "round_number": msg_data.get('round_number', 1),
            "message_type": msg_data.get('message_type', 'PROPOSAL'),
            "content": msg_data['content'],
            "created_at": now
        }

    def get_war_room_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages in a war room session chronologically."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM war_room_messages
                WHERE session_id = ?
                ORDER BY round_number ASC, created_at ASC
            """, (session_id,)).fetchall()
            return [dict(r) for r in rows]
