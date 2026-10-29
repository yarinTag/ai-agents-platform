"""Best-effort notification adapter, separate from workflow execution outcome."""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkflowNotifier:
    def __init__(self, database, connector_lookup, deliver):
        self.database = database
        self.connector_lookup = connector_lookup
        self.deliver = deliver

    def notify(self, workflow_id, execution_id, trigger_type, status, outputs,
               input_tokens, output_tokens, cost, error):
        workflow = self.database.get_workflow(workflow_id)
        binding = json.loads(workflow.definition_json).get("metadata", {}).get("channel_binding") if workflow else None
        if not binding:
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
        provider = binding.get("provider", "slack")
        channel = binding.get("channel_id", "")
        connector = self.connector_lookup(self.database, provider, workflow.organization_id)
        output = list(outputs.values())[-1] if outputs else ""
        output = output[:2450] + "...\n(truncated)" if len(output) > 2500 else output
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
        if connector is None:
            logger.warning("Workflow notification connector unavailable for execution %s", execution_id)
            return
        agents = self.database.list_agents(organization_id=workflow.organization_id)
        if not agents:
            logger.warning("Workflow notification has no audit actor for execution %s", execution_id)
            return
        record = {
            "id": call_id, "connector_id": connector.id,
            "tool_id": f"tool_{provider}_send_message", "agent_id": agents[0].id,
            "task_id": None, "arguments": {"channel": channel, "text": text},
            "status": "STARTED", "started_at": datetime.now().isoformat(),
        }
        self.database.save_mcp_tool_call(record)
        try:
            self.deliver(connector, channel, text)
        except Exception:
            record.update(status="FAILED", error="Channel delivery failed")
            logger.warning("Workflow notification failed for execution %s", execution_id)
        else:
            record.update(status="COMPLETED", result=f"Notification delivered to {channel}")
        record["completed_at"] = datetime.now().isoformat()
        self.database.save_mcp_tool_call(record)
