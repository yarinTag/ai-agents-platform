"""Real SQLite/FastAPI contracts; no provider calls. Not executed under task restrictions."""
import base64
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.api import runtimes, models
from backend.dependencies import get_db_manager
from backend.security import authenticate_request, create_access_token
from config import AgentConfig
from persistence import DatabaseManager
from runtime.command_builder import RuntimeCommandBuilder
from runtime.direct_config import configuration, resolve_api_key, model_setting
from runtime.direct_tools import DirectTools
from storage.runtime_settings import OrganizationRuntimeSettings


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_DEV_MODE', '1')
    monkeypatch.setenv('PLATFORM_SECRETS_KEY', base64.b64encode(b'a' * 32).decode())
    db = DatabaseManager(str(tmp_path / 'credentials.db'))
    for org in ('a', 'b'):
        db.create_organization(id=org, name=org, slug=org)
        db.create_user(id=org, organization_id=org, email=org + '@example.test',
                       full_name=org, role='ORG_ADMIN')
    monkeypatch.setattr(runtimes, 'db_manager', db)
    app = FastAPI()
    app.dependency_overrides[get_db_manager] = lambda: db
    app.include_router(runtimes.router, prefix='/api/v1/runtimes', dependencies=[Depends(authenticate_request)])
    app.include_router(models.router, prefix='/api/v1/models', dependencies=[Depends(authenticate_request)])
    client = TestClient(app)
    return db, client


def headers(org):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': org, 'org_id': org, 'role': 'ORG_ADMIN'})}


def save(client, org, key, model='gpt-4o'):
    return client.put('/api/v1/runtimes/selection', headers=headers(org), json={
        'provider_id': 'direct_openai', 'model_id': model, 'api_key': key})


def test_tenant_credentials_are_encrypted_and_configuration_is_private(setup):
    db, client = setup
    assert save(client, 'a', 'private-key-a', 'gpt-4.1').status_code == 200
    assert save(client, 'b', 'private-key-b').status_code == 200
    a, b = [OrganizationRuntimeSettings(db, org) for org in ('a', 'b')]
    assert resolve_api_key('direct_openai', a) == 'private-key-a'
    assert resolve_api_key('direct_openai', b) == 'private-key-b'
    assert a.get_setting(model_setting('direct_openai')) == 'gpt-4.1'
    assert b.get_setting(model_setting('direct_openai')) == 'gpt-4o'
    response = client.get('/api/v1/runtimes/', headers=headers('a'))
    assert 'private-key' not in response.text
    with db._get_connection() as conn:
        rows = conn.execute('SELECT * FROM organization_provider_credentials').fetchall()
        assert all(b'private-key' not in row['ciphertext'] for row in rows)
        assert not conn.execute("SELECT 1 FROM platform_settings WHERE key LIKE 'runtime_api_key_%'").fetchone()


def test_host_and_global_keys_never_resolve_for_unconfigured_org(setup, monkeypatch):
    db, client = setup
    monkeypatch.setenv('OPENAI_API_KEY', 'global-key')
    db.set_setting('runtime_api_key_direct_openai', 'old-global-key')
    assert resolve_api_key('direct_openai') == ''
    assert resolve_api_key('direct_openai', db) == ''
    assert resolve_api_key('direct_openai', OrganizationRuntimeSettings(db, 'b')) == ''
    state = client.get('/api/v1/runtimes/', headers=headers('b')).json()
    assert not any(provider['available'] for provider in state['providers'])
    assert client.get('/api/v1/models/', headers=headers('b')).json() == []
    assert save(client, 'b', '').status_code == 400


def test_stale_admin_disabled_user_and_secret_validation(setup):
    db, client = setup
    db.update_user('a', role='MEMBER')
    assert save(client, 'a', 'must-not-save').status_code == 403
    db.update_user('a', role='ORG_ADMIN', status='INACTIVE')
    assert save(client, 'a', 'must-not-save').status_code == 401
    response = client.put('/api/v1/runtimes/selection', headers=headers('b'), json={
        'provider_id': 'direct_openai', 'api_key': {'value': 'never-echo-secret'}})
    assert response.status_code == 422
    assert 'never-echo-secret' not in response.text


def test_invalid_batch_or_missing_encryption_key_writes_nothing(setup, monkeypatch):
    db, client = setup
    response = client.put('/api/v1/runtimes/selection', headers=headers('a'), json={
        'provider_id': 'direct_openai', 'api_key': 'private-key',
        'provider_models': {'direct_openai': 'invalid model'}})
    assert response.status_code == 400
    settings = OrganizationRuntimeSettings(db, 'a')
    assert not settings.has_credential('direct_openai')
    monkeypatch.delenv('PLATFORM_SECRETS_KEY')
    assert save(client, 'a', 'private-key').status_code == 503
    assert not settings.has_credential('direct_openai')
    assert settings.get_setting('runtime_provider') is None


def test_worker_key_rotation_revocation_and_no_cross_org_fallback(setup, monkeypatch):
    db, client = setup
    assert save(client, 'a', 'old-private-key').status_code == 200
    assert save(client, 'b', 'other-private-key').status_code == 200
    settings = OrganizationRuntimeSettings(db, 'a')
    monkeypatch.setenv('PLATFORM_PROVIDER_DB', str(db.db_path))
    monkeypatch.setenv('PLATFORM_PROVIDER_ORGANIZATION', 'a')
    monkeypatch.setenv('PLATFORM_PROVIDER_VERSION', str(settings.credential_version('direct_openai')))
    monkeypatch.setenv('OPENAI_API_KEY', 'old-private-key')
    assert configuration('direct_openai')[1] == 'old-private-key'
    assert save(client, 'a', 'new-private-key').status_code == 200
    with pytest.raises(ValueError, match='rotated'):
        configuration('direct_openai')
    monkeypatch.setenv('PLATFORM_PROVIDER_VERSION', str(settings.credential_version('direct_openai')))
    monkeypatch.setenv('OPENAI_API_KEY', 'new-private-key')
    assert configuration('direct_openai')[1] == 'new-private-key'
    assert client.delete('/api/v1/runtimes/credentials/direct_openai', headers=headers('a')).status_code == 200
    with pytest.raises(ValueError, match='revoked'):
        configuration('direct_openai')
    assert OrganizationRuntimeSettings(db, 'b').resolve_credential('direct_openai') == 'other-private-key'
    assert not client.get('/api/v1/runtimes/', headers=headers('a')).json()['setup_completed']


def test_ciphertext_cannot_be_copied_to_another_org(setup):
    db, client = setup
    assert save(client, 'a', 'bound-private-key').status_code == 200
    assert save(client, 'b', 'other-key').status_code == 200
    with db._get_connection() as conn:
        row = conn.execute("SELECT ciphertext,nonce FROM organization_provider_credentials WHERE organization_id='a'").fetchone()
        conn.execute("UPDATE organization_provider_credentials SET ciphertext=?,nonce=? WHERE organization_id='b'",
                     (row['ciphertext'], row['nonce']))
    with pytest.raises(ValueError, match='decrypted'):
        OrganizationRuntimeSettings(db, 'b').resolve_credential('direct_openai')


def test_command_environment_uses_only_own_key_and_tools_drop_credentials(setup, monkeypatch):
    db, client = setup
    assert save(client, 'a', 'own-key').status_code == 200
    monkeypatch.setenv('OPENAI_API_KEY', 'host-key')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'unrelated-key')
    monkeypatch.setenv('PLATFORM_RUNTIME_PROVIDER', 'direct_nvidia')
    monkeypatch.setenv('PLATFORM_AGENT_ENV_PASSTHROUGH', 'OPENAI_API_KEY,PLATFORM_SECRETS_KEY')
    builder = RuntimeCommandBuilder(SimpleNamespace(database=lambda: db))
    profile = AgentConfig(id='worker-a', name='A', description='A', system_prompt='', organization_id='a')
    env = builder._build_claude_env(agent_config=profile)
    assert env['OPENAI_API_KEY'] == 'own-key'
    assert env['PLATFORM_RUNTIME_PROVIDER'] == 'direct_openai'
    assert 'ANTHROPIC_API_KEY' not in env
    assert 'PLATFORM_SECRETS_KEY' not in env
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    shell_env = DirectTools._shell_env()
    assert 'OPENAI_API_KEY' not in shell_env
    assert not any(name.startswith('PLATFORM_PROVIDER_') for name in shell_env)
    with pytest.raises(ValueError):
        builder.resolve_runtime_provider(AgentConfig(id='worker-b', name='B', description='B', system_prompt='', organization_id='b'))
