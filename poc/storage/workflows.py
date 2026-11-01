"""Workflows persistence operations; dependencies are injected callbacks."""
from .records import RunEvaluation, Workflow, WorkflowExecution, WorkflowRevisionConflict
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
import json


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
                    started_at, completed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    execution_id=excluded.execution_id,
                    step_key=excluded.step_key,
                    agent_id=excluded.agent_id,
                    status=excluded.status,
                    task_run_id=excluded.task_run_id,
                    input_data=excluded.input_data,
                    output_data=excluded.output_data,
                    input_tokens=excluded.input_tokens,
                    output_tokens=excluded.output_tokens,
                    cost_usd=excluded.cost_usd,
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at,
                    error_message=excluded.error_message
            """, tuple(record[key] for key in (
                "id", "execution_id", "step_key", "agent_id", "status", "task_run_id",
                "input_data", "output_data", "input_tokens", "output_tokens", "cost_usd",
                "started_at", "completed_at",
            )) + (record.get("error_message"),))

    def create_workflow(
        self,
        id: str,
        name: str,
        definition_json: str,
        department_id: Optional[str] = None,
        description: Optional[str] = None,
        cron_expression: Optional[str] = None,
        webhook_enabled: bool = True,
        organization_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_label: str = "System",
        is_active: bool = True
    ) -> Workflow:
        """Create a workflow definition."""
        now = datetime.now().isoformat()
        webhook_token = f"whk_{uuid.uuid4().hex}" if webhook_enabled else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO workflows (id, name, description, department_id, definition_json, webhook_enabled, webhook_token, cron_expression, is_active, created_at, updated_at, organization_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (id, name, description, department_id, definition_json, 1 if webhook_enabled else 0, webhook_token, cron_expression, int(is_active), now, now, organization_id))
            row = dict(conn.execute("SELECT * FROM workflows WHERE id = ?", (id,)).fetchone())
            self._insert_workflow_revision(conn, row, list(self._WORKFLOW_VERSION_FIELDS),
                actor_id, actor_label, "Workflow created", now)
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
            updated_at=d.get('updated_at'),
            revision=d.get('revision', 1),
        )

    def get_workflow(self, id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            return self._row_to_workflow(row)

    def update_workflow(self, id: str, *, actor_id: Optional[str] = None,
                        actor_label: str = "System", change_summary: Optional[str] = None,
                        expected_revision: Optional[int] = None, **kwargs) -> Optional[Workflow]:
        """Atomically update the current configuration and append an immutable snapshot."""
        nullable = {"description", "department_id", "cron_expression"}
        values = {key: value for key, value in kwargs.items() if key in self._WORKFLOW_VERSION_FIELDS
                  and (value is not None or key in nullable)}
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT * FROM workflows WHERE id = ?", (id,)).fetchone()
            if current is None:
                conn.rollback()
                return None
            current = dict(current)
            if expected_revision is not None and current["revision"] != expected_revision:
                raise WorkflowRevisionConflict("Workflow changed since you opened it. Reload the latest revision before saving.")
            changed = []
            for key, value in values.items():
                old = current.get(key)
                if key == "definition_json":
                    try:
                        if json.loads(old or "{}") == json.loads(value):
                            continue
                    except (ValueError, TypeError):
                        pass
                if old != value:
                    changed.append(key)
            if changed:
                values = {key: values[key] for key in changed}
                values.update(revision=current["revision"] + 1, updated_at=now)
                conn.execute("UPDATE workflows SET " + ", ".join(f"{key} = ?" for key in values) + " WHERE id = ?",
                    (*values.values(), id))
                current.update(values)
                self._insert_workflow_revision(conn, current, changed, actor_id, actor_label, change_summary, now)
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
        sandbox_path: Optional[str] = None,
        payload_hash: Optional[str] = None,
        status: str = "RUNNING"
    ) -> WorkflowExecution:
        """Create a new workflow execution instance."""
        now = datetime.now().isoformat()
        started_at = now if status == "RUNNING" else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO workflow_executions (
                    id, workflow_id, trigger_type, trigger_payload, status,
                    department_id, sandbox_path, started_at, created_at, payload_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (execution_id, workflow_id, trigger_type, trigger_payload, status, department_id, sandbox_path, started_at, now, payload_hash))
            conn.commit()
        return self.get_workflow_execution(execution_id)

    def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution status and metrics."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflow_executions WHERE id = ?", (execution_id,)).fetchone()
            if not row:
                return None
            return self._row_to_workflow_execution(dict(row))

    def update_workflow_execution(self, execution_id: str, **kwargs) -> Optional[WorkflowExecution]:
        """Update status, token counts, or error for an execution."""
        fields = []
        params = []
        for k in ("status", "total_input_tokens", "total_output_tokens", "total_cost_usd", "started_at", "completed_at", "error_message", "payload_hash", "sandbox_path"):
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

    _WORKFLOW_VERSION_FIELDS = ("name", "description", "department_id", "definition_json",
        "webhook_enabled", "cron_expression", "is_active", "organization_id")


    def _insert_workflow_revision(self, conn, row, changed_fields, actor_id, actor_label, summary, created_at):
        snapshot = {key: row.get(key) for key in self._WORKFLOW_VERSION_FIELDS}
        conn.execute("""INSERT INTO workflow_revisions
            (workflow_id, revision, snapshot_json, changed_fields_json, actor_id, actor_label, change_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (row["id"], row.get("revision", 1),
            json.dumps(snapshot, ensure_ascii=False), json.dumps(changed_fields), actor_id,
            actor_label or "System", summary, created_at or datetime.now().isoformat()))


    def list_workflow_revisions(self, workflow_id: str, limit: int = 50,
                                before_revision: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            query = "SELECT * FROM workflow_revisions WHERE workflow_id = ?"
            params = [workflow_id]
            if before_revision is not None:
                query += " AND revision < ?"
                params.append(before_revision)
            rows = conn.execute(query + " ORDER BY revision DESC LIMIT ?", (*params, limit)).fetchall()
        return [{"workflow_id": row["workflow_id"], "revision": row["revision"],
            "snapshot": json.loads(row["snapshot_json"]), "changed_fields": json.loads(row["changed_fields_json"]),
            "actor_id": row["actor_id"], "actor_label": row["actor_label"],
            "change_summary": row["change_summary"], "created_at": row["created_at"]} for row in rows]


    def _row_to_workflow_execution(self, d: Dict[str, Any]) -> WorkflowExecution:
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
            created_at=d.get('created_at'),
            payload_hash=d.get('payload_hash')
        )


    def list_workflow_executions(
        self,
        workflow_id: Optional[str] = None,
        department_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[WorkflowExecution]:
        """List recent workflow executions with optional filtering."""
        query = "SELECT * FROM workflow_executions WHERE 1=1"
        params: List[Any] = []
        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        if department_id:
            query += " AND department_id = ?"
            params.append(department_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_workflow_execution(dict(r)) for r in rows]


    def find_matching_workflow_execution(
        self,
        workflow_id: str,
        payload_hash: str,
        max_cache_age_seconds: int = 300
    ) -> Optional[WorkflowExecution]:
        """
        Deduplication checker:
        1. Returns currently active (QUEUED or RUNNING) execution if present.
        2. Returns recently completed execution with identical payload_hash within cache window.
        """
        if not payload_hash:
            return None

        with self._get_connection() as conn:
            # Active check
            row = conn.execute("""
                SELECT * FROM workflow_executions
                WHERE workflow_id = ? AND payload_hash = ? AND status IN ('QUEUED', 'RUNNING')
                ORDER BY created_at DESC LIMIT 1
            """, (workflow_id, payload_hash)).fetchone()
            if row:
                return self._row_to_workflow_execution(dict(row))

            # Completed cache check
            row = conn.execute("""
                SELECT * FROM workflow_executions
                WHERE workflow_id = ? AND payload_hash = ? AND status = 'COMPLETED'
                ORDER BY completed_at DESC LIMIT 1
            """, (workflow_id, payload_hash)).fetchone()
            if row:
                d = dict(row)
                completed_at_str = d.get('completed_at')
                if completed_at_str:
                    try:
                        completed_dt = datetime.fromisoformat(completed_at_str)
                        if (datetime.now() - completed_dt).total_seconds() <= max_cache_age_seconds:
                            return self._row_to_workflow_execution(d)
                    except Exception:
                        pass
        return None


