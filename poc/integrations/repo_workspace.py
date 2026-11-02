"""Governed GitHub repository workspaces: policy, clone and draft pull requests.

The backend clones and publishes; the model only edits files inside a Docker
sandbox (workflows.repo_sandbox). Git metadata lives outside the sandbox mount,
credentials travel only in per-command environment variables, and publication
creates a new branch plus a draft pull request. Nothing is pushed to an existing
branch and nothing is merged; merging stays a human decision on GitHub.
"""
import base64
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from .provider_http import request_json
from .tool_definitions import ToolAccessError, require_credentials, resource_values, valid_repository
from .tool_scopes import agent_tool_allowed, connector_authorized, execution_context, require_initiator

logger = logging.getLogger(__name__)

CLONE_OPERATION = 'clone_repository'
PUBLISH_OPERATION = 'open_pull_request'
OPERATIONS = {
    CLONE_OPERATION: 'Clone an approved GitHub repository into an isolated workflow sandbox.',
    PUBLISH_OPERATION: 'Push sandbox changes to a new branch and open a draft pull request.',
}
# Pushing these could run agent-written CI with repository secrets before review.
BLOCKED_PREFIXES = ('.github/workflows/', '.github/actions/')
BLOCKED_FILES = ('.gitmodules',)
MAX_CHANGED_FILES = 200
MAX_CHANGED_LINES = 50000
_REF = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,199}')
_TOKEN_KEYS = ('token', 'personal_access_token', 'api_key', 'GITHUB_PERSONAL_ACCESS_TOKEN')
_ROOT = Path(tempfile.gettempdir()) / 'ai_agents_repo_workspaces'


class RepositoryWorkspace(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    connector_id: str = Field(min_length=1, max_length=200)
    repository: str = Field(min_length=3, max_length=150)
    ref: Optional[str] = Field(default=None, min_length=1, max_length=200)
    mode: Literal['read', 'write'] = 'read'
    pr_title: Optional[str] = Field(default=None, min_length=1, max_length=200)


def workspace_configuration(step):
    raw = (step.params or {}).get('workspace')
    if raw is None:
        if (step.params or {}).get('required_outcome') == 'pull_request':
            raise ValueError('A required pull request needs a write repository workspace.')
        return None
    parsed = RepositoryWorkspace.model_validate(raw)
    if (step.params or {}).get('required_outcome') == 'pull_request' and parsed.mode != 'write':
        raise ValueError('A required pull request needs a write repository workspace.')
    if not valid_repository(parsed.repository):
        raise ValueError('Workspace repository must be an exact owner/repo name.')
    if parsed.ref is not None and (not _REF.fullmatch(parsed.ref) or '..' in parsed.ref
            or '//' in parsed.ref or parsed.ref.endswith(('/', '.lock'))):
        raise ValueError('Workspace ref must be a plain branch or tag name.')
    if step.mcp_servers:
        raise ValueError('A repository workspace step cannot also declare connector tools.')
    if (step.params or {}).get('channel_action') is not None:
        raise ValueError('A repository workspace step cannot be a channel delivery action.')
    return parsed


def _tool(db, connector, operation):
    """Implementation metadata for audit/agent checks; never a model-callable tool or a grant."""
    identifier = 'tool_repo_' + hashlib.sha256(f'{connector.id}:{operation}'.encode()).hexdigest()[:24]
    return db.get_mcp_tool(identifier) or db.save_mcp_tool({'id': identifier, 'connector_id': connector.id,
        'name': operation, 'description': OPERATIONS[operation], 'input_schema': {'type': 'object'}})


def authorize_workspace(db, execution_id, step, config):
    """Recheck current tenant, initiator, connector, repository and grants. Returns (connector, agent)."""
    execution = db.get_workflow_execution(execution_id)
    workflow = db.get_workflow(execution.workflow_id) if execution else None
    agent = db.get_agent(step.agent_id)
    if not workflow or not workflow.organization_id or not workflow.department_id or not agent:
        raise ToolAccessError('Repository workspaces require an organization, department and configured agent.')
    if execution.trigger_type == 'PLAYGROUND':
        raise ToolAccessError('Playground cannot receive repository workspaces.')
    organization_id, department_id = workflow.organization_id, workflow.department_id
    if agent.organization_id != organization_id or agent.department_id not in (None, department_id):
        raise ToolAccessError('Execution agent is outside this workflow department.')
    context = execution_context(db, execution_id)
    if not context:
        raise ToolAccessError('Workflow execution context is missing.')
    require_initiator(db, context.get('initiator_id'), organization_id, department_id)
    connector = connector_authorized(db, config.connector_id, organization_id, department_id, agent)
    if connector.provider.lower() != 'github':
        raise ToolAccessError('Repository workspaces require a GitHub connector.')
    require_credentials(connector)
    if config.repository not in resource_values(connector.configuration or {}, 'repositories'):
        raise ToolAccessError('The repository is not on this connector\'s approved repository list.')
    operations = [CLONE_OPERATION] + ([PUBLISH_OPERATION] if config.mode == 'write' else [])
    for operation in operations:
        permission = db.check_department_mcp_permission(department_id, connector.id, operation)
        if not permission.get('allowed'):
            raise ToolAccessError(f'The department is not granted {operation} on this connector.')
        if operation == PUBLISH_OPERATION and '*' in (permission.get('allowed_tools') or []):
            raise ToolAccessError('Opening pull requests requires an explicit open_pull_request grant; '
                'wildcard grants do not cover repository writes.')
        if not agent_tool_allowed(db, agent, connector, _tool(db, connector, operation)):
            raise ToolAccessError(f'The execution agent is not allowed to use {operation}.')
    budget = db.check_department_budget(department_id)
    if not budget.get('allowed'):
        raise ToolAccessError('Department budget does not permit repository work.')
    return connector, agent


def _token(connector):
    config = connector.configuration or {}
    token = next((config[key].strip() for key in _TOKEN_KEYS
                  if isinstance(config.get(key), str) and config[key].strip()), None)
    if not token:
        raise ToolAccessError('The GitHub connector has no configured access token.')
    return token


def _git_env(worktree, token=None):
    """Ignore system/global config, hooks and credential helpers; the token lives only in this env."""
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(worktree.parent), 'LC_ALL': 'C',
           'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
    settings = [('core.hooksPath', os.devnull), ('core.fsmonitor', 'false'), ('core.symlinks', 'false'),
                ('protocol.allow', 'never'), ('protocol.https.allow', 'always'), ('submodule.recurse', 'false'),
                ('credential.helper', ''), ('http.followRedirects', 'false'), ('safe.directory', str(worktree))]
    if token:
        basic = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
        settings.append(('http.https://github.com/.extraHeader', 'Authorization: Basic ' + basic))
    env['GIT_CONFIG_COUNT'] = str(len(settings))
    for index, (key, value) in enumerate(settings):
        env[f'GIT_CONFIG_KEY_{index}'], env[f'GIT_CONFIG_VALUE_{index}'] = key, value
    return env


def _run(args, env, timeout=180):
    try:
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ToolAccessError('A git operation timed out.') from exc
    if result.returncode != 0:
        # git output can echo remote URLs; never surface it, only log the exit status.
        logger.warning('git command failed with exit code %s', result.returncode)
        raise ToolAccessError('A git operation failed (exit code %s). Check the ref, repository access and token scope.'
                              % result.returncode)
    return result.stdout


def _git(workspace, *args, token=None, timeout=180):
    worktree, gitdir = Path(workspace['worktree']), Path(workspace['gitdir'])
    # Explicit --git-dir/--work-tree: a .git file written by sandboxed code is ignored.
    return _run(['git', f'--git-dir={gitdir}', f'--work-tree={worktree}', *args],
                _git_env(worktree, token), timeout)


def _audit(db, task_id, agent_id, connector, operation, arguments):
    identifier = 'call_repo_' + hashlib.sha256(f'{task_id}:{operation}'.encode()).hexdigest()
    if db.get_mcp_tool_call(identifier):
        raise ToolAccessError(f'{operation} was already attempted for this step; it will not be repeated automatically.')
    db.save_mcp_tool_call({'id': identifier, 'connector_id': connector.id, 'tool_id': _tool(db, connector, operation).id,
        'agent_id': agent_id, 'task_id': task_id, 'run_id': task_id, 'status': 'STARTED',
        'arguments': arguments, 'started_at': datetime.now().isoformat()})
    return identifier


def _finish(db, identifier, result=None, error=None):
    db.update_mcp_tool_call(identifier, status='FAILED' if error else 'COMPLETED',
        result=json.dumps(result) if result is not None else None, error=error,
        completed_at=datetime.now().isoformat())


def open_workspace(db, task_id, execution_id, step, config):
    """Authorize, clone and start the sandbox container. Fails closed without Docker."""
    from workflows.repo_sandbox import (proxy_image, remove_container, remove_egress, require_docker,
                                        sandbox_image, start_container, start_egress)
    from workflows.settings import MACHINE_SIZES, settings_for_workflow
    from .workflow_secrets import resolve_workflow_secrets
    connector, agent = authorize_workspace(db, execution_id, step, config)
    workflow = db.get_workflow(db.get_workflow_execution(execution_id).workflow_id)
    try:
        settings = settings_for_workflow(workflow)
    except ValueError as exc:
        raise ToolAccessError(f'Workflow settings are invalid: {exc}') from exc
    image = sandbox_image()
    egress_image = proxy_image() if settings.network_allowlist else None
    require_docker()
    secrets = resolve_workflow_secrets(db, workflow)  # Fails the step rather than starting without them.
    audit = _audit(db, task_id, agent.id, connector, CLONE_OPERATION,
                   {'repository': config.repository, 'ref': config.ref, 'mode': config.mode})
    _ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='ws_', dir=_ROOT))
    workspace = {'task_id': task_id, 'execution_id': execution_id, 'step_key': step.key,
        'connector_id': connector.id, 'repository': config.repository, 'mode': config.mode,
        'pr_title': config.pr_title, 'root': str(root), 'worktree': str(root / 'repo'),
        'gitdir': str(root / 'git'), 'cwd': str(root / 'cwd'), 'container': None, 'state': 'ACTIVE',
        'machine_size': settings.machine_size, 'egress': None, 'secret_names': sorted(secrets),
        'redactions': None}
    try:
        # The worker's cwd is on its import path; it must never be the untrusted checkout.
        Path(workspace['cwd']).mkdir(mode=0o700)
        from .repo_cache import checkout_repository
        token = _token(connector)

        def authorize_cache_use():
            current, _ = authorize_workspace(db, execution_id, step, config)
            execution = db.get_workflow_execution(execution_id)
            task = db.get_task_run(task_id)
            state = str(getattr(task.status, 'value', task.status)).lower() if task else ''
            if not execution or execution.status != 'RUNNING' or state != 'running':
                raise ToolAccessError('Repository checkout was cancelled or is no longer running.')
            if _token(current) != token:
                raise ToolAccessError('Repository credentials changed during checkout; start a new execution.')

        cache_root = os.environ.get('PLATFORM_REPO_CACHE_DIR') or str(Path(db.db_path).resolve().parent / 'repo_cache')
        workspace['repository_cache'] = checkout_repository(
            cache_root, workflow.organization_id, connector.id, config.repository, config.ref,
            root / 'repo', root / 'git', run=_run, git_env=_git_env, token=token,
            authorize=authorize_cache_use)
        workspace['commit'] = _git(workspace, 'rev-parse', 'HEAD').strip()
        try:
            workspace['base_branch'] = _git(workspace, 'symbolic-ref', '--short', 'HEAD').strip()
        except ToolAccessError:
            workspace['base_branch'] = None  # A tag checkout is detached.
        if config.mode == 'write' and not workspace['base_branch']:
            raise ToolAccessError('Write workspaces need a branch ref as the pull request base, not a tag.')
        if secrets:
            # Host-only (never mounted) 0600 file so the worker can redact values from tool output.
            redactions = root / 'redactions.json'
            descriptor = os.open(redactions, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as handle:
                json.dump(secrets, handle)
            workspace['redactions'] = str(redactions)
        if egress_image:
            workspace['egress'] = start_egress(settings.network_allowlist, egress_image)
        workspace['container'] = start_container(root / 'repo', image, MACHINE_SIZES[settings.machine_size],
                                                 secrets, workspace['egress'])
        with db._get_connection() as conn:
            conn.execute('INSERT INTO workflow_repo_workspaces(task_id, execution_id, workspace_json) VALUES (?, ?, ?)',
                         (task_id, execution_id, json.dumps(workspace)))
        _finish(db, audit, {'repository': config.repository, 'commit': workspace['commit'],
                            'base_branch': workspace['base_branch'], 'repository_cache': workspace['repository_cache']})
        return workspace
    except Exception as exc:
        _finish(db, audit, error=str(exc) if isinstance(exc, ToolAccessError) else 'Workspace preparation failed.')
        if workspace['container']:
            remove_container(workspace['container'])
        remove_egress(workspace['egress'])
        shutil.rmtree(root, ignore_errors=True)
        raise


def load_workspace(db, task_id):
    with db._get_connection() as conn:
        row = conn.execute('SELECT workspace_json FROM workflow_repo_workspaces WHERE task_id=?', (task_id,)).fetchone()
    return json.loads(row['workspace_json']) if row else None


def step_requires_workspace(db, task_id):
    """A workflow task whose step declares a workspace must never launch without one."""
    with db._get_connection() as conn:
        row = conn.execute('SELECT execution_id,step_key FROM workflow_step_runs WHERE task_run_id=?', (task_id,)).fetchone()
    execution = db.get_workflow_execution(row['execution_id']) if row else None
    workflow = db.get_workflow(execution.workflow_id) if execution else None
    if not workflow:
        return False
    from workflows.parser import WorkflowParser
    definition = WorkflowParser.from_json(workflow.definition_json)
    step = next((s for s in definition.steps if s.key == row['step_key']), None)
    return bool(step and (step.params or {}).get('workspace') is not None)


def close_workspace(db, workspace):
    from workflows.repo_sandbox import remove_container, remove_egress
    if workspace.get('container'):
        remove_container(workspace['container'])
    remove_egress(workspace.get('egress'))
    shutil.rmtree(workspace['root'], ignore_errors=True)
    workspace['state'] = 'RELEASED'
    with db._get_connection() as conn:
        conn.execute('UPDATE workflow_repo_workspaces SET workspace_json=? WHERE task_id=?',
                     (json.dumps(workspace), workspace['task_id']))


def _slug(value, limit):
    return re.sub(r'[^a-z0-9-]+', '-', str(value).lower()).strip('-')[:limit] or 'step'


def _fenced(text):
    """Untrusted model text inside a code fence: no mentions, links or markup reach GitHub."""
    longest = max((len(m) for m in re.findall(r'`+', text)), default=0)
    fence = '`' * max(3, longest + 1)
    return f'{fence}text\n{text}\n{fence}'


def _reject_secret_values(workspace, names):
    """Never push a workflow secret: refuse if any changed file contains a secret value."""
    if not workspace.get('redactions'):
        return
    with open(workspace['redactions']) as handle:
        values = [(name, value.encode()) for name, value in json.load(handle).items() if len(value) >= 4]
    worktree = Path(workspace['worktree']).resolve()
    for name in names:
        path = worktree / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(worktree):
            continue
        if path.stat().st_size > 5_000_000:
            raise ToolAccessError(f'{name} is too large to check for secrets; it was not published.')
        content = path.read_bytes()
        leaked = [secret for secret, value in values if value in content]
        if leaked:
            raise ToolAccessError(f'{name} contains the value of workflow secret(s) {", ".join(leaked)}; nothing was published.')


def publish_workspace(db, step, workspace, summary):
    """Commit all sandbox changes, push a new branch and open a draft PR. Returns a receipt."""
    config = RepositoryWorkspace(connector_id=workspace['connector_id'], repository=workspace['repository'],
                                 mode='write', pr_title=workspace.get('pr_title'))
    _git(workspace, 'add', '--all', '--', '.')
    names = [n for n in _git(workspace, 'diff', '--cached', '--name-only', '-z').split('\0') if n]
    if not names:
        return {'changed': False, 'pull_request_url': None}
    if any(n.startswith(BLOCKED_PREFIXES) or n in BLOCKED_FILES for n in names):
        raise ToolAccessError('Changes to CI workflows, actions or submodules are never published automatically.')
    if len(names) > MAX_CHANGED_FILES:
        raise ToolAccessError(f'The change touches more than {MAX_CHANGED_FILES} files; it was not published.')
    _reject_secret_values(workspace, names)
    lines = 0
    for row in _git(workspace, 'diff', '--cached', '--numstat').splitlines():
        added, removed = row.split('\t')[:2]
        lines += (int(added) if added.isdigit() else 0) + (int(removed) if removed.isdigit() else 0)
    if lines > MAX_CHANGED_LINES:
        raise ToolAccessError(f'The change exceeds {MAX_CHANGED_LINES} changed lines; it was not published.')
    execution = db.get_workflow_execution(workspace['execution_id'])
    branch = f'agent/{_slug(execution.workflow_id, 60)}/{_slug(execution.id, 40)}-{_slug(step.key, 40)}'
    _git(workspace, 'check-ref-format', '--branch', branch)
    title = config.pr_title or f'[agent] {step.name or step.key}'
    _git(workspace, '-c', 'user.name=AI Agents Platform',
         '-c', 'user.email=ai-agents-platform@users.noreply.github.com',
         'commit', '--no-verify', '--no-gpg-sign', '-m', title,
         '-m', f'Workflow {execution.workflow_id}, execution {execution.id}, step {step.key}.')
    commit = _git(workspace, 'rev-parse', 'HEAD').strip()
    connector, agent = authorize_workspace(db, workspace['execution_id'], step, config)
    audit = _audit(db, workspace['task_id'], agent.id, connector, PUBLISH_OPERATION,
                   {'repository': config.repository, 'branch': branch, 'base': workspace['base_branch'],
                    'commit': commit, 'changed_files': len(names)})
    try:
        token = _token(connector)
        # An empty lease value asserts the branch does not exist: never overwrite or force-push.
        _git(workspace, 'push', '--no-verify', f'--force-with-lease=refs/heads/{branch}:',
             f'https://github.com/{config.repository}.git', f'HEAD:refs/heads/{branch}', token=token)
        authorize_workspace(db, workspace['execution_id'], step, config)
        body = ('Opened automatically by an AI Agents Platform workflow as a **draft**. '
                'It needs human review and approval before merging.\n\n'
                f'- Workflow: `{execution.workflow_id}`\n- Execution: `{execution.id}`\n- Step: `{step.key}`\n'
                f'- Base commit: `{workspace["commit"]}`\n\nAgent summary (untrusted model output):\n\n'
                + _fenced((summary or 'No summary provided.')[:20000]))
        response = request_json('api.github.com', f'/repos/{config.repository}/pulls',
            {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
             'X-GitHub-Api-Version': '2026-03-10'},
            payload={'title': title, 'head': branch, 'base': workspace['base_branch'], 'body': body, 'draft': True},
            accepted=(201,))
        url = response.get('html_url') if isinstance(response, dict) else None
        if not isinstance(url, str) or not url.startswith(f'https://github.com/{config.repository}/pull/'):
            raise ToolAccessError('GitHub returned an unexpected pull request response.')
        receipt = {'changed': True, 'branch': branch, 'commit': commit, 'changed_files': len(names),
                   'pull_request_url': url, 'pull_request_number': response.get('number'), 'draft': True}
        _finish(db, audit, receipt)
        return receipt
    except ToolAccessError as exc:
        _finish(db, audit, error=str(exc))
        raise
    except Exception as exc:
        _finish(db, audit, error='Pull request publication failed.')
        raise ToolAccessError('Pull request publication failed; the branch may exist without a PR.') from exc
