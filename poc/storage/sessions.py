"""Sessions persistence operations; dependencies are injected callbacks."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class SessionsRepository:
    def __init__(self, connection_factory, get_agent):
        self._get_connection = connection_factory
        self.get_agent = get_agent

    def create_agent_session(
        self,
        agent_id: str,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        close_existing: bool = True,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new session for an agent.
        If close_existing is True, marks all previous active sessions as CLOSED.
        Links the supervisor's active session ID so child-parent A2A context is retained.
        """
        with self._get_connection() as conn:
            now = datetime.now().isoformat()
            if close_existing:
                conn.execute(
                    "UPDATE agent_conversations SET status = 'CLOSED', updated_at = ? WHERE agent_id = ? AND status = 'ACTIVE'",
                    (now, agent_id)
                )

            # Determine supervisor session from agent hierarchy
            supervisor_session_id = None
            try:
                agent = self.get_agent(agent_id)
                if agent and getattr(agent, "parent_id", None):
                    sup_row = conn.execute(
                        "SELECT id, claude_session_id FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                        (agent.parent_id,)
                    ).fetchone()
                    if sup_row:
                        supervisor_session_id = sup_row["id"]
                    else:
                        sup_any = conn.execute(
                            "SELECT id FROM agent_conversations WHERE agent_id = ? ORDER BY updated_at DESC LIMIT 1",
                            (agent.parent_id,)
                        ).fetchone()
                        if sup_any:
                            supervisor_session_id = sup_any["id"]
            except Exception:
                pass

            conv_id = f"conv_{uuid.uuid4().hex[:12]}"
            claude_session_id = f"sess_{agent_id}_{uuid.uuid4().hex[:8]}"
            count_row = conn.execute("SELECT COUNT(*) FROM agent_conversations WHERE agent_id = ?", (agent_id,)).fetchone()
            seq_num = (count_row[0] + 1) if count_row else 1
            session_title = title or f"Session {seq_num}"
            assigned_task_id = task_id or f"task_{conv_id.replace('conv_', '')}"

            conn.execute("""
                INSERT INTO agent_conversations (
                    id, agent_id, project_id, title, claude_session_id, runtime_session_id, task_id, supervisor_session_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """, (conv_id, agent_id, project_id, session_title, claude_session_id, claude_session_id, assigned_task_id, supervisor_session_id, now, now))
            conn.commit()

            return {
                "id": conv_id,
                "agent_id": agent_id,
                "project_id": project_id,
                "title": session_title,
                "claude_session_id": claude_session_id,
                "runtime_session_id": claude_session_id,
                "task_id": assigned_task_id,
                "supervisor_session_id": supervisor_session_id,
                "status": "ACTIVE",
                "created_at": now,
                "updated_at": now
            }

    def list_agent_sessions(self, agent_id: str) -> List[Dict[str, Any]]:
        """List all chat sessions for an agent, latest first, enriched with supervisor info."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_conversations WHERE agent_id = ? ORDER BY created_at DESC",
                (agent_id,)
            ).fetchall()
            sessions = [dict(r) for r in rows]

            # Resolve supervisor info if parent agent exists
            parent_id = None
            parent_name = None
            parent_active_session_id = None
            parent_active_session_title = None
            try:
                agent = self.get_agent(agent_id)
                if agent and getattr(agent, "parent_id", None):
                    parent_id = agent.parent_id
                    parent_agent = self.get_agent(parent_id)
                    parent_name = parent_agent.name if parent_agent else parent_id
                    sup_active = conn.execute(
                        "SELECT id, title FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                        (parent_id,)
                    ).fetchone()
                    if sup_active:
                        parent_active_session_id = sup_active["id"]
                        parent_active_session_title = sup_active["title"]
            except Exception:
                pass

            for s in sessions:
                s["supervisor_agent_id"] = parent_id
                s["supervisor_agent_name"] = parent_name
                if s.get("supervisor_session_id"):
                    try:
                        sup_row = conn.execute("SELECT title FROM agent_conversations WHERE id = ?", (s["supervisor_session_id"],)).fetchone()
                        s["supervisor_session_title"] = sup_row["title"] if sup_row else (parent_active_session_title or "Supervisor Session")
                    except Exception:
                        s["supervisor_session_title"] = parent_active_session_title or "Supervisor Session"
                else:
                    s["supervisor_session_id"] = parent_active_session_id
                    s["supervisor_session_title"] = parent_active_session_title

            return sessions

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific conversation/session by ID, enriched with supervisor info."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE id = ?",
                (conversation_id,)
            ).fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                agent = self.get_agent(res["agent_id"])
                if agent and getattr(agent, "parent_id", None):
                    res["supervisor_agent_id"] = agent.parent_id
                    parent_agent = self.get_agent(agent.parent_id)
                    res["supervisor_agent_name"] = parent_agent.name if parent_agent else agent.parent_id
                    sup_active = conn.execute(
                        "SELECT id, title FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                        (agent.parent_id,)
                    ).fetchone()
                    if sup_active:
                        if not res.get("supervisor_session_id"):
                            res["supervisor_session_id"] = sup_active["id"]
                        res["supervisor_session_title"] = sup_active["title"]
            except Exception:
                pass
            return res

    def activate_agent_session(self, agent_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Set a specific session as ACTIVE, closing any other active sessions."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE agent_conversations SET status = 'CLOSED', updated_at = ? WHERE agent_id = ?",
                (now, agent_id)
            )
            conn.execute(
                "UPDATE agent_conversations SET status = 'ACTIVE', updated_at = ? WHERE id = ? AND agent_id = ?",
                (now, conversation_id, agent_id)
            )
            conn.commit()
            return self.get_conversation(conversation_id)

    def close_agent_session(self, conversation_id: str) -> bool:
        """Close an active session."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE agent_conversations SET status = 'CLOSED', updated_at = ? WHERE id = ?",
                (now, conversation_id)
            )
            conn.commit()
            return True

    def get_or_create_channel(
        self,
        manager_id: str,
        worker_id: str,
        task_id: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get or create a dedicated, isolated communication channel between a manager and a worker
        for a specific task, preventing cross-talk between sibling subagents.
        Channel key format: channel:{manager_id}:{worker_id}:{task_id}
        """
        channel_key = f"channel:{manager_id}:{worker_id}:{task_id}"
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE channel_key = ? LIMIT 1",
                (channel_key,)
            ).fetchone()
            if row:
                return dict(row)

            conv_id = f"conv_chan_{uuid.uuid4().hex[:12]}"
            now = datetime.now().isoformat()
            title = f"Channel: {manager_id} <-> {worker_id} ({task_id})"

            conn.execute("""
                INSERT INTO agent_conversations (
                    id, agent_id, project_id, title, task_id, status, channel_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
            """, (conv_id, worker_id, project_id, title, task_id, channel_key, now, now))
            conn.commit()

            return self.get_conversation(conv_id)

    def get_or_create_conversation(self, agent_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the active conversation for an agent, or create a new one."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                (agent_id,)
            ).fetchone()

            if row:
                res = dict(row)
                if not res.get("task_id"):
                    assigned_task_id = f"task_{res['id'].replace('conv_', '')}"
                    conn.execute("UPDATE agent_conversations SET task_id = ? WHERE id = ?", (assigned_task_id, res["id"]))
                    conn.commit()
                    res["task_id"] = assigned_task_id
                return res

            # If no ACTIVE session, try latest existing before creating fresh
            any_row = conn.execute(
                "SELECT * FROM agent_conversations WHERE agent_id = ? ORDER BY updated_at DESC LIMIT 1",
                (agent_id,)
            ).fetchone()
            if any_row:
                now_str = datetime.now().isoformat()
                assigned_task_id = any_row["task_id"] or f"task_{any_row['id'].replace('conv_', '')}"
                conn.execute(
                    "UPDATE agent_conversations SET status = 'ACTIVE', task_id = ?, updated_at = ? WHERE id = ?",
                    (assigned_task_id, now_str, any_row["id"])
                )
                conn.commit()
                return self.get_conversation(any_row["id"])

        return self.create_agent_session(agent_id, project_id=project_id, close_existing=False)

    def update_conversation_session(self, conversation_id: str, claude_session_id: str, task_id: Optional[str] = None):
        """Associate a runtime/CLI session ID and optional task_id with the conversation."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            if task_id:
                conn.execute("""
                    UPDATE agent_conversations
                    SET claude_session_id = ?, runtime_session_id = ?, task_id = ?, updated_at = ?
                    WHERE id = ?
                """, (claude_session_id, claude_session_id, task_id, now, conversation_id))
            else:
                conn.execute("""
                    UPDATE agent_conversations
                    SET claude_session_id = ?, runtime_session_id = ?, updated_at = ?
                    WHERE id = ?
                """, (claude_session_id, claude_session_id, now, conversation_id))
            conn.commit()
