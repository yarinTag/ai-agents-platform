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
        self.notify_event(workflow_id, execution_id, trigger_type, status, outputs,
                          input_tokens, output_tokens, cost, error, event='complete')

    def notify_event(self, workflow_id, execution_id, trigger_type, status, outputs,
                     input_tokens=0, output_tokens=0, cost=0.0, error=None, *, event='complete'):
        from integrations.tool_scopes import execution_context, record_notification_error
        from integrations.notification_guard import deliver_notification, notification_call_id
        from .notification_modes import should_notify
        context = execution_context(self.database, execution_id)
        binding = context.get('binding') if context else None
        if not binding or not should_notify(binding.get('notify_mode', 'ON_COMPLETE'), event, status):
            return
        if self.database.get_mcp_tool_call(notification_call_id(execution_id, event)):
            return  # No retry of acknowledged, failed or ambiguous sends.
        workflow = self.database.get_workflow(workflow_id)
        if not workflow:
            return
        if event == 'start':
            text = f'Workflow started: {workflow.name}\nRun: {execution_id}\nTrigger: {trigger_type}'
        elif event.startswith('step:'):
            step_key = event.removeprefix('step:')
            text = f'Workflow: {workflow.name}\nStep: {step_key}\nStatus: {status}\nRun: {execution_id}'
            if error:
                text += f'\nError: {error}'
        else:
            output = list(outputs.values())[-1] if outputs else ''
            template = binding.get('message_template')
            if template:
                text = template.replace('{{workflow_name}}', workflow.name).replace('{{status}}', status)
                if '{{output}}' in template:
                    text = text.replace('{{output}}', output)
                elif output and output not in text:
                    text += f'\n\nResult:\n{output}'
            else:
                text = (f'Workflow: {workflow.name}\nStatus: {status}\nRun: {execution_id}\n'
                        f'Trigger: {trigger_type}\nTokens: {input_tokens + output_tokens}')
                if output:
                    text += f'\n\nResult:\n{output}'
            if error:
                text += f'\nError: {error}'
        try:
            deliver_notification(self.database, workflow, execution_id, text, event_key=event)
        except ValueError as failure:
            record_notification_error(self.database, execution_id, f'{event}: {failure}')
            logger.warning('Workflow notification denied/failed for %s: %s', execution_id, failure)
