"""Best-effort notification adapter, separate from workflow execution outcome."""

import logging

logger = logging.getLogger(__name__)


class WorkflowNotifier:
    def __init__(self, database, connector_lookup, deliver):
        self.database = database
        self.connector_lookup = connector_lookup
        self.deliver = deliver

    def notify(self, workflow_id, execution_id, trigger_type, status, outputs,
               input_tokens, output_tokens, cost, error):
        workflow = self.database.get_workflow(workflow_id)
        from integrations.tool_scopes import execution_context
        context = execution_context(self.database, execution_id)
        binding = context.get('binding') if context else None
        if not binding:
            return
        if context.get('notification_error'):
            logger.warning('Workflow notification blocked for %s: %s', execution_id, context['notification_error'])
            return
        mode = binding.get("notify_mode", "ON_COMPLETE")
        if not (mode == "ALWAYS" or mode == "ON_COMPLETE" and status == "COMPLETED"
                or mode == "ON_FAILURE" and status == "FAILED"):
            return
        call_id = f"call_notify_{execution_id}"
        # No automatic retries: a repeated call must not resend acknowledged work.
        previous = self.database.get_mcp_tool_call(call_id)
        if previous:
            return
        output = list(outputs.values())[-1] if outputs else ""
        template = binding.get("message_template")
        if template:
            text = template.replace("{{workflow_name}}", workflow.name).replace("{{status}}", status)
            if "{{output}}" in template:
                text = text.replace("{{output}}", output)
            elif output and output not in text:
                text += f"\n\n📋 *Workflow Summary / Report:*\n{output}"
        else:
            text = (f"🤖 *Workflow Run Notification*\n• Workflow: *{workflow.name}* (`{workflow.id}`)\n"
                    f"• Status: *{status}*\n• Trigger: `{trigger_type}`\n"
                    f"• Tokens: {input_tokens + output_tokens} (Cost: ${cost:.4f})")
            if output:
                text += f"\n\n📋 *Result:*\n{output}"
            if error:
                text += f"\n• Error: {error}"
        from integrations.notification_guard import deliver_notification
        try:
            deliver_notification(self.database, workflow, execution_id, text)
        except ValueError as error:
            from integrations.tool_scopes import record_notification_error
            record_notification_error(self.database, execution_id, str(error))
            logger.warning("Workflow notification denied/failed for %s: %s", execution_id, error)
