"""Server-owned open PR discovery and bounded review input."""
import json
from datetime import datetime

from runtime.models import TaskStatus
from integrations.tool_executor import WorkflowToolExecutor
from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    eligible_pull_numbers: list[PositiveInt] = Field(max_length=10)
    findings: str = Field(min_length=1, max_length=40000)

    @classmethod
    def parse_output(cls, report):
        # Some providers emit literal line breaks inside the JSON findings string.
        if any(ord(char) < 32 and char not in '\n\r\t' for char in report):
            raise ValueError('Invalid control character in PR review report.')
        return cls.model_validate(json.loads(report, strict=False))


EMPTY_REVIEW = '{"eligible_pull_numbers":[],"findings":"No matching open pull requests."}'
REVIEW_FORMAT = (
    'In the completion tool arguments, set eligible_pull_numbers to the PR numbers that passed your review '
    'and output to plain-text findings with one or two lines per PR and any deferred PR numbers. '
    'Summarize the decision and concrete blockers. Do not reproduce patches or enumerate successful checks. '
    'Exclude any PR with breaking changes or missing evidence from eligible_pull_numbers.'
    ' Use approval_ready and observed_ci_passed for the approval decision. Report branch protection, '
    'required-check policy and GitHub review limitations separately as potential merge blockers. '
    'A major version bump warrants investigation but does not by itself prove a breaking change.'
)


def discover(db, task, author):
    executor = WorkflowToolExecutor(db, task.run_id)
    entries = list(executor.entries.values())
    if len(entries) != 1 or entries[0]['operation'] != 'list_open_pull_requests' or len(entries[0]['repositories']) != 1:
        raise ValueError('PR discovery requires one explicit open-PR tool and repository.')
    entry = entries[0]
    result = executor.call(entry['name'], {'repository': entry['repositories'][0], 'author': author})
    executor.verify_completion()
    if result.get('partial') is not False:
        raise ValueError('Open PR discovery was incomplete. Review was stopped.')
    return json.dumps(result['pull_requests'], ensure_ascii=False)


def finish(db, task, output):
    current = db.get_task_run(task.run_id)
    if not current or current.status != TaskStatus.RUNNING:
        raise ValueError('PR batch task is no longer running.')
    current.status = TaskStatus.COMPLETED
    current.result = output
    current.ended_at = datetime.now()
    db.save_task_run(current)


def review_candidates(db, execution_id, step):
    source = step.params.get('open_pr_source')
    if source not in step.depends_on:
        raise ValueError('Open PR review requires an explicit discovery dependency.')
    refs = step.params.get('authorized_resources', [])
    if len(refs) != 1 or refs[0].get('tool_name') != 'get_pull_request_review':
        raise ValueError('Open PR review requires one aggregate review tool and repository.')
    with db._get_connection() as conn:
        calls = conn.execute("""SELECT c.result, c.arguments FROM workflow_step_runs s
            JOIN mcp_tool_calls c ON c.task_id=s.task_run_id
            JOIN mcp_tools t ON t.id=c.tool_id
            WHERE s.execution_id=? AND s.step_key=? AND s.status='COMPLETED'
              AND c.status='COMPLETED' AND c.connector_id=? AND t.name='list_open_pull_requests'
              AND json_extract(c.arguments,'$.repository')=? AND json_extract(c.arguments,'$.author') IS NOT NULL
              AND c.id LIKE 'call_exec_%'""",
            (execution_id, source, refs[0]['connector_id'], refs[0]['repository'])).fetchall()
    if len(calls) != 1:
        raise ValueError('Open PR review requires exactly one successful filtered discovery receipt.')
    receipt = json.loads(calls[0]['result'])
    author = json.loads(calls[0]['arguments'])['author']
    pulls = receipt.get('pull_requests')
    if receipt.get('partial') is not False or not isinstance(pulls, list) or any(
            not isinstance(pull, dict) or type(pull.get('number')) is not int
            or pull.get('state') != 'open' or pull.get('author') != author for pull in pulls):
        raise ValueError('Open PR discovery returned invalid candidates.')
    return author, list(dict.fromkeys(pull['number'] for pull in pulls))
