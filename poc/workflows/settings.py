"""Per-workflow execution settings stored in the definition under `settings`.

model: "default", a tier ID ("tier:developer") or a catalog model ID; the runtime's
       existing resolution maps it to the active provider (no names hardcoded here).
machine_size: sandbox container preset for repository-workspace steps.
network_allowlist: exact HTTPS hostnames the sandbox may reach through the egress proxy.
Secret values never live here; see integrations/workflow_secrets.py.
"""
import re
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

MACHINE_SIZES: Dict[str, Dict[str, str]] = {
    'small': {'cpus': '1', 'memory': '1g', 'pids': '128'},
    'medium': {'cpus': '2', 'memory': '4g', 'pids': '256'},
    'large': {'cpus': '4', 'memory': '8g', 'pids': '512'},
}
DEFAULT_MACHINE_SIZE = 'medium'
MAX_ALLOWED_HOSTS = 20
_HOSTNAME = re.compile(r'(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')


class WorkflowSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    machine_size: Literal['small', 'medium', 'large'] = DEFAULT_MACHINE_SIZE
    network_allowlist: List[str] = Field(default_factory=list, max_length=MAX_ALLOWED_HOSTS)

    @field_validator('network_allowlist')
    @classmethod
    def _hosts(cls, hosts: List[str]) -> List[str]:
        normalized = []
        for host in hosts:
            value = host.strip().lower().rstrip('.')
            # Hostnames only: no IPs, ports, schemes, paths or wildcards.
            if not _HOSTNAME.fullmatch(value):
                raise ValueError(f'Invalid allowlisted host: {host!r}. Use an exact hostname such as api.example.com.')
            if value not in normalized:
                normalized.append(value)
        return normalized


def allowed_models() -> set:
    from runtime.model_policy import model_policy_resolver
    from runtime.direct_config import PROVIDER_MODELS
    ids = {'default'} | {tier['id'] for tier in model_policy_resolver.list_tiers()}
    for models in PROVIDER_MODELS.values():
        ids.update(model['id'] for model in models)
    return ids


def validate_settings(raw) -> WorkflowSettings:
    settings = WorkflowSettings.model_validate(raw or {})
    if settings.model is not None and settings.model not in allowed_models():
        raise ValueError(f'Unknown model {settings.model!r}; choose a tier or a model from the catalog.')
    return settings


def settings_for_workflow(workflow) -> WorkflowSettings:
    """Settings of a saved workflow; invalid stored settings fail closed rather than run with defaults."""
    import json
    definition = json.loads(workflow.definition_json) if workflow and workflow.definition_json else {}
    return validate_settings(definition.get('settings'))


def model_for_task(db, task_id: str) -> Optional[str]:
    """Model override for a workflow step task; None keeps the agent's own model.

    Invalid stored settings raise, so the step fails instead of silently using another model.
    """
    if not task_id.startswith('wf_task_'):
        return None
    with db._get_connection() as conn:
        row = conn.execute('SELECT e.workflow_id FROM workflow_step_runs s JOIN workflow_executions e '
                           'ON e.id = s.execution_id WHERE s.task_run_id = ?', (task_id,)).fetchone()
    workflow = db.get_workflow(row['workflow_id']) if row else None
    if not workflow:
        return None
    model = settings_for_workflow(workflow).model
    return None if model in (None, 'default') else model
