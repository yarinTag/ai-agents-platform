"""Check surviving historical references without resurrecting deleted identities."""
from .configuration_snapshot import MigrationConflict
from .execution_snapshot import json_value


def validate_source_ownership(connection, org, rows):
    references = {'users': set(), 'agents': set(), 'task_runs': set(),
                  'channel_bindings': set(), 'external_identity_links': set(), 'mcp_connectors': set()}
    sources = (
        ('workflow_step_runs', 'agent_id', 'agents'),
        ('workflow_step_runs', 'task_run_id', 'task_runs'),
        ('workflow_tool_scopes', 'task_id', 'task_runs'),
        ('workflow_repo_workspaces', 'task_id', 'task_runs'),
        ('workflow_approvals', 'task_id', 'task_runs'),
        ('workflow_approvals', 'resolved_by', 'users'),
        ('workflow_dag_approvals', 'initiator_id', 'users'),
        ('workflow_dag_approvals', 'decided_by', 'users'),
        ('workflow_dag_approval_votes', 'user_id', 'users'),
        ('dag_channel_callbacks', 'user_id', 'users'),
        ('pr_channel_deliveries', 'binding_id', 'channel_bindings'),
        ('dag_channel_deliveries', 'binding_id', 'channel_bindings'),
        ('pr_channel_deliveries', 'identity_link_id', 'external_identity_links'),
        ('pr_channel_deliveries', 'connector_id', 'mcp_connectors'),
        ('dag_channel_deliveries', 'connector_id', 'mcp_connectors'),
    )
    for table, column, target in sources:
        values = [row[column] for row in rows[table] if row[column] is not None]
        if any(not isinstance(value, str) for value in values):
            raise MigrationConflict('Historical reference has an invalid identifier type.')
        references[target].update(values)
    for table, column in (('workflow_execution_tool_contexts', 'context_json'),
                          ('workflow_tool_scopes', 'scope_json')):
        for row in rows[table]:
            value = json_value(row, column, dict)
            for key, target in (('initiator_id', 'users'), ('agent_id', 'agents'),
                                ('notification_agent_id', 'agents')):
                if isinstance(value.get(key), str):
                    references[target].add(value[key])
            if table == 'workflow_tool_scopes' and 'entries' in value:
                if not isinstance(value['entries'], list):
                    raise MigrationConflict('Invalid frozen tool entries.')
                for entry in value['entries']:
                    if not isinstance(entry, dict):
                        raise MigrationConflict('Invalid frozen tool entry.')
                    connector = entry.get('connector_id')
                    if connector is not None:
                        if not isinstance(connector, str):
                            raise MigrationConflict('Invalid frozen connector reference.')
                        references['mcp_connectors'].add(connector)
    for table, identifiers in references.items():
        # Fixed source table/key names only; values are parameterized in bounded chunks.
        key = 'run_id' if table == 'task_runs' else 'id'
        ordered = sorted(identifiers)
        for offset in range(0, len(ordered), 400):
            batch = ordered[offset:offset + 400]
            marks = ','.join('?' for _ in batch)
            foreign = connection.execute(f'SELECT 1 FROM {table} WHERE {key} IN ({marks}) '
                'AND organization_id IS NOT NULL AND organization_id<>? LIMIT 1', (*batch, org)).fetchone()
            if foreign:
                raise MigrationConflict(f'Historical reference belongs to another organization in {table}.')
