"""Audit persistence operations; dependencies are injected callbacks."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


class AuditRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def log_audit(
        self,
        action: str,
        actor: str,
        entity_type: str,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record an immutable security audit trail event."""
        log_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        details_json = json.dumps(details) if details is not None else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs
                (id, action, actor, entity_type, entity_id, details, ip_address, correlation_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, action, actor, entity_type, entity_id, details_json, ip_address, correlation_id, now))
            conn.commit()

        return {
            "id": log_id,
            "action": action,
            "actor": actor,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
            "ip_address": ip_address,
            "correlation_id": correlation_id,
            "timestamp": now
        }

    def get_audit_logs(
        self,
        limit: int = 100,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        actor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve security audit logs with optional filters."""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: List[Any] = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if action:
            query += " AND action = ?"
            params.append(action)
        if actor:
            query += " AND actor = ?"
            params.append(actor)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            res = []
            for r in rows:
                details = None
                if r['details']:
                    try:
                        details = json.loads(r['details'])
                    except Exception:
                        details = r['details']
                res.append({
                    "id": r['id'],
                    "action": r['action'],
                    "actor": r['actor'],
                    "entity_type": r['entity_type'],
                    "entity_id": r['entity_id'],
                    "details": details,
                    "ip_address": r['ip_address'],
                    "correlation_id": r['correlation_id'],
                    "timestamp": str(r['timestamp'])
                })
            return res
