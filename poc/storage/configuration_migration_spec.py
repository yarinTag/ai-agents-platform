"""Explicit SQLite -> PostgreSQL configuration v1 inventory, not SQL translation."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[tuple[str, str], ...]
    keys: tuple[str, ...]
    query: str


def spec(name, text, *, integers='', reals='', blobs='', keys=('id',), query=None):
    columns = tuple((key, 'TEXT') for key in text.split())
    columns += tuple((key, 'BIGINT') for key in integers.split())
    columns += tuple((key, 'DOUBLE PRECISION') for key in reals.split())
    columns += tuple((key, 'BYTEA') for key in blobs.split())
    return TableSpec(name, columns, keys,
        query or f'SELECT * FROM {name} WHERE organization_id=?')


TABLES = (
    spec('organizations', 'id name slug domain settings_json created_at updated_at '
         'plugins_source_mode plugins_git_repo plugins_local_path',
         query='SELECT * FROM organizations WHERE id=?'),
    spec('departments', 'id name description budget_action organization_id created_at '
         'updated_at parent_department_id plugins_source_mode plugins_git_repo',
         reals='monthly_budget_usd current_spend_usd alert_threshold_pct'),
    spec('users', 'id organization_id email full_name role status password_hash '
         'created_at updated_at last_login_at'),
    spec('mcp_connectors', 'id name provider status configuration capabilities '
         'error_message created_at updated_at organization_id'),
    spec('mcp_tools', 'id connector_id name description input_schema created_at',
         query='SELECT t.* FROM mcp_tools t JOIN mcp_connectors c '
               'ON c.id=t.connector_id WHERE c.organization_id=?'),
    spec('department_members', 'id department_id user_id role joined_at',
         query='SELECT m.* FROM department_members m LEFT JOIN departments d '
               'ON d.id=m.department_id LEFT JOIN users u ON u.id=m.user_id '
               'WHERE d.organization_id=? OR u.organization_id=?'),
    spec('department_mcp_access', 'id organization_id department_id connector_id '
         'allowed_tools granted_by_user_id granted_at', integers='is_active',
         query='SELECT a.* FROM department_mcp_access a LEFT JOIN departments d '
               'ON d.id=a.department_id LEFT JOIN mcp_connectors c ON c.id=a.connector_id '
               'WHERE a.organization_id=? OR d.organization_id=? OR c.organization_id=?'),
    spec('workflows', 'id name description department_id definition_json webhook_token '
         'cron_expression created_at updated_at organization_id',
         integers='webhook_enabled is_active revision',
         query='SELECT w.* FROM workflows w LEFT JOIN departments d '
               'ON d.id=w.department_id WHERE w.organization_id=? OR d.organization_id=?'),
    spec('workflow_revisions', 'workflow_id snapshot_json changed_fields_json actor_id '
         'actor_label change_summary created_at', integers='revision',
         keys=('workflow_id', 'revision'),
         query='SELECT r.* FROM workflow_revisions r JOIN workflows w '
               'ON w.id=r.workflow_id WHERE w.organization_id=?'),
    spec('capability_policies', 'organization_id scope_type scope_id document_json '
         'updated_by updated_at', integers='revision', keys=('scope_type', 'scope_id')),
    spec('capability_policy_revisions', 'organization_id scope_type scope_id document_json '
         'updated_by updated_at', integers='revision',
         keys=('scope_type', 'scope_id', 'revision')),
    spec('organization_runtime_settings', 'organization_id key value updated_at', keys=('key',)),
    spec('organization_provider_credentials', 'organization_id provider updated_by updated_at',
         integers='version', blobs='ciphertext nonce', keys=('provider',)),
    spec('organization_provider_credential_events', 'organization_id provider action actor_id '
         'created_at', integers='id'),
    spec('workflow_secrets', 'id workflow_id organization_id name kind external_ref '
         'created_by created_at updated_at', blobs='ciphertext nonce'),
)

# References include tenant identity on the PostgreSQL side. Historical actor IDs
# may refer to deleted users and are deliberately not invented foreign keys.
REFERENCES = {
    'departments': (('parent_department_id', 'departments', 'id'),),
    'mcp_tools': (('connector_id', 'mcp_connectors', 'id'),),
    'department_members': (('department_id', 'departments', 'id'), ('user_id', 'users', 'id')),
    'department_mcp_access': (('department_id', 'departments', 'id'),
                              ('connector_id', 'mcp_connectors', 'id')),
    'workflows': (('department_id', 'departments', 'id'),),
    'workflow_revisions': (('workflow_id', 'workflows', 'id'),),
    'workflow_secrets': (('workflow_id', 'workflows', 'id'),),
}

# Preserve source uniqueness in addition to tenant-composite primary keys.
UNIQUES = {
    'organizations': (('id',), ('slug',)),
    'departments': (('id',),), 'users': (('id',), ('email',)),
    'mcp_connectors': (('id',),), 'mcp_tools': (('id',),),
    'department_members': (('id',), ('department_id', 'user_id')),
    'department_mcp_access': (('id',), ('department_id', 'connector_id')),
    'workflows': (('id',), ('webhook_token',)),
    'workflow_secrets': (('id',), ('workflow_id', 'name')),
    'organization_provider_credential_events': (('id',),),
}

REQUIRED = {
    'organizations': 'id name slug', 'departments': 'id name',
    'users': 'id organization_id email full_name',
    'mcp_connectors': 'id name provider status', 'mcp_tools': 'id connector_id name',
    'department_members': 'id department_id user_id',
    'department_mcp_access': 'id department_id connector_id',
    'workflows': 'id name definition_json revision',
    'workflow_revisions': 'workflow_id revision snapshot_json changed_fields_json actor_label created_at',
    'capability_policies': 'organization_id scope_type scope_id revision document_json updated_by updated_at',
    'capability_policy_revisions': 'organization_id scope_type scope_id revision document_json updated_by updated_at',
    'organization_runtime_settings': 'organization_id key updated_at',
    'organization_provider_credentials': 'organization_id provider ciphertext nonce version updated_at',
    'organization_provider_credential_events': 'id organization_id provider action created_at',
    'workflow_secrets': 'id workflow_id organization_id name kind created_at updated_at',
}

WORKFLOW_FIELDS = ('name', 'description', 'department_id', 'definition_json',
                   'webhook_enabled', 'cron_expression', 'is_active', 'organization_id')

CHECKS = {
    'capability_policies': ("scope_type IN ('organization','department') AND revision>0 "
                            "AND (scope_type<>'organization' OR scope_id=organization_id)",),
    'capability_policy_revisions': ("scope_type IN ('organization','department') AND revision>0 "
                            "AND (scope_type<>'organization' OR scope_id=organization_id)",),
    'workflows': ('revision>0',), 'workflow_revisions': ('revision>0',),
    'workflow_secrets': ("kind IN ('encrypted','external')",),
}


def schema_document():
    return {'format_version': 1, 'tables': [(t.name, t.columns, t.keys) for t in TABLES],
            'references': REFERENCES, 'required': REQUIRED, 'unique': UNIQUES, 'checks': CHECKS}
