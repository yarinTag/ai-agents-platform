"""Chat persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


class ChatRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def save_chat_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new chat message, thought, or tool call."""
        msg_id = message_data.get('id') or f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        meta = message_data.get('metadata')
        meta_str = json.dumps(meta) if isinstance(meta, (dict, list)) else meta

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO chat_messages (
                    id, conversation_id, agent_id, task_id,
                    sender_type, message_type, content, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_id,
                message_data['conversation_id'],
                message_data['agent_id'],
                message_data.get('task_id'),
                message_data.get('sender_type', 'USER'),
                message_data.get('message_type', 'CHAT'),
                message_data['content'],
                meta_str,
                message_data.get('created_at') or now
            ))
            # Also touch updated_at on the conversation
            conn.execute(
                "UPDATE agent_conversations SET updated_at = ? WHERE id = ?",
                (now, message_data['conversation_id'])
            )
            conn.commit()

            return {
                "id": msg_id,
                "conversation_id": message_data['conversation_id'],
                "agent_id": message_data['agent_id'],
                "task_id": message_data.get('task_id'),
                "sender_type": message_data.get('sender_type', 'USER'),
                "message_type": message_data.get('message_type', 'CHAT'),
                "content": message_data['content'],
                "metadata": meta,
                "created_at": now
            }

    def get_chat_history(self, agent_id: str, limit: int = 100, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent chat history for an agent (optionally filtered by conversation_id)."""
        with self._get_connection() as conn:
            if conversation_id:
                rows = conn.execute("""
                    SELECT * FROM (
                        SELECT * FROM chat_messages
                        WHERE agent_id = ? AND conversation_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    ) sub
                    ORDER BY created_at ASC
                """, (agent_id, conversation_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM (
                        SELECT * FROM chat_messages
                        WHERE agent_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    ) sub
                    ORDER BY created_at ASC
                """, (agent_id, limit)).fetchall()

            return [decode_json_columns(row, 'metadata') for row in rows]

    def has_chat_message_for_task(self, agent_id: str, task_id: str, sender_type: str, content: Optional[str] = None) -> bool:
        """Check if a chat message already exists for a specific task and sender type, or with identical prompt."""
        with self._get_connection() as conn:
            if content:
                row = conn.execute("""
                    SELECT 1 FROM chat_messages
                    WHERE agent_id = ? 
                      AND (task_id = ? OR json_extract(metadata, '$.task_id') = ?)
                      AND content = ?
                      AND sender_type = ?
                    LIMIT 1
                """, (agent_id, task_id, task_id, content, sender_type)).fetchone()
            else:
                row = conn.execute("""
                    SELECT 1 FROM chat_messages
                    WHERE agent_id = ? 
                      AND (task_id = ? OR json_extract(metadata, '$.task_id') = ?)
                      AND sender_type = ?
                    LIMIT 1
                """, (agent_id, task_id, task_id, sender_type)).fetchone()
            return row is not None

    def clear_chat_history(self, agent_id: str):
        """Clear all messages and start fresh for an agent."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_conversations WHERE agent_id = ?", (agent_id,))
            conn.commit()
