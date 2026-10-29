"""Workflows persistence operations; dependencies are injected callbacks."""
from .records import RunEvaluation, Workflow, WorkflowExecution
from datetime import datetime
from typing import List, Optional
import uuid


class WorkflowsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def save_workflow_step_run(self, record):
        """Persist one observed step outcome; the caller supplies truthful state."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO workflow_step_runs (
                    id, execution_id, step_key, agent_id, status, task_run_id,
                    input_data, output_data, input_tokens, output_tokens, cost_usd,
                    started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(record[key] for key in (
                "id", "execution_id", "step_key", "agent_id", "status", "task_run_id",
                "input_data", "output_data", "input_tokens", "output_tokens", "cost_usd",
                "started_at", "completed_at",
            )))

    def create_workflow(
        self,
        id: str,
        name: str,
        definition_json: str,
        department_id: Optional[str] = None,
        description: Optional[str] = None,
        cron_expression: Optional[str] = None,
        webhook_enabled: bool = True,
        organization_id: Optional[str] = None
    ) -> Workflow:
        """Create a workflow definition."""
        now = datetime.now().isoformat()
        webhook_token = f"whk_{uuid.uuid4().hex}" if webhook_enabled else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO workflows (id, name, description, department_id, definition_json, webhook_enabled, webhook_token, cron_expression, is_active, created_at, updated_at, organization_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (id, name, description, department_id, definition_json, 1 if webhook_enabled else 0, webhook_token, cron_expression, now, now, organization_id))
            conn.commit()
        return self.get_workflow(id)

    @staticmethod
    def _row_to_workflow(row) -> Workflow:
        """Map the shared persisted definition contract for ID and token lookups."""
        d = dict(row)
        return Workflow(
            id=d['id'],
            name=d['name'],
            description=d.get('description'),
            department_id=d.get('department_id'),
            definition_json=d.get('definition_json') or "{}",
            webhook_enabled=bool(d.get('webhook_enabled', 1)),
            webhook_token=d.get('webhook_token'),
            cron_expression=d.get('cron_expression'),
            is_active=bool(d.get('is_active', 1)),
            organization_id=d.get('organization_id'),
            created_at=d.get('created_at'),
            updated_at=d.get('updated_at')
        )

    def get_workflow(self, id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            return self._row_to_workflow(row)

    def update_workflow(self, id: str, **kwargs) -> Optional[Workflow]:
        """Update workflow configuration, definition, and channel bindings."""
        fields = []
        params = []
        now = datetime.now().isoformat()
        allowed_keys = ("name", "description", "department_id", "definition_json", "webhook_enabled", "cron_expression", "is_active", "organization_id")
        for k in allowed_keys:
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                if k in ("webhook_enabled", "is_active"):
                    params.append(1 if kwargs[k] else 0)
                else:
                    params.append(kwargs[k])
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE workflows SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_workflow(id)

    def get_workflow_by_webhook_token(self, webhook_token: str) -> Optional[Workflow]:
        """Lookup an active workflow by its incoming webhook token."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE webhook_token = ? AND is_active = 1", (webhook_token,)).fetchone()
            if not row:
                return None
            return self._row_to_workflow(row)

    def list_workflows(
        self,
        department_id: Optional[str] = None,
        active_only: bool = False,
        organization_id: Optional[str] = None,
        department_ids: Optional[List[str]] = None
    ) -> List[Workflow]:
        """List workflows with filtering."""
        query = "SELECT id FROM workflows WHERE 1=1"
        params = []
        if organization_id:
            query += " AND organization_id = ?"
            params.append(organization_id)
        if department_id:
            query += " AND department_id = ?"
            params.append(department_id)
        if department_ids is not None:
            if not department_ids:
                return []
            placeholders = ",".join("?" for _ in department_ids)
            query += f" AND department_id IN ({placeholders})"
            params.extend(department_ids)
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY name ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self.get_workflow(r['id']) for r in rows if r['id']]

    def delete_workflow(self, id: str) -> bool:
        """Delete a workflow and cascade delete executions."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM workflows WHERE id = ?", (id,))
            conn.commit()
            return cursor.rowcount > 0

    def create_workflow_execution(
        self,
        execution_id: str,
        workflow_id: str,
        trigger_type: str,
        trigger_payload: Optional[str] = None,
        department_id: Optional[str] = None,
        sandbox_path: Optional[str] = None
    ) -> WorkflowExecution:
        """Create a new workflow execution instance."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO workflow_executions (
                    id, workflow_id, trigger_type, trigger_payload, status,
                    department_id, sandbox_path, started_at, created_at
                ) VALUES (?, ?, ?, ?, 'RUNNING', ?, ?, ?, ?)
            """, (execution_id, workflow_id, trigger_type, trigger_payload, department_id, sandbox_path, now, now))
            conn.commit()
        return self.get_workflow_execution(execution_id)

    def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution status and metrics."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflow_executions WHERE id = ?", (execution_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return WorkflowExecution(
                id=d['id'],
                workflow_id=d['workflow_id'],
                trigger_type=d['trigger_type'],
                trigger_payload=d.get('trigger_payload'),
                status=d.get('status') or 'PENDING',
                department_id=d.get('department_id'),
                sandbox_path=d.get('sandbox_path'),
                total_input_tokens=int(d.get('total_input_tokens') or 0),
                total_output_tokens=int(d.get('total_output_tokens') or 0),
                total_cost_usd=float(d.get('total_cost_usd') or 0.0),
                started_at=d.get('started_at'),
                completed_at=d.get('completed_at'),
                error_message=d.get('error_message'),
                created_at=d.get('created_at')
            )

    def update_workflow_execution(self, execution_id: str, **kwargs) -> Optional[WorkflowExecution]:
        """Update status, token counts, or error for an execution."""
        fields = []
        params = []
        for k in ("status", "total_input_tokens", "total_output_tokens", "total_cost_usd", "completed_at", "error_message"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                params.append(kwargs[k])
        if fields:
            params.append(execution_id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE workflow_executions SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_workflow_execution(execution_id)

    def save_run_evaluation(
        self,
        id: str,
        execution_id: str,
        workflow_id: str,
        rating: Optional[int] = None,
        feedback_notes: Optional[str] = None,
        lessons_extracted: Optional[str] = None
    ) -> RunEvaluation:
        """Save a human or automated evaluation for learning."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO run_evaluations (id, execution_id, workflow_id, rating, feedback_notes, lessons_extracted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id, execution_id, workflow_id, rating, feedback_notes, lessons_extracted, now))
            conn.commit()
        return RunEvaluation(
            id=id,
            execution_id=execution_id,
            workflow_id=workflow_id,
            rating=rating,
            feedback_notes=feedback_notes,
            lessons_extracted=lessons_extracted,
            created_at=now
        )
