"""Workflow secret records. Stores ciphertext or an external reference, never plaintext."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

_PUBLIC = 'id, workflow_id, organization_id, name, kind, external_ref, created_by, created_at, updated_at'


class WorkflowSecretsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def list_workflow_secrets(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Metadata only; ciphertext is never returned by this method."""
        with self._get_connection() as conn:
            rows = conn.execute(f'SELECT {_PUBLIC} FROM workflow_secrets WHERE workflow_id = ? ORDER BY name',
                                (workflow_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_workflow_secret_material(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Ciphertext/reference rows for runtime injection only."""
        with self._get_connection() as conn:
            rows = conn.execute('SELECT name, kind, ciphertext, nonce, external_ref, organization_id '
                                'FROM workflow_secrets WHERE workflow_id = ? ORDER BY name', (workflow_id,)).fetchall()
        return [dict(row) for row in rows]

    def upsert_workflow_secret(self, workflow_id: str, organization_id: str, name: str, kind: str,
                               ciphertext: Optional[bytes], nonce: Optional[bytes], external_ref: Optional[str],
                               actor: Optional[str]) -> None:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute('''INSERT INTO workflow_secrets
                (id, workflow_id, organization_id, name, kind, ciphertext, nonce, external_ref, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id, name) DO UPDATE SET kind=excluded.kind, ciphertext=excluded.ciphertext,
                    nonce=excluded.nonce, external_ref=excluded.external_ref, updated_at=excluded.updated_at''',
                (f'wsec_{uuid.uuid4().hex[:16]}', workflow_id, organization_id, name, kind, ciphertext, nonce,
                 external_ref, actor, now, now))

    def delete_workflow_secret(self, workflow_id: str, name: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute('DELETE FROM workflow_secrets WHERE workflow_id = ? AND name = ?', (workflow_id, name))
        return cursor.rowcount > 0
