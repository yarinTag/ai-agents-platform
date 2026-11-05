"""Organization-only runtime configuration and authenticated encrypted credentials."""
import os
import secrets
from datetime import datetime


class OrganizationRuntimeSettings:
    """Settings port with no fallback to platform settings or host credentials."""

    def __init__(self, db, organization_id):
        if not organization_id or not db.get_organization(organization_id):
            raise ValueError('A valid organization is required for model configuration.')
        self.db = db
        self.organization_id = organization_id

    def get_setting(self, key, default=None):
        if key.startswith('runtime_api_key_'):
            raise ValueError('Credentials must be resolved through the credential broker.')
        with self.db._get_connection() as conn:
            row = conn.execute('SELECT value FROM organization_runtime_settings WHERE organization_id=? AND key=?',
                               (self.organization_id, key)).fetchone()
        return row['value'] if row else default

    def has_credential(self, provider):
        return self.credential_version(provider) is not None

    def credential_version(self, provider):
        with self.db._get_connection() as conn:
            row = conn.execute('SELECT version FROM organization_provider_credentials WHERE organization_id=? AND provider=?',
                               (self.organization_id, provider)).fetchone()
        return row['version'] if row else None

    def resolve_credential(self, provider):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
        from integrations.workflow_secrets import _key
        with self.db._get_connection() as conn:
            row = conn.execute('SELECT ciphertext, nonce FROM organization_provider_credentials '
                               'WHERE organization_id=? AND provider=?', (self.organization_id, provider)).fetchone()
        if not row:
            return ''
        try:
            return AESGCM(_key()).decrypt(row['nonce'], row['ciphertext'], self._aad(provider)).decode()
        except InvalidTag:
            raise ValueError('The organization provider credential could not be decrypted.') from None

    def _aad(self, provider):
        return f'organization-provider:v1:{self.organization_id}:{provider}'.encode()

    def save(self, settings, credentials, actor_id):
        """Validate/encrypt first, then atomically replace configuration and keys."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from integrations.workflow_secrets import _key
        encrypted = {}
        if credentials:
            cipher = AESGCM(_key())
            for provider, value in credentials.items():
                nonce = os.urandom(12)
                encrypted[provider] = (cipher.encrypt(nonce, value.encode(), self._aad(provider)), nonce)
        now = datetime.now().isoformat()
        with self.db._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for key, value in settings.items():
                conn.execute('INSERT INTO organization_runtime_settings(organization_id,key,value,updated_at) '
                             'VALUES(?,?,?,?) ON CONFLICT(organization_id,key) DO UPDATE SET '
                             'value=excluded.value,updated_at=excluded.updated_at',
                             (self.organization_id, key, value, now))
            for provider, (ciphertext, nonce) in encrypted.items():
                conn.execute('''INSERT INTO organization_provider_credentials
                    (organization_id,provider,ciphertext,nonce,version,updated_by,updated_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(organization_id,provider) DO UPDATE SET
                    ciphertext=excluded.ciphertext,nonce=excluded.nonce,
                    version=excluded.version,
                    updated_by=excluded.updated_by,updated_at=excluded.updated_at''',
                    (self.organization_id, provider, ciphertext, nonce, secrets.randbits(62) + 1, actor_id, now))
                conn.execute('INSERT INTO organization_provider_credential_events '
                             '(organization_id,provider,action,actor_id,created_at) VALUES(?,?,?,?,?)',
                             (self.organization_id, provider, 'REPLACE', actor_id, now))

    def revoke(self, provider, actor_id=None):
        with self.db._get_connection() as conn:
            conn.execute('DELETE FROM organization_provider_credentials WHERE organization_id=? AND provider=?',
                         (self.organization_id, provider))
            conn.execute('INSERT INTO organization_provider_credential_events '
                         '(organization_id,provider,action,actor_id,created_at) VALUES(?,?,?,?,?)',
                         (self.organization_id, provider, 'REVOKE', actor_id, datetime.now().isoformat()))


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS organization_runtime_settings (
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        key TEXT NOT NULL, value TEXT, updated_at TEXT NOT NULL,
        PRIMARY KEY(organization_id,key))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS organization_provider_credentials (
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        provider TEXT NOT NULL, ciphertext BLOB NOT NULL, nonce BLOB NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, updated_by TEXT, updated_at TEXT NOT NULL,
        PRIMARY KEY(organization_id,provider))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS organization_provider_credential_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        provider TEXT NOT NULL, action TEXT NOT NULL, actor_id TEXT, created_at TEXT NOT NULL)''')
