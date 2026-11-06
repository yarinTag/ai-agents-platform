"""Bounded evidence collection; unknown provider policy never becomes merge authority."""
import re
from urllib.parse import quote
from .tool_definitions import ToolAccessError

EVIDENCE_VERSION = 2
SHA = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')


def pinned_pull(client, number):
    from .github_prs import project_pull
    row = client.get(f'pulls/{number}')
    if not isinstance(row, dict) or type(row.get('number')) is not int or row.get('number') != number:
        raise ToolAccessError('GitHub returned an unexpected PR identity.')
    pull = project_pull(row, client.repository)
    if not all(isinstance(pull[key]['sha'], str) and SHA.fullmatch(pull[key]['sha']) for key in ('head', 'base')):
        raise ToolAccessError('GitHub did not return immutable PR revisions.')
    if pull['base']['repository'] != client.repository or not isinstance(pull['base']['ref'], str):
        raise ToolAccessError('GitHub returned an unexpected base repository or branch.')
    return row, pull


def file_evidence(client, number, row):
    files, partial = client.pages(f'pulls/{number}/files')
    partial |= type(row.get('changed_files')) is not int or row.get('changed_files') != len(files)
    result, size = [], 0
    for file in files:
        patch = file.get('patch')
        if not isinstance(patch, str) or size + len(patch) > 60000:
            partial, patch = True, None
        else:
            size += len(patch)
        result.append({**{key: file.get(key) for key in ('filename', 'previous_filename', 'status', 'additions', 'deletions')}, 'patch': patch})
    return result, partial


def branch_policy(client, pull):
    ref = quote(pull['base']['ref'], safe='')
    unknown = {'known': False, 'strict': False, 'enforce_admins': False, 'contexts': [], 'required_approvals': 1}
    try:
        branch = client.get(f'branches/{ref}')
        rules = client.get(f'rules/branches/{ref}')
        if not isinstance(branch, dict) or type(branch.get('protected')) is not bool or not isinstance(rules, list) or len(rules) > 100:
            return unknown
        if branch.get('protected') is not True:
            return {**unknown, 'known': True, 'base_sha': (branch.get('commit') or {}).get('sha')}
        # Classic strict protection with administrator enforcement is the supported
        # no-bypass slice. Ruleset-only/opaque protection remains blocked.
        protection = client.get(f'branches/{ref}/protection')
        status = protection.get('required_status_checks') if isinstance(protection, dict) else None
        if not isinstance(status, dict) or not isinstance(status.get('contexts'), list) or not isinstance(status.get('checks'), list):
            return unknown
        if any(not isinstance(check, dict) or 'app_id' not in check for check in status['checks']): return unknown
        contexts = [{'context': name, 'app_id': None} for name in status['contexts']]
        contexts += [{'context': check.get('context'), 'app_id': check.get('app_id')} for check in status['checks'] if isinstance(check, dict)]
        count = 1
        policies = [protection.get('required_pull_request_reviews') or {}]
        for rule in rules:
            if not isinstance(rule, dict): return unknown
            kind, params = rule.get('type'), rule.get('parameters') or {}
            if kind == 'required_status_checks':
                values = params.get('required_status_checks')
                if not isinstance(values, list) or any(not isinstance(value, dict) or 'integration_id' not in value for value in values): return unknown
                contexts += [{'context': value.get('context'), 'app_id': value.get('integration_id')} for value in values if isinstance(value, dict)]
            elif kind == 'pull_request': policies.append(params)
            elif kind not in ('creation', 'deletion', 'non_fast_forward', 'required_linear_history'):
                return unknown  # Merge queue, workflows, scanning, deployment etc. need their own proofs.
        for policy in policies:
            if (not isinstance(policy, dict) or policy.get('require_code_owner_reviews') or policy.get('require_code_owner_review')
                    or policy.get('require_last_push_approval')):
                return unknown
            required = policy.get('required_approving_review_count', 0)
            if type(required) is not int or not 0 <= required <= 10: return unknown
            count = max(count, required)
        if any(not isinstance(value.get('context'), str) or not value['context'] or
               (value['app_id'] is not None and (type(value['app_id']) is not int or value['app_id'] < -1)) for value in contexts):
            return unknown
        return {'known': True, 'strict': status.get('strict') is True,
                'enforce_admins': (protection.get('enforce_admins') or {}).get('enabled') is True,
                'contexts': contexts, 'required_approvals': count,
                'base_sha': (branch.get('commit') or {}).get('sha')}
    except ToolAccessError:
        return unknown


def ci_evidence(client, row, pull):
    checks, statuses, partial = [], [], False
    shas = [pull['head']['sha']]
    merge_sha = row.get('merge_commit_sha')
    if row.get('mergeable') is True and isinstance(merge_sha, str) and SHA.fullmatch(merge_sha) and merge_sha not in shas:
        shas.append(merge_sha)
    for sha in shas:
        runs, truncated = client.pages(f'commits/{sha}/check-runs', 'check_runs', params={'filter': 'latest'})
        values, truncated_statuses = client.pages(f'commits/{sha}/statuses')
        partial |= truncated or truncated_statuses
        latest = {}
        for run in runs:
            if (run.get('head_sha') != sha or type(run.get('id')) is not int or not run.get('name')
                    or type((run.get('app') or {}).get('id')) is not int or run['app']['id'] <= 0):
                partial = True; continue
            key = (run['name'], (run.get('app') or {}).get('id'))
            if run['id'] > latest.get(key, {}).get('id', -1): latest[key] = run
        checks += [{**{key: run.get(key) for key in ('name', 'status', 'conclusion', 'head_sha')},
                    'app_id': (run.get('app') or {}).get('id')} for run in latest.values()]
        latest = {}
        for value in values:
            if value.get('sha') != sha or type(value.get('id')) is not int or not value.get('context'):
                partial = True; continue
            if value['id'] > latest.get(value['context'], {}).get('id', -1): latest[value['context']] = value
        statuses += [{key: value.get(key) for key in ('context', 'state', 'sha')} for value in latest.values()]
    return checks, statuses, shas[-1], partial


def review_evidence(client, number, pull):
    rows, partial = client.pages(f'pulls/{number}/reviews')
    latest = {}
    for row in rows:
        if row.get('state') not in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'): continue
        login = (row.get('user') or {}).get('login')
        if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9_\[\]-]{1,100}', login) or type(row.get('id')) is not int:
            partial = True; continue
        if row['id'] > latest.get(login, {}).get('id', -1): latest[login] = row
    result = []
    for login, row in latest.items():
        trusted = False
        if row.get('state') == 'APPROVED' and row.get('commit_id') == pull['head']['sha'] and login.casefold() != str(pull['author']).casefold() and (row.get('user') or {}).get('type') == 'User':
            if len(result) >= 10: partial = True
            else:
                try:
                    value = client.get(f'collaborators/{quote(login, safe="")}/permission')
                    trusted = (isinstance(value, dict) and value.get('permission') in ('admin', 'maintain', 'write')
                               and (value.get('user') or {}).get('login') == login)
                except ToolAccessError: partial = True
        result.append({'author': login, 'state': row.get('state'), 'commit_id': row.get('commit_id'), 'trusted_approval': trusted})
    return result, partial


def required_checks_pass(policy, checks, statuses, head_sha, test_sha):
    if not policy['known'] or not policy['contexts']: return False
    for required in policy['contexts']:
        name, app = required['context'], required['app_id']
        candidates = [value for value in checks if value['name'] == name and (app in (None, -1) or value['app_id'] == app)]
        legacy = [value for value in statuses if value['context'] == name] if app in (None, -1) else []
        chosen_sha = test_sha if any(value['head_sha'] == test_sha for value in candidates) or any(value['sha'] == test_sha for value in legacy) else head_sha
        candidates = [value for value in candidates if value['head_sha'] == chosen_sha]
        legacy = [value for value in legacy if value['sha'] == chosen_sha]
        if not candidates and not legacy: return False
        if any(value['status'] != 'completed' or value['conclusion'] != 'success' for value in candidates): return False
        if any(value['state'] != 'success' for value in legacy): return False
    return True


def collect(client, number, include_files=True):
    from .github_prs import readiness_blockers
    row, pull = pinned_pull(client, number)
    files, files_partial = file_evidence(client, number, row) if include_files else ([], False)
    checks, statuses, test_sha, ci_partial = ci_evidence(client, row, pull)
    reviews, reviews_partial = review_evidence(client, number, pull)
    policy = branch_policy(client, pull)
    compare = client.get(f"compare/{pull['base']['sha']}...{pull['head']['sha']}", {'per_page': 1})
    up_to_date = (isinstance(compare, dict) and compare.get('behind_by') == 0 and type(compare.get('behind_by')) is int
                  and (compare.get('merge_base_commit') or {}).get('sha') == pull['base']['sha']
                  and compare.get('status') in ('ahead', 'identical'))
    end_row, end = pinned_pull(client, number)
    branch = client.get('branches/' + quote(pull['base']['ref'], safe=''))
    changed = (end['head'] != pull['head'] or end['base'] != pull['base'] or not isinstance(branch, dict)
               or end_row.get('merge_commit_sha') != row.get('merge_commit_sha')
               or (branch.get('commit') or {}).get('sha') != pull['base']['sha'])
    partial = files_partial or ci_partial or reviews_partial or changed
    ci = bool(checks or statuses) and all(value['status'] == 'completed' and value['conclusion'] in ('success', 'neutral', 'skipped') for value in checks) and all(value['state'] == 'success' for value in statuses)
    approved = sum(review['trusted_approval'] for review in reviews) >= policy['required_approvals']
    required = required_checks_pass(policy, checks, statuses, pull['head']['sha'], test_sha)
    codes = []
    if end.get('merged') is not False: codes.append('PR_STATE_UNKNOWN_OR_CLOSED')
    if not approved: codes.append('REVIEW_APPROVAL_MISSING')
    if not up_to_date or policy.get('base_sha') != pull['base']['sha']: codes.append('BASE_NOT_UP_TO_DATE')
    if not policy['known']: codes.append('BRANCH_POLICY_UNKNOWN_OR_UNSUPPORTED')
    if not policy['strict'] or not policy['enforce_admins']: codes.append('STRICT_PROTECTED_BASE_REQUIRED')
    if not required: codes.append('REQUIRED_CHECKS_NOT_PASSING')
    blockers = readiness_blockers(end, partial, changed, ci, reviews) + codes
    return {'repository': client.repository, 'pull_request': end, 'partial': partial, 'files': files,
            'checks': checks, 'statuses': statuses, 'reviews': reviews, 'branch_policy': policy,
            'candidate_ready': not blockers, 'blockers': blockers, 'blocker_codes': codes,
            'evidence_version': EVIDENCE_VERSION, 'review_approved': approved, 'base_up_to_date': up_to_date and not changed,
            'required_checks_satisfied': required, 'untrusted_external_data': True,
            'limitations': 'Strict classic protection/admin enforcement and fully observable rules are required for automatic merge. Unknown evidence blocks merging; this is not proof of code correctness.'}
