"""Read-only first slice: explicit configuration, frozen identity and live policy."""
import os
import re
import time
import sys
from dataclasses import dataclass

from integrations.repo_workspace import authorize_workspace, load_workspace, workspace_configuration
from integrations.tool_scopes import execution_context
from storage.runtime_settings import OrganizationRuntimeSettings

SDK_VERSION = '0.2.177'
IMAGE_ENV = 'PLATFORM_CLAUDE_SDK_IMAGE'
TOOLS = ('Read', 'Glob', 'Grep')
IMAGE_PATTERN = re.compile(r'[a-z0-9][a-z0-9._/:-]{0,255}@sha256:[0-9a-f]{64}')


def configured_image():
    if os.getenv('PLATFORM_ENABLE_CLAUDE_SDK', '').lower() != 'true':
        raise ValueError('Claude Agent SDK is disabled. Set PLATFORM_ENABLE_CLAUDE_SDK=true after deployment verification.')
    image = os.getenv(IMAGE_ENV, '').strip()
    if sys.platform != 'linux' or not IMAGE_PATTERN.fullmatch(image):
        raise ValueError('Claude Agent SDK requires a native Linux Docker host and digest-pinned PLATFORM_CLAUDE_SDK_IMAGE.')
    return image


def require_read_workspace(step, settings):
    config = workspace_configuration(step)
    if config is None or config.mode != 'read':
        raise ValueError('Claude Agent SDK currently requires an explicit read-only repository workspace.')
    if settings.network_allowlist:
        raise ValueError('Claude Agent SDK does not permit tool-network egress in this release.')
    if (step.params or {}).get('reviewerAgentId'):
        raise ValueError('Claude Agent SDK does not yet support automatic reviewer sessions.')
    return config


def read_tools(agent):
    aliases = {'read': 'Read', 'view': 'Read', 'View': 'Read', 'glob': 'Glob', 'grep': 'Grep'}
    configured = set()
    for value in agent.allowed_tools or []:
        if value == '*':
            configured.update(TOOLS)
        else:
            configured.add(aliases.get(value, value))
    tools = tuple(tool for tool in TOOLS if tool in configured)
    if not tools:
        raise ValueError('Claude Agent SDK requires explicit Read, Glob or Grep agent grants.')
    return tools


@dataclass(frozen=True)
class HostedContext:
    task_id: str
    execution_id: str
    workflow_id: str
    organization_id: str
    department_id: str
    step_key: str
    agent_id: str
    credential_version: int
    deadline: float
    model: str
    tools: tuple
    max_tokens: int

    def authorize(self, db):
        if time.monotonic() >= self.deadline:
            raise ValueError('Hosted session expired.')
        task = db.get_task_run(self.task_id)
        execution = db.get_workflow_execution(self.execution_id)
        workflow = db.get_workflow(self.workflow_id)
        agent = db.get_agent(self.agent_id)
        state = str(getattr(task.status, 'value', task.status)).lower() if task else ''
        if (state != 'running' or not execution or execution.status != 'RUNNING' or not workflow
                or execution.workflow_id != self.workflow_id or execution.department_id != self.department_id
                or workflow.organization_id != self.organization_id or workflow.department_id != self.department_id
                or not task or task.organization_id != self.organization_id or task.agent_id != self.agent_id
                or not agent or agent.organization_id != self.organization_id):
            raise ValueError('Hosted run identity is cancelled, revoked or changed.')
        from workflows.parser import WorkflowParser
        from workflows.settings import settings_for_workflow
        from workflows.backend_policy import step_backend
        definition = WorkflowParser.from_json(workflow.definition_json)
        step = next((s for s in definition.steps if s.key == self.step_key), None)
        if not step or step.agent_id != self.agent_id:
            raise ValueError('Hosted workflow step changed.')
        settings = settings_for_workflow(workflow)
        if step_backend(settings, step).value != 'claude_code':
            raise ValueError('Hosted workflow backend changed.')
        config = require_read_workspace(step, settings)
        authorize_workspace(db, self.execution_id, step, config)
        workspace = load_workspace(db, self.task_id)
        if (not workspace or workspace['state'] != 'ACTIVE' or workspace['repository'] != config.repository
                or workspace.get('connector_id') != config.connector_id
                or workspace.get('execution_id') != self.execution_id or workspace.get('mode') != 'read'):
            raise ValueError('Hosted repository workspace is no longer active.')
        if db.list_workflow_secrets(workflow.id):
            raise ValueError('Claude Agent SDK does not accept workflow secrets in this release.')
        if not set(self.tools) <= set(read_tools(agent)):
            raise ValueError('Hosted agent tool grants were revoked.')
        credentials = OrganizationRuntimeSettings(db, self.organization_id)
        if credentials.credential_version('direct_anthropic') != self.credential_version:
            raise ValueError('Organization Anthropic key was revoked or replaced.')
        return workspace, credentials


def context_for_task(db, run, agent, model):
    if not run.run_id.startswith('wf_task_') or not model.startswith('claude-'):
        raise ValueError('Claude Agent SDK requires a workflow repository task and an explicit Claude model.')
    with db._get_connection() as conn:
        row = conn.execute('SELECT execution_id,step_key FROM workflow_step_runs WHERE task_run_id=?',
                           (run.run_id,)).fetchone()
    if not row:
        raise ValueError('Hosted step context is missing.')
    execution = db.get_workflow_execution(row['execution_id'])
    workflow = db.get_workflow(execution.workflow_id) if execution else None
    if not workflow or not workflow.department_id or not execution_context(db, execution.id):
        raise ValueError('Hosted organization/department context is missing.')
    from workflows.parser import WorkflowParser
    definition = WorkflowParser.from_json(workflow.definition_json)
    step = next((s for s in definition.steps if s.key == row['step_key']), None)
    if not step:
        raise ValueError('Hosted step is missing.')
    credentials = OrganizationRuntimeSettings(db, workflow.organization_id)
    version = credentials.credential_version('direct_anthropic')
    if version is None:
        raise ValueError('Configure an Anthropic API key for this organization.')
    context = HostedContext(run.run_id, execution.id, workflow.id, workflow.organization_id,
        workflow.department_id, step.key, agent.id, version,
        time.monotonic() + min(max(step.timeout_seconds, 1), 1800), model, read_tools(agent),
        min(max(agent.max_tokens, 1), 32000))
    context.authorize(db)
    return context


def resolve_sdk_model(agent, credentials):
    from runtime.direct_config import resolve_model_for_provider
    if agent.runtime_provider not in (None, 'direct_anthropic', 'anthropic_api', 'claude_code_native'):
        raise ValueError('Claude Agent SDK cannot use this agent provider override.')
    model = resolve_model_for_provider('direct_anthropic', agent.model, credentials)
    raw = agent.model or 'default'
    if raw not in ('default', 'sonnet', 'opus', 'haiku', 'fable') and not raw.startswith('tier:') and raw != model:
        raise ValueError('Claude Agent SDK model does not match the Anthropic provider.')
    if not model.startswith('claude-'):
        raise ValueError('Claude Agent SDK requires an explicit Claude model.')
    return model


def preflight_hosted(db, workflow, step, settings):
    from dataclasses import replace
    from runtime.direct_pricing import pricing
    agent = db.get_agent(step.agent_id)
    if not agent or agent.organization_id != workflow.organization_id:
        raise ValueError('Hosted agent must exist in the workflow organization.')
    read_tools(agent)
    if db.list_workflow_secrets(workflow.id):
        raise ValueError('Hosted SDK read-only steps do not accept workflow secrets.')
    credentials = OrganizationRuntimeSettings(db, workflow.organization_id)
    if not credentials.resolve_credential('direct_anthropic'):
        raise ValueError('Configure the organization Anthropic API key before hosted execution.')
    if settings.model not in (None, 'default'):
        agent = replace(agent, model=settings.model)
    model = resolve_sdk_model(agent, credentials)
    if pricing('direct_anthropic', model)['rates'] is None:
        raise ValueError('Configure explicit Anthropic token prices before hosted execution.')
