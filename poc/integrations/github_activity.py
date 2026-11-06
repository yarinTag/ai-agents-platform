"""Read-only GitHub activity with bounded pagination and explicit partial-result flags."""
from datetime import datetime, timedelta, timezone
from .provider_http import request_json
from .tool_definitions import ToolAccessError, valid_repository


def fetch_activity(configuration, operation, repository, days, authorize):
    if not valid_repository(repository):
        raise ToolAccessError('Repository must be an exact owner/name identifier.')
    token = next((configuration.get(key) for key in ('token', 'personal_access_token', 'api_key', 'GITHUB_PERSONAL_ACCESS_TOKEN')
                  if isinstance(configuration.get(key), str) and configuration[key].strip()), None)
    if not token:
        raise ToolAccessError('The GitHub connector has no configured access token.')
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat(timespec='seconds').replace('+00:00', 'Z')
    until = now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    groups = ['commits', 'issues', 'pulls', 'releases'] if operation == 'get_repository_activity' else [{
        'list_commits': 'commits', 'list_issues': 'issues', 'list_pull_requests': 'pulls', 'list_releases': 'releases'}[operation]]
    result = {'repository': repository, 'since': since, 'until': until, 'untrusted_external_data': True,
        'partial': False, 'limits': 'At most 3 pages of 50 items per category; issues/PRs use updated_at, releases use published_at.'}
    total_chars = 0
    headers = {'Authorization': 'Bearer ' + token.strip(), 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2026-03-10'}
    for group in groups:
        items = []
        for page in range(1, 4):
            authorize()  # Recheck live scope/permissions before every network request.
            params = {'per_page': 50, 'page': page}
            if group == 'commits':
                params.update(since=since, until=until)
            elif group in ('issues', 'pulls'):
                params.update(state='all', sort='updated', direction='desc')
                if group == 'issues':
                    params['since'] = since
            rows = request_json('api.github.com', f'/repos/{repository}/{group}', headers, params)
            if not isinstance(rows, list):
                raise ToolAccessError('GitHub returned an unexpected response.')
            authorize()  # Revocation while waiting must not publish newly fetched data.
            for row in rows:
                if not isinstance(row, dict) or group == 'issues' and 'pull_request' in row:
                    continue
                if group == 'commits':
                    commit = row.get('commit') or {}
                    item = {'sha': row.get('sha'), 'message': str(commit.get('message', ''))[:500],
                        'date': (commit.get('committer') or {}).get('date')}
                elif group == 'releases':
                    date = row.get('published_at') or ''
                    if not since <= date <= until:
                        continue
                    item = {'tag': row.get('tag_name'), 'name': str(row.get('name') or '')[:300], 'published_at': date}
                else:
                    date = row.get('updated_at') or ''
                    if not since <= date <= until:
                        continue
                    item = {'number': row.get('number'), 'title': str(row.get('title') or '')[:300],
                        'state': row.get('state'), 'created_at': row.get('created_at'),
                        'updated_at': date, 'closed_at': row.get('closed_at')}
                    if group == 'pulls':
                        from .github_prs import project_pull
                        item.update(project_pull(row, repository))
                size = len(str(item))
                if total_chars + size > 45000:
                    result['partial'] = True
                    break
                items.append(item)
                total_chars += size
            if len(rows) < 50 or total_chars > 44000:
                if total_chars > 44000:
                    result['partial'] = True
                break
            if page == 3:
                result['partial'] = True
        result['pull_requests' if group == 'pulls' else group] = items
    return result
