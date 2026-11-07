"""Read-only, bounded projection of persisted PR audit results for scoped run details."""
import json

OPERATIONS = ('open_pull_request', 'get_pull_request', 'get_pull_request_diff',
              'get_pull_request_checks', 'get_pull_request_review', 'comment_pull_request', 'review_pull_request')
FIELDS = ('repository', 'pull_number', 'head_sha', 'base_sha', 'merge_commit_sha', 'provider_actor',
          'provider_id', 'evidence_version', 'candidate_ready', 'review_approved', 'base_up_to_date',
          'required_checks_satisfied', 'partial', 'draft', 'pull_request_number', 'commit')


def step_pr_evidence(db, step, organization_id):
    if not step.get('task_run_id') or not organization_id:
        return []
    with db._get_connection() as conn:
        rows = conn.execute("""SELECT c.*,t.name AS operation FROM mcp_tool_calls c
            JOIN mcp_tools t ON t.id=c.tool_id AND t.connector_id=c.connector_id
            JOIN mcp_connectors connector ON connector.id=c.connector_id
            WHERE c.task_id=? AND c.agent_id=? AND connector.organization_id=?
            AND c.run_id=c.task_id AND connector.provider='github'
            AND (c.id GLOB 'call_exec_*' OR c.id GLOB 'call_repo_*')
            ORDER BY c.started_at,c.id LIMIT 32""",
            (step['task_run_id'], step['agent_id'], organization_id)).fetchall()
    result = []
    for row in rows:
        if row['operation'] not in OPERATIONS:
            continue
        try:
            value = json.loads(row['result'] or '{}')
            arguments = json.loads(row['arguments'] or '{}')
        except (ValueError, TypeError):
            continue
        if not isinstance(value, dict) or not isinstance(arguments, dict):
            continue
        entry = {key: value[key] for key in FIELDS if key in value and isinstance(value[key], (str, int, bool, float))}
        if isinstance(value.get('blockers'), list):
            entry['blockers'] = [v[:1000] for v in value['blockers'][:32] if isinstance(v, str)]
        if isinstance(value.get('reviews'), list):
            entry['reviews'] = [{key: v[key] for key in ('author', 'state', 'commit_id', 'trusted_approval')
                                 if isinstance(v.get(key), (str, bool))} for v in value['reviews'][:300] if isinstance(v, dict)]
        entry.update(operation=row['operation'], audit_id=row['id'], status=row['status'],
                     started_at=row['started_at'], completed_at=row['completed_at'])
        repository = arguments.get('repository', value.get('repository'))
        if not isinstance(repository, str) or len(repository) > 150:
            continue
        entry['repository'] = repository
        for key in ('pull_number', 'head_sha'):
            if key not in entry and isinstance(arguments.get(key), (str, int)):
                entry[key] = arguments[key]
        pull = value.get('pull_request')
        if isinstance(pull, dict):
            entry['pull_request'] = {key: pull[key] for key in ('number', 'state', 'draft', 'merged')
                                     if isinstance(pull.get(key), (str, int, bool))}
            for key in ('head', 'base'):
                branch = pull.get(key)
                if isinstance(branch, dict):
                    entry['pull_request'][key] = {k: branch[k] for k in ('sha', 'ref') if isinstance(branch.get(k), str)}
        if row['operation'] == 'open_pull_request':
            entry.update(pull_number=value.get('pull_request_number') if type(value.get('pull_request_number')) is int else None,
                         head_sha=value.get('commit') if isinstance(value.get('commit'), str) else None)
        result.append(entry)
    return result
