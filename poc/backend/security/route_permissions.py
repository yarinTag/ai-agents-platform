"""Reviewed route inventory. New endpoint names require an explicit permission entry."""
from fastapi import HTTPException


def rules(read='', operate='', manage='', admin=''):
    result = {}
    for level, names in ((1, read), (2, operate), (3, manage), (4, admin)):
        for name in names.split():
            if name in result:
                raise ValueError('Duplicate endpoint permission entry')
            result[name] = level
    return result


ROUTE_PERMISSIONS = {
    'governance': rules(read='list_capability_descriptors get_effective_capability_catalog explain_capability_decision list_channel_bindings get_channel_binding_catalog list_external_identities issue_identity_challenge read_identity_challenge confirm_identity_challenge unlink_external_identity list_identity_connectors',
        manage='get_department_capability_policy put_department_capability_policy list_department_capability_revisions list_managed_identities revoke_managed_identity',
        admin='get_organization_capability_policy put_organization_capability_policy create_channel_binding replace_channel_binding_uses delete_channel_binding rotate_identity_secret get_channel_ingress_diagnostics test_channel_ingress_configuration'),
    'agents': rules(read='list_agents get_entire_hierarchy_tree get_agent get_agent_children get_agent_subtree', manage='create_agent update_agent delete_agent'),
    'projects': rules(read='list_projects get_project list_memories get_context_prompt', admin='create_project update_project delete_project create_memory delete_memory'),
    'skills': rules(read='list_skills get_skill scan_plugins get_plugin_skill_content get_plugins_config', admin='create_skill update_skill delete_skill update_plugins_config get_plugin_git_repos'),
    'tasks': rules(read='list_tasks get_task get_subtasks get_task_tree task_events get_task_logs', operate='create_task delete_task cancel_task delegate_task'),
    'templates': rules(read='list_templates get_template', manage='instantiate_agent_from_template', admin='create_template delete_template'),
    'models': rules(read='list_model_tiers list_models'),
    'runtimes': rules(admin='get_runtime_setup_state select_runtime_provider revoke_provider_credential redetect_providers'),
    'audit': rules(admin='list_audit_logs', read='get_auth_status'),
    'auth': rules(read='get_current_user_profile get_auth_status', admin='list_audit_logs'),
    'schedules': rules(read='list_schedules get_schedule get_schedule_upcoming_runs validate_cron', operate='trigger_schedule_now', manage='create_schedule update_schedule delete_schedule toggle_schedule'),
    'approvals': rules(read='list_pending_approvals', operate='create_approval_request', manage='respond_to_interaction', admin='dispatch_interactive_approval_to_channel'),
    'chat': rules(read='list_sessions get_messages', operate='create_session activate_session send_message clear_messages'),
    'events': rules(read='stream_events get_system_stats get_system_health get_recent_activity'),
    'war-room': rules(read='list_war_room_sessions get_session', operate='add_message', manage='create_session synthesize_plan'),
    'messages': rules(read='list_agent_messages get_agent_message_detail', operate='send_agent_message reply_agent_message'),
    'teams': rules(read='list_teams get_team', operate='dispatch_team synthesize_team', manage='create_team'),
    'fs': rules(admin='browse_directory pick_folder_native'),
    'workflows': rules(read='list_workflows get_workflow list_workflow_revisions list_executions get_execution_status get_workflow_settings get_workflow_approval get_channel_trigger list_dag_approvals decide_dag_approval context convert_format create_workflow generate_workflow_definition chat get_chat cancel_chat create_from_chat',
        operate='execute_workflow execute_playground trigger_webhook',
        manage='decide_workflow_approval save_channel_trigger preview_channel_trigger update_workflow delete_workflow bind_workflow_channel unbind_workflow_channel evaluate_execution update_workflow_settings put_workflow_secret delete_workflow_secret'),
    'mcp': rules(read='get_catalog list_installed_connectors get_connector list_connector_tools list_agent_permissions',
        admin='install_connector update_connector uninstall_connector test_connector test_channel_message discover_resources grant_permission revoke_permission'),
    'organizations': rules(read='list_organizations get_organization', admin='create_organization update_organization list_organization_users'),
    'departments': rules(read='list_departments get_department check_department_budget list_department_mcp_access get_department_mcp_access check_department_mcp_permission list_department_members',
        admin='create_department update_department grant_department_mcp_access revoke_department_mcp_access bulk_invite_department_members remove_department_member'),
}


def required_level(request, domain):
    endpoint = request.scope.get('route')
    name = getattr(endpoint, 'name', None)
    level = ROUTE_PERMISSIONS.get(domain, {}).get(name)
    if level is None:
        raise HTTPException(403, 'No reviewed permission policy exists for this endpoint.')
    return level
