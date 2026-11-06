"""Bounded GitHub PR facts, with pinned revisions and conservative readiness."""
import re
from .provider_http import request_json
from .tool_definitions import ToolAccessError, valid_repository


def project_pull(row, repository):
    def branch(name):
        data = row.get(name) or {}
        return {'ref': data.get('ref'), 'sha': data.get('sha'),
                'repository': (data.get('repo') or {}).get('full_name')}
    number = row.get('number')
    return {'number': number, 'title': str(row.get('title') or '')[:500],
            'author': (row.get('user') or {}).get('login'),
            'labels': [str(label.get('name') or '')[:200] for label in row.get('labels') or []],
            'state': row.get('state'), 'draft': row.get('draft'), 'merged': row.get('merged'),
            'url': f'https://github.com/{repository}/pull/{number}',
            'head': branch('head'), 'base': branch('base'),
            'mergeable': row.get('mergeable'), 'mergeable_state': row.get('mergeable_state'),
            'updated_at': row.get('updated_at')}


class GitHubReads:
    def __init__(self, configuration, repository, authorize):
        if not valid_repository(repository):
            raise ToolAccessError('Repository must be an exact owner/name identifier.')
        token = next((configuration.get(key) for key in ('token', 'personal_access_token', 'api_key', 'GITHUB_PERSONAL_ACCESS_TOKEN')
                      if isinstance(configuration.get(key), str) and configuration[key].strip()), None)
        if not token:
            raise ToolAccessError('The GitHub connector has no configured access token.')
        self.repository, self.authorize = repository, authorize
        self.headers = {'Authorization': 'Bearer ' + token.strip(), 'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2026-03-10'}

    def get(self, suffix, params=None):
        self.authorize()
        value = request_json('api.github.com', f'/repos/{self.repository}/{suffix}', self.headers, params)
        self.authorize()
        return value

    def pages(self, suffix, key=None, maximum=3, params=None):
        items, complete = [], False
        for page in range(1, maximum + 1):
            value = self.get(suffix, {**(params or {}), 'per_page': 100, 'page': page})
            rows = value.get(key) if key and isinstance(value, dict) else value
            if not isinstance(rows, list):
                raise ToolAccessError('GitHub returned an unexpected PR response.')
            items.extend(row for row in rows if isinstance(row, dict))
            if len(rows) < 100:
                complete = True
                break
        return items, not complete

    def open_pulls(self, author=None):
        rows, partial = self.pages('pulls', params={'state': 'open', 'sort': 'updated', 'direction': 'desc'})
        return {'repository': self.repository, 'untrusted_external_data': True, 'partial': partial,
                'pull_requests': [project_pull(row, self.repository) for row in rows
                                  if author is None or (row.get('user') or {}).get('login') == author],
                'limits': 'Up to 300 open PRs across the repository; no lookback cutoff. Filtering is by exact author login.'}

    def review(self, number):
        row = self.get(f'pulls/{number}')
        if not isinstance(row, dict) or row.get('number') != number:
            raise ToolAccessError('GitHub returned an unexpected PR identity.')
        pull = project_pull(row, self.repository)
        sha = pull['head']['sha']
        base_sha = pull['base']['sha']
        if not all(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40,64}', value) for value in (sha, base_sha)):
            raise ToolAccessError('GitHub did not return immutable PR revisions.')
        files, files_partial = self.pages(f'pulls/{number}/files')
        reviews, reviews_partial = self.pages(f'pulls/{number}/reviews')
        checks, checks_partial = self.pages(f'commits/{sha}/check-runs', 'check_runs', params={'filter': 'latest'})
        statuses, statuses_partial = self.pages(f'commits/{sha}/statuses')
        # GitHub can attach required checks to the synthetic merge commit instead of HEAD.
        merge_sha = row.get('merge_commit_sha')
        if row.get('mergeable') is True and isinstance(merge_sha, str) and re.fullmatch(r'[0-9a-f]{40,64}', merge_sha):
            merge_checks, merge_partial = self.pages(f'commits/{merge_sha}/check-runs', 'check_runs', params={'filter': 'latest'})
            checks += merge_checks
            checks_partial |= merge_partial
        partial = any((files_partial, reviews_partial, checks_partial, statuses_partial)) or row.get('changed_files') != len(files)
        patches, size = [], 0
        for file in files:
            patch = file.get('patch')
            if not isinstance(patch, str) or size + len(patch) > 60000:
                partial = True
                patch = None  # Missing binary/large patches are explicit, never a complete review.
            else:
                size += len(patch)
            patches.append({'filename': file.get('filename'), 'previous_filename': file.get('previous_filename'),
                            'status': file.get('status'), 'additions': file.get('additions'),
                            'deletions': file.get('deletions'), 'patch': patch})
        latest_status = {}
        for status in statuses:  # API newest first.
            latest_status.setdefault(status.get('context'), status)
        latest_reviews = {}
        for review in reviews:
            if review.get('state') in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
                latest_reviews[(review.get('user') or {}).get('login')] = review
        ci = bool(checks or latest_status) and all(c.get('status') == 'completed' and c.get('conclusion') in ('success', 'neutral', 'skipped') for c in checks)
        ci = ci and all(s.get('state') == 'success' for s in latest_status.values())
        end = self.get(f'pulls/{number}')
        changed = not isinstance(end, dict) or (end.get('head') or {}).get('sha') != sha or (end.get('base') or {}).get('sha') != base_sha
        if isinstance(end, dict):
            pull = project_pull(end, self.repository)
        blockers = readiness_blockers(pull, partial, changed, ci, latest_reviews.values())
        return {'repository': self.repository, 'pull_request': pull, 'partial': partial or changed,
                'files': patches, 'checks': [{k: c.get(k) for k in ('name', 'status', 'conclusion', 'head_sha')} for c in checks],
                'statuses': [{k: s.get(k) for k in ('context', 'state', 'sha')} for s in latest_status.values()],
                'reviews': [{'author': (r.get('user') or {}).get('login'), 'state': r.get('state'),
                             'commit_id': r.get('commit_id')} for r in latest_reviews.values()],
                'candidate_ready': not blockers, 'blockers': blockers, 'untrusted_external_data': True,
                'limitations': 'Readiness is conservative evidence, not a guarantee of code correctness. GitHub branch rules still govern merging.'}


def execute_read(configuration, operation, inputs, authorize):
    client = GitHubReads(configuration, inputs.repository, authorize)
    return client.open_pulls(inputs.author) if operation == 'list_open_pull_requests' else client.review(inputs.pull_number)


def readiness_blockers(pull, partial, changed, ci, reviews):
    blockers = []
    if changed: blockers.append('PR head/base changed while collecting evidence')
    if partial: blockers.append('Evidence is incomplete or bounded/truncated')
    if pull.get('state') != 'open' or pull.get('draft') is not False: blockers.append('PR is closed or draft/unknown')
    if pull.get('mergeable') is not True or pull.get('mergeable_state') != 'clean': blockers.append('GitHub mergeability is not confirmed clean')
    if not ci: blockers.append('CI is missing, pending or unsuccessful')
    if any(r.get('state') == 'CHANGES_REQUESTED' for r in reviews): blockers.append('A reviewer requested changes')
    return blockers
