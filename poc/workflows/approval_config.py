"""Strict terminal human gate configuration and authoring/preflight contracts."""
import os
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field
from .channel_action import ChannelAction, action_configuration


class HumanApproval(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source_step: str = Field(min_length=1, max_length=80)
    connector_id: str = Field(min_length=1, max_length=200)
    channel_id: str = Field(min_length=1, max_length=200)
    kind: Literal['report', 'pull_requests'] = 'report'
    merge_after_approval: bool = False
    expires_hours: int = Field(default=24, ge=1, le=72)
    channel_binding_id: str | None = Field(default=None, pattern=r'^chb_[a-f0-9]{32}$')


def public_url():
    raw = os.getenv('PLATFORM_PUBLIC_URL', '').rstrip('/')
    parsed = urlsplit(raw)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Configure PLATFORM_PUBLIC_URL as the HTTPS dashboard URL for authenticated approval links.')
    return raw


def optional_public_url():
    try:
        return public_url()
    except ValueError:
        return None


def approval_configuration(step):
    raw = (step.params or {}).get('human_approval')
    if raw is None:
        return None
    config = HumanApproval.model_validate(raw)
    if config.merge_after_approval and config.kind != 'pull_requests':
        raise ValueError('Automatic merge requires a pinned pull-request approval gate.')
    if step.params.get('channel_action') or step.params.get('workspace'):
        raise ValueError('Approval steps cannot also execute channel actions or repository workspaces.')
    # Reuse deterministic exact channel/tool/dependency validation.
    from dataclasses import replace
    params = {**step.params, 'channel_action': ChannelAction(action='send_channel_message',
              connector_id=config.connector_id, channel_id=config.channel_id,
              source_step=config.source_step).model_dump()}
    action_configuration(replace(step, params=params))
    return config


def validate_gates(definition):
    from .dag_approval_config import dag_approval_policy
    for step in definition.steps:
        dag_approval_policy(step)
    gates = [(step, approval_configuration(step)) for step in definition.steps]
    gates = [(step, config) for step, config in gates if config]
    if not gates:
        return
    if len(gates) != 1:
        raise ValueError('Use one terminal approval gate per workflow; it can approve a bounded PR batch.')
    gate, config = gates[0]
    mapping = {step.key: step for step in definition.steps}
    ancestors, pending = set(), list(gate.depends_on)
    while pending:
        key = pending.pop()
        if key in ancestors:
            continue
        if key not in mapping or key == gate.key:
            raise ValueError('Invalid approval dependency graph.')
        ancestors.add(key)
        pending.extend(mapping[key].depends_on)
    if ancestors != set(mapping) - {gate.key}:
        raise ValueError('The approval gate must be terminal and depend on all other work, directly or indirectly.')
    if config.source_step not in ancestors:
        raise ValueError('The approval source must precede the gate.')
