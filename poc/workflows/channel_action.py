"""Explicit server-executed delivery steps using the governed tool executor."""
import json
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ChannelAction(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: str = Field(pattern='^send_channel_message$')
    connector_id: str = Field(min_length=1, max_length=200)
    channel_id: str = Field(min_length=1, max_length=200)
    source_step: str = Field(min_length=1, max_length=200)


def action_configuration(step):
    action = (step.params or {}).get('channel_action')
    if action is None:
        return None
    parsed = ChannelAction.model_validate(action)
    if parsed.source_step not in step.depends_on:
        raise ValueError('Channel action source_step must be an explicit step dependency.')
    return parsed


def delivery_text(action, outputs):
    text = outputs.get(action.source_step)
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Channel action requires nonempty output from its configured source step.')
    if len(text) > 60000:
        raise ValueError('Report exceeds the 60,000-character delivery limit; no content was truncated.')
    return text


def execute_channel_action(db, step, task, outputs):
    from runtime.models import TaskStatus
    from integrations.tool_definitions import ToolAccessError
    from integrations.tool_executor import WorkflowToolExecutor
    action = action_configuration(step)
    if action is None:
        raise ValueError('An explicit channel action is required.')
    executor = WorkflowToolExecutor(db, task.run_id)
    candidates = [entry for entry in executor.entries.values()
                  if entry['connector_id'] == action.connector_id
                  and entry['operation'] in ('send_message', 'post_chat_message')
                  and action.channel_id in entry['channels']]
    # The action cannot silently fulfill a mixed read/write or multiple-target step.
    if len(candidates) != 1 or len(executor.entries) != 1 or candidates[0]['channels'] != [action.channel_id]:
        raise ToolAccessError('Channel action requires exactly one authorized delivery tool and destination.')
    receipt = executor.call(candidates[0]['name'], {
        'channel_id': action.channel_id, 'text': delivery_text(action, outputs)})
    executor.verify_completion()
    current = db.get_task_run(task.run_id)
    if not current or str(getattr(current.status, 'value', current.status)).lower() != 'running':
        raise ToolAccessError('Channel action task stopped; delivery receipt does not resume cancelled work.')
    current.status = TaskStatus.COMPLETED
    current.result = json.dumps(receipt, ensure_ascii=False)
    current.ended_at = datetime.now()
    db.save_task_run(current)
