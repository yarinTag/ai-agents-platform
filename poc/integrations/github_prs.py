"""Bounded GitHub PR facts, with pinned revisions and conservative readiness."""
import hmac
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
        self.repository = repository
        def current_authority():
            connector = authorize()
            configuration = getattr(connector, 'configuration', None) or {}
            current = next((configuration.get(key).strip() for key in ('token', 'personal_access_token', 'api_key', 'GITHUB_PERSONAL_ACCESS_TOKEN')
                            if isinstance(configuration.get(key), str) and configuration[key].strip()), None)
            if current is None or not hmac.compare_digest(token.strip().encode(), current.encode()):
                raise ToolAccessError('GitHub credentials changed during this action. Start a fresh authorized request.')
            return connector
        self.authorize = current_authority
        self.headers = {'Authorization': 'Bearer ' + token.strip(), 'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2026-03-10'}

    def get(self, suffix, params=None):
        self.authorize()
        value = request_json('api.github.com', f'/repos/{self.repository}/{suffix}', self.headers, params)
        self.authorize()
        return value

    def pages(self, suffix, key=None, maximum=3, params=None):
        items, complete, malformed = [], False, False
        for page in range(1, maximum + 1):
            value = self.get(suffix, {**(params or {}), 'per_page': 100, 'page': page})
            rows = value.get(key) if key and isinstance(value, dict) else value
            if not isinstance(rows, list):
                raise ToolAccessError('GitHub returned an unexpected PR response.')
            malformed |= any(not isinstance(row, dict) for row in rows)
            items.extend(row for row in rows if isinstance(row, dict))
            if len(rows) < 100:
                complete = True
                break
        return items, not complete or malformed

    def open_pulls(self, author=None):
        rows, partial = self.pages('pulls', params={'state': 'open', 'sort': 'updated', 'direction': 'desc'})
        return {'repository': self.repository, 'untrusted_external_data': True, 'partial': partial,
                'pull_requests': [project_pull(row, self.repository) for row in rows
                                  if row.get('state') == 'open'
                                  and (author is None or (row.get('user') or {}).get('login') == author)],
                'limits': 'Up to 300 open PRs across the repository; no lookback cutoff. Filtering is by exact author login.'}

    def review(self, number):
        from .github_pr_evidence import collect
        return collect(self, number)


def execute_read(configuration, operation, inputs, authorize):
    client = GitHubReads(configuration, inputs.repository, authorize)
    if operation == 'list_open_pull_requests':
        return client.open_pulls(inputs.author)
    from .github_pr_evidence import collect, file_evidence, pinned_pull
    if operation == 'get_pull_request_review':
        return client.review(inputs.pull_number)
    if operation == 'get_pull_request_checks':
        return {**collect(client, inputs.pull_number, include_files=False), 'files_included': False}
    if operation in ('get_pull_request', 'get_pull_request_diff'):
        row, pull = pinned_pull(client, inputs.pull_number)
        value = {'repository': client.repository, 'pull_request': pull, 'partial': False, 'untrusted_external_data': True}
        if operation == 'get_pull_request_diff':
            files, partial = file_evidence(client, inputs.pull_number, row)
            _, end = pinned_pull(client, inputs.pull_number)
            changed = end['head'] != pull['head'] or end['base'] != pull['base']
            value.update(files=files, partial=partial or changed, revisions_changed=changed)
        return value
    raise ToolAccessError('Unknown GitHub PR read operation.')


def readiness_blockers(pull, partial, changed, ci, reviews):
    blockers = []
    if changed: blockers.append('PR head/base changed while collecting evidence')
    if partial: blockers.append('Evidence is incomplete or bounded/truncated')
    if pull.get('state') != 'open' or pull.get('draft') is not False: blockers.append('PR is closed or draft/unknown')
    if pull.get('mergeable') is not True or pull.get('mergeable_state') != 'clean': blockers.append('GitHub mergeability is not confirmed clean')
    if not ci: blockers.append('CI is missing, pending or unsuccessful')
    if any(r.get('state') == 'CHANGES_REQUESTED' for r in reviews): blockers.append('A reviewer requested changes')
    return blockers
