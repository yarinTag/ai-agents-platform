"""Per-workflow secrets: AES-256-GCM at rest or external manager references.

Values are resolved only when a repository sandbox starts and are passed to the
container as environment variables via a short-lived 0600 env file. They are
never returned by the API, never placed in prompts, and redacted from tool output.

Encrypted: PLATFORM_SECRETS_KEY = base64 of 32 random bytes (e.g. `openssl rand -base64 32`).
External: AWS Secrets Manager ARNs, restricted to PLATFORM_EXTERNAL_SECRET_ARN_PREFIXES and
resolved with the server's own AWS credentials (boto3 must be installed).
"""
import base64
import binascii
import os
import re
from typing import Dict, Optional
from .tool_definitions import ToolAccessError

KEY_ENV = 'PLATFORM_SECRETS_KEY'
ARN_PREFIXES_ENV = 'PLATFORM_EXTERNAL_SECRET_ARN_PREFIXES'
MAX_SECRETS = 50
MAX_VALUE_BYTES = 32768
_NAME = re.compile(r'[A-Z_][A-Z0-9_]{0,63}')
_ARN = re.compile(r'arn:aws:secretsmanager:([a-z0-9-]+):\d{12}:secret:[A-Za-z0-9/_+=.@-]{1,512}')
# Names that would change how the sandbox or its proxy behaves are never overridable.
_RESERVED = {'PATH', 'HOME', 'USER', 'SHELL', 'PWD', 'HOSTNAME', 'LANG', 'TERM', 'TMPDIR', 'HTTP_PROXY',
             'HTTPS_PROXY', 'NO_PROXY', 'ALL_PROXY', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH',
             'PYTHONHOME', 'NODE_OPTIONS', 'BASH_ENV', 'ENV'}


def validate_name(name: str) -> str:
    # DOCKER_* would redirect the docker CLI that receives secrets through its environment.
    if not _NAME.fullmatch(name or '') or name in _RESERVED or name.startswith(('PLATFORM_', 'DOCKER_')):
        raise ValueError('Secret names must be UPPER_SNAKE_CASE (max 64), not reserved, PLATFORM_* or DOCKER_*.')
    return name


def _key() -> bytes:
    raw = os.getenv(KEY_ENV, '').strip()
    try:
        key = base64.b64decode(raw, validate=True) if raw else b''
    except (binascii.Error, ValueError):
        key = b''
    if len(key) != 32:
        raise ToolAccessError(f'{KEY_ENV} must be base64 of 32 random bytes to store or use encrypted secrets.')
    return key


def _aad(workflow_id: str, name: str) -> bytes:
    # Binding ciphertext to its workflow and name prevents copying it to another row.
    return f'workflow-secret:v1:{workflow_id}:{name}'.encode()


def encrypt_value(workflow_id: str, name: str, value: str):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    data = value.encode()
    if not data or len(data) > MAX_VALUE_BYTES:
        raise ValueError(f'Secret values must be 1..{MAX_VALUE_BYTES} bytes.')
    nonce = os.urandom(12)
    return AESGCM(_key()).encrypt(nonce, data, _aad(workflow_id, name)), nonce


def decrypt_value(workflow_id: str, name: str, ciphertext: bytes, nonce: bytes) -> str:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        return AESGCM(_key()).decrypt(nonce, ciphertext, _aad(workflow_id, name)).decode()
    except InvalidTag as exc:
        raise ToolAccessError(f'Secret {name} could not be decrypted (wrong key or tampered record).') from exc


def validate_external_ref(ref: str) -> str:
    prefixes = [p.strip() for p in os.getenv(ARN_PREFIXES_ENV, '').split(',') if p.strip()]
    if not _ARN.fullmatch(ref or ''):
        raise ValueError('External secrets must be AWS Secrets Manager ARNs.')
    if not prefixes:
        raise ToolAccessError(f'Set {ARN_PREFIXES_ENV} to the allowed ARN prefixes before using external secrets.')
    if not any(ref.startswith(prefix) for prefix in prefixes):
        raise ValueError('This ARN is outside the allowed secret prefixes.')
    return ref


def _fetch_external(ref: str) -> str:
    validate_external_ref(ref)  # Recheck at use: the prefix allowlist may have narrowed.
    try:
        import boto3
    except ImportError as exc:
        raise ToolAccessError('External secrets need boto3 installed on the server.') from exc
    region = _ARN.fullmatch(ref).group(1)
    try:
        response = boto3.client('secretsmanager', region_name=region).get_secret_value(SecretId=ref)
    except Exception as exc:
        # Provider errors can include account details; keep the message fixed.
        raise ToolAccessError('An external secret could not be read; check the server IAM role and ARN.') from exc
    value = response.get('SecretString')
    if not isinstance(value, str) or not value or len(value.encode()) > MAX_VALUE_BYTES:
        raise ToolAccessError('External secrets must be non-empty strings within the size limit.')
    return value


def store_secret(db, workflow, name: str, value: Optional[str], external_ref: Optional[str], actor: Optional[str]):
    validate_name(name)
    if (value is None) == (external_ref is None):
        raise ValueError('Provide exactly one of value or external_ref.')
    existing = {row['name'] for row in db.list_workflow_secrets(workflow.id)}
    if name not in existing and len(existing) >= MAX_SECRETS:
        raise ValueError(f'A workflow can hold at most {MAX_SECRETS} secrets.')
    if value is not None:
        ciphertext, nonce = encrypt_value(workflow.id, name, value)
        db.upsert_workflow_secret(workflow.id, workflow.organization_id, name, 'encrypted', ciphertext, nonce, None, actor)
    else:
        db.upsert_workflow_secret(workflow.id, workflow.organization_id, name, 'external', None, None,
                                  validate_external_ref(external_ref), actor)


def resolve_workflow_secrets(db, workflow) -> Dict[str, str]:
    """All secret values for a run. Any failure fails the step: no partial environment."""
    values = {}
    for row in db.get_workflow_secret_material(workflow.id):
        if row['organization_id'] != workflow.organization_id:
            raise ToolAccessError('A workflow secret belongs to another organization.')
        name = validate_name(row['name'])
        if row['kind'] == 'encrypted':
            values[name] = decrypt_value(workflow.id, name, row['ciphertext'], row['nonce'])
        else:
            values[name] = _fetch_external(row['external_ref'])
    return values
