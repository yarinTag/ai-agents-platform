"""Tasks persistence operations; dependencies are injected callbacks."""
from datetime import datetime
from runtime.models import AgentRun, TaskStatus
from typing import Any, Dict, List, Optional
import json
import sqlite3


class TasksRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def claim_waiting_parent(self, parent_task_id: str) -> bool:
        """Atomically claim one waiting parent for completion propagation."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE task_runs SET status = 'running' WHERE run_id = ? AND status = 'waiting_for_children'",
                (parent_task_id,),
            )
            return cursor.rowcount > 0

    def _row_to_task_run(self, row: sqlite3.Row) -> AgentRun:
        """Convert a database row to an AgentRun object."""
        keys = row.keys() if hasattr(row, "keys") else []
        deps_val = row['dependencies'] if 'dependencies' in keys else None
        if deps_val:
            try:
                deps = json.loads(deps_val) if isinstance(deps_val, str) else list(deps_val)
            except Exception:
                deps = []
        else:
            deps = []

        sr_val = row['structured_result'] if 'structured_result' in keys else None
        if sr_val:
            try:
                sr = json.loads(sr_val) if isinstance(sr_val, str) else dict(sr_val)
            except Exception:
                sr = None
        else:
            sr = None

        return AgentRun(
            run_id=row['run_id'],
            agent_id=row['agent_id'],
            project_id=row['project_id'],
            prompt=row['prompt'],
            status=TaskStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
            result=row['result'],
            error=row['error'],
            exit_code=row['exit_code'],
            events=json.loads(row['events']) if row['events'] else [],
            parent_task_id=row['parent_task_id'] if 'parent_task_id' in keys else None,
            root_task_id=row['root_task_id'] if 'root_task_id' in keys else None,
            assigned_by=row['assigned_by'] if 'assigned_by' in keys else None,
            session_id=row['session_id'] if 'session_id' in keys else None,
            dependencies=deps,
            structured_result=sr,
            acceptance_criteria=row['acceptance_criteria'] if 'acceptance_criteria' in keys else None,
            retry_count=int(row['retry_count']) if 'retry_count' in keys and row['retry_count'] is not None else 0,
            input_tokens=int(row['input_tokens']) if 'input_tokens' in keys and row['input_tokens'] is not None else 0,
            output_tokens=int(row['output_tokens']) if 'output_tokens' in keys and row['output_tokens'] is not None else 0,
            cache_read_tokens=int(row['cache_read_tokens']) if 'cache_read_tokens' in keys and row['cache_read_tokens'] is not None else 0,
            cache_write_tokens=int(row['cache_write_tokens']) if 'cache_write_tokens' in keys and row['cache_write_tokens'] is not None else 0,
            cost_usd=float(row['cost_usd']) if 'cost_usd' in keys and row['cost_usd'] is not None else 0.0,
            cost_source=row['cost_source'] if 'cost_source' in keys and row['cost_source'] else 'UNKNOWN',
            model=row['model'] if 'model' in keys else None,
            organization_id=row['organization_id'] if 'organization_id' in keys else None
        )

    def save_task_run(self, run: AgentRun):
        """Save or update a task run."""
        deps_json = json.dumps(run.dependencies) if getattr(run, "dependencies", None) else None
        sr_json = json.dumps(run.structured_result) if getattr(run, "structured_result", None) else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO task_runs
                (run_id, agent_id, project_id, prompt, status, created_at, started_at, ended_at,
                 result, error, exit_code, events, parent_task_id, root_task_id, assigned_by, session_id,
                 dependencies, structured_result, acceptance_criteria, retry_count,
                 input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, cost_source, model, organization_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    project_id = excluded.project_id,
                    prompt = excluded.prompt,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    started_at = COALESCE(excluded.started_at, task_runs.started_at),
                    ended_at = excluded.ended_at,
                    result = excluded.result,
                    error = excluded.error,
                    exit_code = excluded.exit_code,
                    events = COALESCE(excluded.events, task_runs.events),
                    parent_task_id = COALESCE(excluded.parent_task_id, task_runs.parent_task_id),
                    root_task_id = COALESCE(excluded.root_task_id, task_runs.root_task_id),
                    assigned_by = COALESCE(excluded.assigned_by, task_runs.assigned_by),
                    session_id = COALESCE(excluded.session_id, task_runs.session_id),
                    dependencies = COALESCE(excluded.dependencies, task_runs.dependencies),
                    structured_result = COALESCE(excluded.structured_result, task_runs.structured_result),
                    acceptance_criteria = COALESCE(excluded.acceptance_criteria, task_runs.acceptance_criteria),
                    retry_count = COALESCE(excluded.retry_count, task_runs.retry_count),
                    input_tokens = COALESCE(excluded.input_tokens, task_runs.input_tokens),
                    output_tokens = COALESCE(excluded.output_tokens, task_runs.output_tokens),
                    cache_read_tokens = COALESCE(excluded.cache_read_tokens, task_runs.cache_read_tokens),
                    cache_write_tokens = COALESCE(excluded.cache_write_tokens, task_runs.cache_write_tokens),
                    cost_usd = COALESCE(excluded.cost_usd, task_runs.cost_usd),
                    cost_source = COALESCE(excluded.cost_source, task_runs.cost_source),
                    model = COALESCE(excluded.model, task_runs.model),
                    organization_id = COALESCE(excluded.organization_id, task_runs.organization_id)
            """, (
                run.run_id,
                run.agent_id,
                run.project_id,
                run.prompt,
                run.status.value if hasattr(run.status, "value") else str(run.status),
                run.created_at.isoformat() if run.created_at else None,
                run.started_at.isoformat() if run.started_at else None,
                run.ended_at.isoformat() if run.ended_at else None,
                run.result,
                run.error,
                run.exit_code,
                json.dumps(run.events) if run.events else None,
                getattr(run, "parent_task_id", None),
                getattr(run, "root_task_id", None),
                getattr(run, "assigned_by", None),
                getattr(run, "session_id", None),
                deps_json,
                sr_json,
                getattr(run, "acceptance_criteria", None),
                getattr(run, "retry_count", 0),
                getattr(run, "input_tokens", 0) or 0,
                getattr(run, "output_tokens", 0) or 0,
                getattr(run, "cache_read_tokens", 0) or 0,
                getattr(run, "cache_write_tokens", 0) or 0,
                float(getattr(run, "cost_usd", 0.0) or 0.0),
                getattr(run, "cost_source", "UNKNOWN"),
                getattr(run, "model", None),
                getattr(run, "organization_id", None)
            ))
            conn.commit()

    def get_task_run(self, run_id: str) -> Optional[AgentRun]:
        """Get a task run by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM task_runs WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_task_run(row)
        return None

    def update_task_run(
        self,
        run_id: str,
        status: Optional[TaskStatus] = None,
        error: Optional[str] = None,
        result: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        structured_result: Optional[Dict[str, Any]] = None,
        acceptance_criteria: Optional[str] = None,
        retry_count: Optional[int] = None,
        ended_at: Optional[datetime] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        cache_read_tokens: Optional[int] = None,
        cache_write_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        cost_source: Optional[str] = None,
        model: Optional[str] = None
    ) -> Optional[AgentRun]:
        """Update specific fields of an existing task run."""
        fields = []
        params = []
        if status is not None:
            fields.append("status = ?")
            params.append(status.value if hasattr(status, "value") else str(status))
        if error is not None:
            fields.append("error = ?")
            params.append(error)
        if result is not None:
            fields.append("result = ?")
            params.append(result)
        if dependencies is not None:
            fields.append("dependencies = ?")
            params.append(json.dumps(dependencies))
        if structured_result is not None:
            fields.append("structured_result = ?")
            params.append(json.dumps(structured_result))
        if acceptance_criteria is not None:
            fields.append("acceptance_criteria = ?")
            params.append(acceptance_criteria)
        if retry_count is not None:
            fields.append("retry_count = ?")
            params.append(retry_count)
        if ended_at is not None:
            fields.append("ended_at = ?")
            params.append(ended_at.isoformat() if isinstance(ended_at, datetime) else str(ended_at))
        if input_tokens is not None:
            fields.append("input_tokens = ?")
            params.append(input_tokens)
        if output_tokens is not None:
            fields.append("output_tokens = ?")
            params.append(output_tokens)
        if cache_read_tokens is not None:
            fields.append("cache_read_tokens = ?")
            params.append(cache_read_tokens)
        if cache_write_tokens is not None:
            fields.append("cache_write_tokens = ?")
            params.append(cache_write_tokens)
        if cost_usd is not None:
            fields.append("cost_usd = ?")
            params.append(cost_usd)
        if cost_source is not None:
            fields.append("cost_source = ?")
            params.append(cost_source)
        if model is not None:
            fields.append("model = ?")
            params.append(model)

        if not fields:
            return self.get_task_run(run_id)

        params.append(run_id)
        query = f"UPDATE task_runs SET {', '.join(fields)} WHERE run_id = ?"
        with self._get_connection() as conn:
            conn.execute(query, params)
            conn.commit()

        return self.get_task_run(run_id)

    def list_task_runs(
        self,
        agent_id: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        organization_id: Optional[str] = None
    ) -> List[AgentRun]:
        """List task runs with optional filtering, scoped by organization if provided."""
        with self._get_connection() as conn:
            query = "SELECT * FROM task_runs WHERE 1=1"
            params = []

            if organization_id:
                query += " AND organization_id = ?"
                params.append(organization_id)
            if agent_id:
                query += " AND agent_id = ?"
                params.append(agent_id)
            if project_id:
                query += " AND project_id = ?"
                params.append(project_id)
            if status:
                query += " AND status = ?"
                params.append(status.value if hasattr(status, "value") else str(status))

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [self._row_to_task_run(row) for row in cursor.fetchall()]

    def delete_task_run(self, run_id: str):
        """Delete a task run and any child subtasks."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM task_runs WHERE parent_task_id = ?", (run_id,))
            conn.execute("DELETE FROM task_runs WHERE run_id = ?", (run_id,))
            conn.commit()

    def get_subtasks(self, parent_task_id: str) -> List[AgentRun]:
        """Query subtasks for a parent task."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM task_runs WHERE parent_task_id = ? ORDER BY created_at ASC",
                (parent_task_id,)
            )
            return [self._row_to_task_run(row) for row in cursor.fetchall()]

    def get_task_tree(self, root_task_id: str) -> Dict[str, Any]:
        """
        Build a nested recursive dictionary representing the task tree rooted at root_task_id.
        Each node contains task run fields and a 'children' list of child nodes.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM task_runs
                   WHERE run_id = ? OR root_task_id = ? OR parent_task_id = ?
                   ORDER BY created_at ASC""",
                (root_task_id, root_task_id, root_task_id)
            )
            rows = cursor.fetchall()

        if not rows:
            return {}

        nodes: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            run = self._row_to_task_run(row)
            node = run.to_dict()
            node["children"] = []
            nodes[run.run_id] = node

        root_node = nodes.get(root_task_id)
        if not root_node:
            for node in nodes.values():
                if not node.get("parent_task_id") or node.get("parent_task_id") not in nodes:
                    root_node = node
                    break
            if not root_node:
                return {}

        for run_id, node in nodes.items():
            if run_id == root_node["run_id"]:
                continue
            parent_id = node.get("parent_task_id")
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)

        return root_node

    def count_active_subtasks_for_parent(self, parent_agent_id: str) -> int:
        """Count active subtasks (running or pending) assigned by a parent agent."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM task_runs WHERE assigned_by = ? AND LOWER(status) IN ('running', 'pending')",
                (parent_agent_id,)
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
