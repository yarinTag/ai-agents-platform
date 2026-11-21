"""Exact GitHub write intent shared by workflow authoring and approval execution."""
import hashlib
import json
import time
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from integrations.tool_definitions import (
    PullRequestCommentInput,
    PullRequestReviewInput,
    ToolAccessError,
    valid_repository,
)


class CommentIntent(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    operation: Literal['comment_pull_request']
    arguments: PullRequestCommentInput


class ReviewIntent(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    operation: Literal['review_pull_request']
    arguments: PullRequestReviewInput


class PRWriteApproval(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    connector_id: str = Field(min_length=1, max_length=200)
    approval_step: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')
    intent: Annotated[CommentIntent | ReviewIntent, Field(discriminator='operation')]

    @model_validator(mode='after')
    def visible_body(self):
        body = self.intent.arguments.body
        if len(body) > 1000 or any(unicodedata.category(char) in {'Cc', 'Cf', 'Cs'}
                                   and char not in '\n\t' for char in body):
            raise ValueError('An exact PR write requires a visible body of at most 1,000 characters.')
        return self

    def fingerprint(self, step_key):
        value = {'step_key': step_key, **self.model_dump(mode='json')}
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()

    def describe(self):
        arguments = self.intent.arguments
        action = self.intent.operation
        if isinstance(self.intent, ReviewIntent):
            action += f' ({arguments.event})'
        else:
            action += ' (comment about the reviewed commit)'
        return (f"GitHub {action}\n{arguments.repository} #{arguments.pull_number}\n"
                f"Pinned head: {arguments.head_sha}\n\n{arguments.body}")


def write_configuration(step):
    params = step.params or {}
    if 'pr_write_approval' not in params:
        return None
    config = PRWriteApproval.model_validate(params['pr_write_approval'])
    arguments = config.intent.arguments
    if (set(params) != {'pr_write_approval', 'authorized_resources'}
            or list(step.mcp_servers) != [config.connector_id]
            or params['authorized_resources'] != [{
                'connector_id': config.connector_id,
                'repository': arguments.repository,
                'tool_name': config.intent.operation,
            }]
            or config.approval_step not in step.depends_on
            or not valid_repository(arguments.repository)):
        raise ToolAccessError('An exact PR write must depend on its approval and declare one matching repository tool.')
    return config



def approval_manifest(definition, approval_key):
    actions = []
    for step in definition.steps:
        config = write_configuration(step)
        if config and config.approval_step == approval_key:
            actions.append({'step_key': step.key, 'fingerprint': config.fingerprint(step.key),
                            'description': config.describe()})
    if len(actions) > 1:
        raise ToolAccessError('Each exact PR write requires its own approval checkpoint.')
    return actions[0] if actions else None


def validate_write_gates(definition):
    from .dag_approval_config import dag_approval_policy

    checkpoints = {step.key: step for step in definition.steps if dag_approval_policy(step)}
    for step in definition.steps:
        config = write_configuration(step)
        if config:
            gate = checkpoints.get(config.approval_step)
            if gate is None:
                raise ToolAccessError('An exact PR write must depend on a durable DAG approval checkpoint.')
            if dag_approval_policy(gate).mode != 'INDEPENDENT':
                raise ToolAccessError('An exact PR write requires INDEPENDENT approval.')
    for key in checkpoints:
        approval_manifest(definition, key)


def execute_approved_write(db, step, config, task, execution_id):
    from integrations.tool_executor import WorkflowToolExecutor
    from integrations.tool_scopes import prepare_scope
    from storage.dag_approvals import _eligible
    from .pull_request_batch import finish

    def authorize():
        with db._get_connection() as conn:
            approval = conn.execute("""SELECT a.* FROM workflow_dag_approvals a
                JOIN workflow_executions x ON x.id=a.execution_id AND x.status='RUNNING'
                JOIN workflows w ON w.id=x.workflow_id AND w.revision=a.workflow_revision
                    AND w.organization_id=a.organization_id AND w.department_id=a.department_id
                WHERE a.execution_id=? AND a.step_key=? AND a.status='CLAIMED' AND a.expires_at>?""",
                (execution_id, config.approval_step, int(time.time()))).fetchone()
            if not approval:
                raise ToolAccessError('The exact GitHub write has no live claimed approval.')
            manifest = json.loads(approval['checkpoint_json']).get('approved_pr_write') or {}
            if (manifest.get('step_key'), manifest.get('fingerprint')) != (step.key, config.fingerprint(step.key)):
                raise ToolAccessError('The GitHub write differs from the approved action.')
            policy = json.loads(approval['policy_json'])
            from .dag_approval_config import approval_mode
            if approval_mode(policy) != 'INDEPENDENT':
                raise ToolAccessError('An exact PR write requires INDEPENDENT approval.')
            votes = conn.execute('SELECT user_id FROM workflow_dag_approval_votes WHERE approval_id=? AND decision=1',
                                 (approval['id'],)).fetchall()
            if sum(_eligible(conn, approval, policy, vote['user_id']) for vote in votes) < policy['quorum']:
                raise ToolAccessError('The authorized approval quorum for the GitHub write is no longer met.')

    authorize()
    prepare_scope(db, task.run_id, execution_id, step, approval_check=authorize)
    executor = WorkflowToolExecutor(db, task.run_id, approval_check=authorize)
    entry, = executor.entries.values()
    receipt = executor.call(entry['name'], config.intent.arguments.model_dump())
    executor.verify_completion()
    finish(db, task, json.dumps(receipt, ensure_ascii=False))
