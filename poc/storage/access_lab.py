"""Explicit additive access-lab fixture registration; no application/runtime imports."""
import importlib.util
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _password_hasher():
    source = Path(__file__).resolve().parents[1] / 'backend' / 'security' / 'tokens.py'
    spec = importlib.util.spec_from_file_location('_access_lab_passwords', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.hash_password


def create_access_lab(database_path, credentials_path):
    database = Path(database_path).expanduser().resolve()
    credentials = Path(credentials_path).expanduser().resolve()
    if not database.is_file():
        raise ValueError('An existing platform database is required; no default database is created.')
    # Never place passwords in a checkout or overwrite an existing credential file.
    if credentials.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Credentials must be saved outside the repository.')
    credentials.parent.mkdir(parents=True, exist_ok=True)
    hash_password = _password_hasher()
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        descriptor = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except BaseException:
        connection.close()
        raise
    suffix = secrets.token_hex(4)
    now = datetime.now(timezone.utc).isoformat()
    rows, organizations = [], []
    committed = False
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
        connection.execute('BEGIN IMMEDIATE')
        required = {'organizations', 'departments', 'users', 'department_members', 'agents', 'projects',
                    'workflows', 'workflow_revisions', 'skills', 'agent_templates', 'mcp_connectors', 'mcp_tools', 'department_mcp_access', 'audit_logs'}
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= tables:
            raise ValueError('The database does not have the required current platform schema.')
        def insert(table, values):
            columns = ','.join(values)
            placeholders = ','.join('?' for _ in values)
            connection.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', tuple(values.values()))
        connection.execute('''CREATE TABLE IF NOT EXISTS access_resource_owners (
            resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            PRIMARY KEY(resource_type,resource_id))''')
        for label in ('Atlas', 'Boreal'):
            prefix = f'accesslab_{label.lower()}_{suffix}'
            org_id = f'org_{prefix}'
            domain = f'{label.lower()}-{suffix}.example.test'
            insert('organizations', {'id': org_id, 'name': f'Access Lab {label}', 'slug': f'access-lab-{label.lower()}-{suffix}',
                'domain': domain, 'settings_json': json.dumps({'access_lab': suffix}),
                'plugins_source_mode': 'git', 'plugins_git_repo': '', 'plugins_local_path': ''})
            departments = {}
            organizations.append({'id': org_id, 'name': f'Access Lab {label}'})
            for name in ('Engineering', 'Finance', 'Operations'):
                dept_id = f'dept_{prefix}_{name.lower()}'
                departments[name] = dept_id
                insert('departments', {'id': dept_id, 'organization_id': org_id, 'name': name,
                    'description': 'Isolated permission-lab department', 'monthly_budget_usd': 10.0,
                    'current_spend_usd': 0.0, 'budget_action': 'HARD_STOP', 'alert_threshold_pct': 80.0})
                office_id = f'agent_{prefix}_{name.lower()}'
                workflow_id = f'wf_{prefix}_{name.lower()}'
                runner_id = f'wf-agent-{workflow_id}'
                for agent_id, is_runner in ((office_id, False), (runner_id, True)):
                    insert('agents', {'id': agent_id, 'organization_id': org_id, 'department_id': dept_id,
                        'name': f'{label} {name} ' + ('Workflow Runner' if is_runner else 'Read-only Assistant'),
                        'description': 'Access-lab fixture. No credentials or live connectors.',
                        'system_prompt': 'Use only explicitly supplied data. Report missing access; do not simulate success.',
                        'skills': '[]', 'model': 'default', 'effort': 'medium', 'max_tokens': 1000,
                        'temperature': 0.2, 'department': name, 'role_type': 'WORKFLOW_AUTOMATION' if is_runner else 'WORKER',
                        'is_workflow_agent': int(is_runner), 'workflow_id': workflow_id if is_runner else None,
                        'allowed_tools': '["Read","Glob","Grep"]', 'allowed_child_ids': '[]', 'allowed_peer_ids': '[]',
                        'dangerously_skip_permissions': 0})
                definition = {'name': f'{label} {name} permission check',
                    'settings': {'execution_backend': 'direct_api'},
                    'steps': [{'key': 'check', 'name': 'Permission check', 'agent_id': runner_id,
                               'prompt_template': 'Summarize the supplied test input. Do not use external resources.', 'depends_on': []}]}
                values = {'id': workflow_id, 'name': f'{label} / {name} / Access check',
                    'description': 'Inactive permission fixture. Execution requires this organization to configure its own model credentials.',
                    'department_id': dept_id, 'organization_id': org_id, 'definition_json': json.dumps(definition),
                    'webhook_enabled': 0, 'webhook_token': None, 'cron_expression': None, 'is_active': 0,
                    'revision': 1, 'created_at': now, 'updated_at': now}
                insert('workflows', values)
                snapshot = {**values, 'is_active': False, 'webhook_enabled': False}
                insert('workflow_revisions', {'workflow_id': workflow_id, 'revision': 1,
                    'snapshot_json': json.dumps(snapshot), 'changed_fields_json': '[]', 'actor_id': None,
                    'actor_label': 'Explicit access-lab setup', 'change_summary': 'Created inactive isolated permission fixture', 'created_at': now})
            def account(name, role, memberships=(), status='ACTIVE'):
                user_id = f'usr_{prefix}_{name}'
                password = secrets.token_urlsafe(18)
                email = f'{name}@{domain}'
                insert('users', {'id': user_id, 'organization_id': org_id, 'email': email,
                    'full_name': f'{label} {name.replace("-", " ").title()}', 'role': role,
                    'status': status, 'password_hash': hash_password(password)})
                for department, department_role in memberships:
                    insert('department_members', {'id': f'mem_{secrets.token_hex(10)}', 'department_id': departments[department],
                        'user_id': user_id, 'role': department_role})
                rows.append({'organization': label, 'email': email, 'password': password, 'role': role,
                    'scope': ', '.join(f'{department}: {department_role}' for department, department_role in memberships) or ('All departments' if role == 'ORG_ADMIN' else 'No departments'), 'status': status})
                return user_id
            admin_id = account('admin', 'ORG_ADMIN')
            for department in departments:
                for role in ('MANAGER', 'OPERATOR', 'MEMBER'):
                    account(f'{department.lower()}-{role.lower()}', role, [(department, role)])
            account('mixed-manager', 'MANAGER', [('Engineering', 'MANAGER'), ('Finance', 'MEMBER')])
            account('unassigned-member', 'MEMBER')
            account('disabled-member', 'MEMBER', [('Engineering', 'MEMBER')], status='DISABLED')
            root = Path(os.getenv('PLATFORM_TENANT_STORAGE_ROOT', str(Path(__file__).resolve().parents[1] / 'workspaces' / 'tenants'))).resolve()
            project_directory = root / org_id / 'shared' / 'access-lab'
            project_directory.mkdir(parents=True, exist_ok=True)
            insert('projects', {'id': f'project_{prefix}', 'organization_id': org_id,
                'name': f'{label} shared permission project', 'description': 'Explicit organization-shared project, not another department workspace.',
                'working_directory': str(project_directory), 'instructions': 'Use only the test input. Do not contact external services.',
                'skills': '[]', 'allowed_tools': '["Read","Glob","Grep"]'})
            skill_id, template_id = f'{org_id}--access-reading', f'{org_id}--access-assistant'
            insert('skills', {'id': skill_id, 'name': f'{label} private reading skill', 'description': 'Visible only in this lab organization.',
                'content': 'Read the provided input and cite evidence. Never claim an operation was performed without a receipt.'})
            insert('agent_templates', {'id': template_id, 'name': f'{label} private assistant template',
                'description': 'Organization-owned, read-only fixture', 'role': 'WORKER', 'system_prompt': 'Read only explicitly supplied data.',
                'skills': '[]', 'tools': '["Read","Glob","Grep"]', 'suggested_children': '[]', 'model': 'default', 'category': 'Engineering'})
            for kind, identifier in (('skill', skill_id), ('template', template_id)):
                insert('access_resource_owners', {'resource_type': kind, 'resource_id': identifier, 'organization_id': org_id})
            connector_id = f'mcp_{prefix}_offline'
            insert('mcp_connectors', {'id': connector_id, 'organization_id': org_id, 'name': f'{label} OFFLINE permission fixture',
                'provider': 'github', 'status': 'DISCONNECTED', 'configuration': '{}', 'capabilities': '[]'})
            insert('mcp_tools', {'id': f'tool_{prefix}_read', 'connector_id': connector_id, 'name': 'list_issues', 'description': 'Offline fixture; no credentials.'})
            insert('department_mcp_access', {'id': f'grant_{prefix}', 'organization_id': org_id,
                'department_id': departments['Engineering'], 'connector_id': connector_id,
                'allowed_tools': '["list_issues"]', 'is_active': 1, 'granted_by_user_id': admin_id})
            insert('audit_logs', {'id': f'audit_{prefix}', 'action': 'ACCESS_LAB_CREATED', 'actor': 'explicit-local-setup',
                'entity_type': 'organization', 'entity_id': org_id,
                'details': json.dumps({'organization_id': org_id, 'departments': list(departments.values()), 'no_execution': True}), 'timestamp': now})
        content = ['# Access lab login accounts', '', f'Created: {now}', '',
                   'Open the platform login page and use an account below. Each password is unique.',
                   'Organizations have no model/provider keys. Connectors are OFFLINE; workflows are inactive, with no cron or webhooks.',
                   'No existing organization, account, permission or execution was modified.', '',
                   '| Organization | Email | Password | Account role | Department access | Status |',
                   '|---|---|---|---|---|---|']
        content += [f"| {row['organization']} | {row['email']} | {row['password']} | {row['role']} | {row['scope']} | {row['status']} |" for row in rows]
        content += ['', '## Manual cases', '',
                    '1. Admin: all three own departments; the other organization never appears.',
                    '2. Manager: edit agents/workflows/schedules in the assigned department; no connector grants, provider keys or organization administration.',
                    '3. Operator: run/cancel work and chat in the assigned department; cannot edit workflow definitions or governance.',
                    '4. Member: read assigned department resources; mutation controls are disabled and direct writes denied.',
                    '5. Mixed manager: Engineering management, Finance read-only, Operations denied.',
                    '6. Unassigned member: no department data. Disabled member: login denied.',
                    '7. Engineering sees the offline connector grant; Finance/Operations members do not.',
                    '8. Use the copied resource IDs below with another organization login: direct detail and mutation requests must fail.',
                    '', '## Organization IDs', '']
        content += [f"- {org['name']}: `{org['id']}`" for org in organizations]
        content += ['', f'Database: {database}', f'Fixture marker: {suffix}',
                    'The source security changes require backend reload. This setup does not run application or permission tests.']
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            descriptor = None
            stream.write('\n'.join(content) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        connection.commit()
        committed = True
        return {'organizations': organizations, 'departments': 6, 'users': len(rows), 'agents': 12,
                'inactive_workflows': 6, 'shared_projects': 2, 'credentials_path': str(credentials), 'fixture_marker': suffix}
    finally:
        if not committed:
            connection.rollback()
            if descriptor is not None:
                os.close(descriptor)
            credentials.unlink(missing_ok=True)
        connection.close()
