"""Memory persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


class MemoryRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def create_project_memory(self, memory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new knowledge insight, ADR, or convention to the project memory."""
        mem_id = memory_data.get('id') or f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        tags = memory_data.get('tags')
        tags_str = json.dumps(tags) if isinstance(tags, (list, dict)) else tags

        source_task_id = memory_data.get('source_task_id')
        source_run_id = memory_data.get('source_run_id')
        confidence = memory_data.get('confidence', 1.0)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO project_memories (
                    id, project_id, category, title, content, tags, author_agent_id,
                    source_task_id, source_run_id, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id,
                memory_data['project_id'],
                memory_data.get('category', 'INSIGHT'),
                memory_data['title'],
                memory_data['content'],
                tags_str,
                memory_data.get('author_agent_id'),
                source_task_id,
                source_run_id,
                confidence,
                now,
                now
            ))
            conn.commit()


        return self.get_project_memory(mem_id)

    def get_project_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory item by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM project_memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return None
            return decode_json_columns(row, 'tags')

    def list_project_memories(
        self,
        project_id: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List shared memories for a project."""
        query = "SELECT * FROM project_memories WHERE project_id = ?"
        params: List[Any] = [project_id]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY updated_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [decode_json_columns(row, 'tags') for row in rows]

    def delete_project_memory(self, memory_id: str) -> bool:
        """Delete a shared memory item."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cur.rowcount > 0
