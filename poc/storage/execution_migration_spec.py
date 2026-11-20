"""History profile v2: configuration plus execution evidence, never live recovery."""
from . import configuration_migration_spec as config
from .configuration_migration_spec import spec


def by_execution(table, column='execution_id'):
    return (f'SELECT t.* FROM {table} t JOIN workflow_executions x ON x.id=t.{column} '
            'JOIN workflows w ON w.id=x.workflow_id WHERE w.organization_id=?')


def by_approval(table, parent):
    return (f'SELECT t.* FROM {table} t JOIN {parent} a ON a.id=t.approval_id '
            'JOIN workflow_executions x ON x.id=a.execution_id '
            'JOIN workflows w ON w.id=x.workflow_id WHERE a.organization_id=? OR w.organization_id=?')


HISTORY_TABLES = (
    spec('channel_bindings', 'id organization_id department_id connector_id provider '
         'channel_id created_at updated_at',
         integers='send_notifications trigger_workflows approve_decisions revision'),
    spec('external_identity_links', 'id organization_id connector_id user_id provider account subject',
         integers='created_at'),
    spec('workflow_executions', 'id workflow_id trigger_type trigger_payload status department_id '
         'sandbox_path started_at completed_at error_message created_at payload_hash',
         integers='total_input_tokens total_output_tokens', reals='total_cost_usd',
         query='SELECT x.* FROM workflow_executions x LEFT JOIN workflows w ON w.id=x.workflow_id '
               'LEFT JOIN departments d ON d.id=x.department_id '
               'WHERE w.organization_id=? OR d.organization_id=?'),
    spec('workflow_step_runs', 'id execution_id step_key agent_id status task_run_id input_data '
         'output_data started_at completed_at error_message',
         integers='input_tokens output_tokens', reals='cost_usd',
         query=by_execution('workflow_step_runs')),
    spec('run_evaluations', 'id execution_id workflow_id feedback_notes lessons_extracted created_at',
         integers='rating', query='SELECT t.* FROM run_evaluations t '
         'LEFT JOIN workflow_executions x ON x.id=t.execution_id LEFT JOIN workflows w ON w.id=x.workflow_id '
         'LEFT JOIN workflows v ON v.id=t.workflow_id WHERE w.organization_id=? OR v.organization_id=?'),
    spec('workflow_execution_tool_contexts', 'execution_id context_json', keys=('execution_id',),
         query=by_execution('workflow_execution_tool_contexts')),
    spec('workflow_tool_scopes', 'task_id execution_id scope_json', keys=('task_id',),
         query=by_execution('workflow_tool_scopes')),
    spec('workflow_repo_workspaces', 'task_id execution_id workspace_json', keys=('task_id',),
         query=by_execution('workflow_repo_workspaces')),
    spec('workflow_approvals', 'id execution_id step_run_id task_id organization_id department_id '
         'status config_json subjects_json report created_at expires_at resolved_at resolved_by '
         'error receipts_json remaining_json',
         integers='workflow_revision position advance_pending advance_claim_until',
         query='SELECT a.* FROM workflow_approvals a LEFT JOIN workflow_executions x '
               'ON x.id=a.execution_id LEFT JOIN workflows w ON w.id=x.workflow_id '
               'WHERE a.organization_id=? OR w.organization_id=?'),
    spec('workflow_dag_approvals', 'id execution_id step_key organization_id department_id '
         'initiator_id policy_json checkpoint_json status decided_by',
         integers='workflow_revision expires_at decided_at',
         query='SELECT a.* FROM workflow_dag_approvals a LEFT JOIN workflow_executions x '
               'ON x.id=a.execution_id LEFT JOIN workflows w ON w.id=x.workflow_id '
               'WHERE a.organization_id=? OR w.organization_id=?'),
    spec('workflow_dag_approval_votes', 'approval_id user_id', integers='decision created_at',
         keys=('approval_id', 'user_id'),
         query=by_approval('workflow_dag_approval_votes', 'workflow_dag_approvals')),
    spec('pr_channel_deliveries', 'approval_id binding_id token_digest connector_id channel_id '
         'message_id bot_id status rendered callback_id identity_link_id',
         integers='retry_at decision claimed_at', keys=('approval_id',),
         query=by_approval('pr_channel_deliveries', 'workflow_approvals')),
    spec('dag_channel_deliveries', 'approval_id binding_id token_digest connector_id channel_id '
         'message_id bot_id status rendered', integers='retry_at claimed_at', keys=('approval_id',),
         query=by_approval('dag_channel_deliveries', 'workflow_dag_approvals')),
    spec('dag_channel_callbacks', 'approval_id callback_id user_id action', integers='created_at',
         keys=('approval_id', 'callback_id'),
         query=by_approval('dag_channel_callbacks', 'workflow_dag_approvals')),
)
TABLES = (*config.TABLES, *HISTORY_TABLES)
REFERENCES = {**config.REFERENCES,
    'channel_bindings': (('department_id', 'departments', 'id'), ('connector_id', 'mcp_connectors', 'id')),
    'external_identity_links': (('connector_id', 'mcp_connectors', 'id'), ('user_id', 'users', 'id')),
    'workflow_executions': (('workflow_id', 'workflows', 'id'), ('department_id', 'departments', 'id')),
    'workflow_step_runs': (('execution_id', 'workflow_executions', 'id'),),
    'run_evaluations': (('execution_id', 'workflow_executions', 'id'), ('workflow_id', 'workflows', 'id')),
    'workflow_execution_tool_contexts': (('execution_id', 'workflow_executions', 'id'),),
    'workflow_tool_scopes': (('execution_id', 'workflow_executions', 'id'),),
    'workflow_repo_workspaces': (('execution_id', 'workflow_executions', 'id'),),
    'workflow_approvals': (('execution_id', 'workflow_executions', 'id'),
                          ('step_run_id', 'workflow_step_runs', 'id'), ('department_id', 'departments', 'id')),
    'workflow_dag_approvals': (('execution_id', 'workflow_executions', 'id'),
                              ('department_id', 'departments', 'id')),
    'workflow_dag_approval_votes': (('approval_id', 'workflow_dag_approvals', 'id'),),
    'pr_channel_deliveries': (('approval_id', 'workflow_approvals', 'id'),),
    'dag_channel_deliveries': (('approval_id', 'workflow_dag_approvals', 'id'),),
    # callback refers to delivery, not merely to the approval.
    'dag_channel_callbacks': (('approval_id', 'dag_channel_deliveries', 'approval_id'),),
}
REQUIRED = {**config.REQUIRED,
    'channel_bindings': 'id organization_id connector_id provider channel_id send_notifications '
        'trigger_workflows approve_decisions revision created_at updated_at',
    'external_identity_links': 'id organization_id connector_id user_id provider account subject created_at',
    'workflow_executions': 'id workflow_id trigger_type status',
    'workflow_step_runs': 'id execution_id step_key',
    'run_evaluations': 'id execution_id workflow_id',
    'workflow_execution_tool_contexts': 'execution_id context_json',
    'workflow_tool_scopes': 'task_id execution_id scope_json',
    'workflow_repo_workspaces': 'task_id execution_id workspace_json',
    'workflow_approvals': 'id execution_id step_run_id task_id organization_id department_id '
        'workflow_revision status config_json subjects_json report created_at expires_at '
        'receipts_json position remaining_json advance_pending',
    'workflow_dag_approvals': 'id execution_id step_key workflow_revision organization_id '
        'department_id initiator_id policy_json checkpoint_json status expires_at',
    'workflow_dag_approval_votes': 'approval_id user_id decision created_at',
    'pr_channel_deliveries': 'approval_id binding_id status retry_at',
    'dag_channel_deliveries': 'approval_id binding_id status retry_at',
    'dag_channel_callbacks': 'approval_id callback_id user_id action created_at',
}
UNIQUES = {**config.UNIQUES,
    **{name: (('id',),) for name in ('channel_bindings', 'external_identity_links',
        'workflow_executions', 'workflow_step_runs', 'run_evaluations')},
    'external_identity_links': (('id',), ('organization_id', 'provider', 'account', 'subject'),
                               ('organization_id', 'provider', 'account', 'user_id')),
    'workflow_approvals': (('id',), ('execution_id', 'position')),
    'workflow_dag_approvals': (('id',), ('execution_id', 'step_key')),
    'workflow_execution_tool_contexts': (('execution_id',),),
    'workflow_tool_scopes': (('task_id',),), 'workflow_repo_workspaces': (('task_id',),),
    'pr_channel_deliveries': (('approval_id',), ('token_digest',)),
    'dag_channel_deliveries': (('approval_id',), ('token_digest',)),
}
CHECKS = {**config.CHECKS,
    'channel_bindings': ('revision>0', 'send_notifications IN (0,1)',
                         'trigger_workflows IN (0,1)', 'approve_decisions IN (0,1)'),
    'workflow_dag_approvals': ("status IN ('PENDING','APPROVED','REJECTED','TIMED_OUT','CLAIMED')",),
    'workflow_dag_approval_votes': ('decision IN (0,1)',),
}


def schema_document():
    return {'format_version': 2, 'tables': [(t.name, t.columns, t.keys) for t in TABLES],
            'references': REFERENCES, 'required': REQUIRED, 'unique': UNIQUES, 'checks': CHECKS,
            'recovery_policy': 'archive_only_holds_v1',
            'extra_indexes': 'live_terminal_approval_and_exact_channel_identity_v1'}
