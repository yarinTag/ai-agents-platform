"""Additive fixture setup against real SQLite; no application or providers."""
from persistence import DatabaseManager
from storage.access_lab import create_access_lab
from backend.security.tokens import verify_password


def test_access_lab_is_additive_and_creates_private_isolated_accounts(tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_TENANT_STORAGE_ROOT', str(tmp_path / 'files'))
    database = tmp_path / 'lab.db'
    db = DatabaseManager(str(database))
    db.create_organization(id='existing', name='Existing', slug='existing')
    credentials = tmp_path / 'private' / 'logins.md'
    result = create_access_lab(database, credentials)
    assert result['departments'] == 6
    assert result['users'] == 26
    assert result['inactive_workflows'] == 6
    assert db.get_organization('existing').name == 'Existing'
    assert credentials.stat().st_mode & 0o777 == 0o600
    report = credentials.read_text()
    for org in result['organizations']:
        departments = db.list_departments(organization_id=org['id'])
        assert len(departments) == 3
        assert len(db.list_users_by_organization(org['id'])) == 13
        assert all(not workflow.is_active and not workflow.webhook_enabled and workflow.cron_expression is None
                   for workflow in db.list_workflows(organization_id=org['id']))
    account_line = next(line for line in report.splitlines() if '| admin@' in line)
    cells = [cell.strip() for cell in account_line.split('|')]
    email, password = cells[2], cells[3]
    user = db.get_user_by_email(email)
    assert verify_password(password, user.password_hash)
    assert password not in user.password_hash
    assert all(connector.status == 'DISCONNECTED' for org in result['organizations']
               for connector in db.list_mcp_connectors(organization_id=org['id']))
