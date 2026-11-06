"""Explicitly granted, head-pinned PR comments/reviews; never model-supplied approval."""
from datetime import datetime, timezone
import re
from .github_prs import GitHubReads
from .github_pr_evidence import pinned_pull
from .provider_http import request_json
from .tool_definitions import ToolAccessError


def execute_write(configuration, operation, inputs, authorize):
    if operation not in ('comment_pull_request', 'review_pull_request'):
        raise ToolAccessError('Unknown GitHub PR write operation.')
    client = GitHubReads(configuration, inputs.repository, authorize)
    _, pull = pinned_pull(client, inputs.pull_number)
    if pull['state'] != 'open' or pull['head']['sha'] != inputs.head_sha:
        raise ToolAccessError('PR is not open at the requested head. Re-read it before writing.')
    review = operation == 'review_pull_request'
    suffix = f'pulls/{inputs.pull_number}/reviews' if review else f'issues/{inputs.pull_number}/comments'
    body = inputs.body if review else f'Workflow comment for commit {inputs.head_sha}:\n\n{inputs.body}'
    payload = {'body': body}
    if review:
        payload.update(commit_id=inputs.head_sha, event=inputs.event)
    authorize()
    value = request_json('api.github.com', f'/repos/{inputs.repository}/{suffix}', client.headers,
                         payload=payload, accepted=(200, 201), method='POST')
    expected_state = {'COMMENT': 'COMMENTED', 'REQUEST_CHANGES': 'CHANGES_REQUESTED'}
    if (not isinstance(value, dict) or type(value.get('id')) is not int or value['id'] <= 0
            or value.get('body') != body or not isinstance((value.get('user') or {}).get('login'), str)
            or not re.fullmatch(r'[A-Za-z0-9_\[\]-]{1,100}', value['user']['login'])
            or (review and (value.get('commit_id') != inputs.head_sha or value.get('state') != expected_state[inputs.event]))):
        raise ToolAccessError('GitHub did not confirm the PR write identity. Outcome may be unknown; no automatic retry.')
    # A comment endpoint cannot atomically pin HEAD; its body names the reviewed SHA.
    # A post-write revocation must not erase the acknowledged receipt or cause a retry.
    return {'repository': inputs.repository, 'pull_number': inputs.pull_number, 'head_sha': inputs.head_sha,
            'operation': operation, 'status': 'COMPLETED', 'provider_id': value['id'],
            'provider_actor': str(value['user']['login'])[:100],
            'url': f'https://github.com/{inputs.repository}/pull/{inputs.pull_number}#' +
                   (f"pullrequestreview-{value['id']}" if review else f"issuecomment-{value['id']}"),
            'completed_at': datetime.now(timezone.utc).isoformat(), 'untrusted_external_data': True}
