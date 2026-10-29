"""Interactions persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


class InteractionsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def retarget_interaction(self, interaction_id: str, target_approver_id: str):
        """Change approval routing without relying on nonexistent schema columns."""
        with self._get_connection() as conn:
            conn.execute("UPDATE agent_interactions SET target_approver_id = ? WHERE id = ?",
                         (target_approver_id, interaction_id))

    def create_interaction(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new question or approval request from an agent."""
        interaction_id = interaction_data.get('id') or f"inter_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        ctx_data = interaction_data.get('context_data')
        ctx_str = json.dumps(ctx_data) if isinstance(ctx_data, (dict, list)) else ctx_data

        init_status = interaction_data.get('status', 'PENDING')
        res_resp = interaction_data.get('resolution_response')
        res_by = interaction_data.get('resolved_by')

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_interactions (
                    id, task_id, requester_agent_id, target_approver_id,
                    interaction_type, title, content, context_data,
                    status, resolution_response, resolved_by, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction_id,
                interaction_data['task_id'],
                interaction_data['requester_agent_id'],
                interaction_data['target_approver_id'],
                interaction_data.get('interaction_type', 'QUESTION'),
                interaction_data['title'],
                interaction_data['content'],
                ctx_str,
                init_status,
                res_resp,
                res_by,
                now,
                now if init_status != 'PENDING' else None
            ))
            conn.commit()

        return self.get_interaction(interaction_id)

    def get_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get an interaction by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_interactions WHERE id = ?", (interaction_id,)).fetchone()
            if not row:
                return None
            return decode_json_columns(row, 'context_data')

    def list_interactions(
        self,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        target_approver_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List interactions / pending approvals with filters."""
        query = "SELECT * FROM agent_interactions WHERE 1=1"
        params: List[Any] = []
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if agent_id and not target_approver_id:
            query += " AND (requester_agent_id = ? OR target_approver_id = ?)"
            params.extend([agent_id, agent_id])
        elif agent_id:
            query += " AND requester_agent_id = ?"
            params.append(agent_id)
        if target_approver_id and not agent_id:
            query += " AND target_approver_id = ?"
            params.append(target_approver_id)
        elif target_approver_id and agent_id:
            query += " AND target_approver_id = ?"
            params.append(target_approver_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [decode_json_columns(row, 'context_data') for row in rows]

    def resolve_interaction(
        self,
        interaction_id: str,
        resolution_response: str,
        resolved_by: str,
        decision: str = 'RESOLVED'
    ) -> Optional[Dict[str, Any]]:
        """Mark an interaction as resolved or rejected with a response."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE agent_interactions
                SET status = ?, resolution_response = ?, resolved_by = ?, resolved_at = ?
                WHERE id = ?
            """, (decision, resolution_response, resolved_by, now, interaction_id))
            conn.commit()

        return self.get_interaction(interaction_id)
