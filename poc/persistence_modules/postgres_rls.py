"""
PostgreSQL Row-Level Security (RLS) DDL Generator & Append-Only Audit Repository Mixin.

Provides:
1. `generate_postgres_rls_migrations()` — generates production PostgreSQL RLS DDL
   enforcing tenant isolation via `current_setting('app.org_id')` across all multi-tenant tables.
2. `AppendOnlyAuditRepositoryMixin` — enforces immutable, append-only `audit_logs` in SQLite
   via `BEFORE UPDATE` and `BEFORE DELETE` triggers and records structured security events
   with SHA-256 `params_hash`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

RLS_MANAGED_TABLES: List[str] = [
    "organizations", "departments", "users", "department_members",
    "department_mcp_access", "workflows", "workflow_executions", "audit_logs",
]


def compute_params_hash(params: Optional[Dict[str, Any]] = None) -> str:
    """Compute a deterministic SHA-256 hex digest over canonical JSON parameters."""
    if not params:
        canonical = "{}"
    else:
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_postgres_rls_migrations() -> List[str]:
    """
    Generate PostgreSQL Row-Level Security (RLS) DDL statements for all multi-tenant tables
    using `current_setting('app.org_id')`.
    """
    statements: List[str] = []

    # 1. Direct organization_id or id match tables
    direct_policies = {
        "organizations": "id = current_setting('app.org_id', true)",
        "departments": "organization_id = current_setting('app.org_id', true)",
        "users": "organization_id = current_setting('app.org_id', true)",
        "department_mcp_access": "organization_id = current_setting('app.org_id', true)",
    }

    # 2. Relational department-scoped or tenant-scoped tables
    relational_policies = {
        "department_members": (
            "department_id IN ("
            "SELECT id FROM departments WHERE organization_id = current_setting('app.org_id', true)"
            ")"
        ),
        "workflows": (
            "department_id IN ("
            "SELECT id FROM departments WHERE organization_id = current_setting('app.org_id', true)"
            ")"
        ),
        "workflow_executions": (
            "department_id IN ("
            "SELECT id FROM departments WHERE organization_id = current_setting('app.org_id', true)"
            ")"
        ),
        "audit_logs": (
            "correlation_id LIKE (current_setting('app.org_id', true) || '%') "
            "OR details::jsonb ->> 'org_id' = current_setting('app.org_id', true)"
        ),
    }

    all_policies = {**direct_policies, **relational_policies}

    for table in RLS_MANAGED_TABLES:
        predicate = all_policies[table]
        policy_name = f"tenant_isolation_{table}_policy"
        statements.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        statements.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        statements.append(
            f"DROP POLICY IF EXISTS {policy_name} ON {table};"
        )
        statements.append(
            f"CREATE POLICY {policy_name} ON {table} "
            f"USING ({predicate}) "
            f"WITH CHECK ({predicate});"
        )

    # Append-only immutability rule for audit_logs in PostgreSQL
    statements.append(
        "CREATE OR REPLACE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;"
    )
    statements.append(
        "CREATE OR REPLACE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;"
    )

    return statements


class AppendOnlyAuditRepositoryMixin:
    """
    Mixin and helper enforcing append-only immutability on `audit_logs`
    and structured security event logging with SHA-256 `params_hash`.
    """

    @staticmethod
    def install_append_only_triggers_on_connection(conn: sqlite3.Connection) -> None:
        """Install SQLite BEFORE UPDATE and BEFORE DELETE triggers on `audit_logs`."""
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Security Violation: audit_logs is append-only (UPDATE prohibited)');
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Security Violation: audit_logs is append-only (DELETE prohibited)');
            END;
            """
        )

    def ensure_append_only_audit_triggers(self) -> None:
        """Ensure the SQLite database has append-only triggers installed on `audit_logs`."""
        with self._get_connection() as conn:  # type: ignore[attr-defined]
            self.install_append_only_triggers_on_connection(conn)
            conn.commit()

    def record_append_only_security_event(
        self, action: str, actor: str, entity_type: str, entity_id: str, org_id: str,
        department_id: Optional[str] = None, run_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None,
        decision: str = "ALLOWED", reason: Optional[str] = None, ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an immutable security event with SHA-256 `params_hash` into `audit_logs`."""
        return record_security_audit_event(
            db=self, action=action, actor=actor, entity_type=entity_type, entity_id=entity_id,
            org_id=org_id, department_id=department_id, run_id=run_id, parameters=parameters,
            metadata=metadata, decision=decision, reason=reason, ip_address=ip_address,
        )


def record_security_audit_event(
    db: Any,
    action: str,
    actor: str,
    entity_type: str,
    entity_id: str,
    org_id: str,
    department_id: Optional[str] = None,
    run_id: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    decision: str = "ALLOWED",
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Install append-only triggers (if `db` provides `_get_connection`) and write a structured
    security audit record containing `params_hash` (never raw secrets).
    """
    params_hash = compute_params_hash(parameters)
    param_keys = sorted(list(parameters.keys())) if isinstance(parameters, dict) else []

    details_payload: Dict[str, Any] = {
        "org_id": org_id,
        "department_id": department_id,
        "run_id": run_id,
        "decision": decision,
        "reason": reason,
        "params_hash": params_hash,
        "param_keys": param_keys,
    }
    if metadata:
        details_payload["metadata"] = metadata

    correlation_id = f"{org_id}:{run_id}" if run_id else org_id
    log_id = f"aud_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    if hasattr(db, "_get_connection"):
        with db._get_connection() as conn:
            AppendOnlyAuditRepositoryMixin.install_append_only_triggers_on_connection(conn)
            conn.execute(
                """
                INSERT INTO audit_logs
                (id, action, actor, entity_type, entity_id, details, ip_address, correlation_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    action,
                    actor,
                    entity_type,
                    entity_id,
                    json.dumps(details_payload, sort_keys=True),
                    ip_address,
                    correlation_id,
                    now,
                ),
            )
            conn.commit()
    elif hasattr(db, "log_audit"):
        return db.log_audit(
            action=action,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_payload,
            ip_address=ip_address,
            correlation_id=correlation_id,
        )

    return {
        "id": log_id,
        "action": action,
        "actor": actor,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details_payload,
        "params_hash": params_hash,
        "ip_address": ip_address,
        "correlation_id": correlation_id,
        "timestamp": now,
    }
