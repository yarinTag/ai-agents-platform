"""Schedules persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


class SchedulesRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def create_cron_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new scheduled cron job."""
        job_id = job_data.get('id') or f"cron_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        input_data = job_data.get('input_data')
        input_str = json.dumps(input_data) if isinstance(input_data, (dict, list)) else input_data

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO cron_jobs (
                    id, name, description, cron_expression, agent_id, project_id,
                    prompt, input_data, enabled, concurrency_policy, misfire_policy,
                    timezone, next_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                job_data['name'],
                job_data.get('description'),
                job_data['cron_expression'],
                job_data['agent_id'],
                job_data.get('project_id'),
                job_data['prompt'],
                input_str,
                1 if job_data.get('enabled', True) else 0,
                job_data.get('concurrency_policy', 'SKIP'),
                job_data.get('misfire_policy', 'RUN_ONCE'),
                job_data.get('timezone', 'UTC'),
                job_data['next_run_at'],
                now,
                now
            ))
            conn.commit()

        return self.get_cron_job(job_id)

    @staticmethod
    def _row_to_job(row) -> Dict[str, Any]:
        values = decode_json_columns(row, 'input_data')
        values['enabled'] = bool(values['enabled'])
        return values

    def get_cron_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a scheduled cron job by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM cron_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            return self._row_to_job(row)

    def list_cron_jobs(
        self,
        agent_id: Optional[str] = None,
        project_id: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List scheduled cron jobs with optional filters."""
        query = "SELECT * FROM cron_jobs WHERE 1=1"
        params: List[Any] = []
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        query += " ORDER BY next_run_at ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_job(row) for row in rows]

    def update_cron_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update properties of an existing cron job."""
        fields = []
        params = []
        now = datetime.now().isoformat()

        for k, v in updates.items():
            if k in ['name', 'description', 'cron_expression', 'agent_id', 'project_id',
                     'prompt', 'concurrency_policy', 'misfire_policy', 'timezone',
                     'last_run_at', 'last_run_id', 'last_status', 'next_run_at']:
                fields.append(f"{k} = ?")
                params.append(v)
            elif k == 'enabled':
                fields.append("enabled = ?")
                params.append(1 if v else 0)
            elif k == 'input_data':
                fields.append("input_data = ?")
                params.append(json.dumps(v) if isinstance(v, (dict, list)) else v)

        if not fields:
            return self.get_cron_job(job_id)

        fields.append("updated_at = ?")
        params.append(now)
        params.append(job_id)

        query = f"UPDATE cron_jobs SET {', '.join(fields)} WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, params)
            conn.commit()

        return self.get_cron_job(job_id)

    def delete_cron_job(self, job_id: str) -> bool:
        """Delete a scheduled cron job."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_due_cron_jobs(self, current_time_iso: str) -> List[Dict[str, Any]]:
        """Find enabled cron jobs that are due for execution (next_run_at <= current_time)."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM cron_jobs 
                WHERE enabled = 1 AND next_run_at <= ?
                ORDER BY next_run_at ASC
            """, (current_time_iso,)).fetchall()
            return [self._row_to_job(row) for row in rows]
