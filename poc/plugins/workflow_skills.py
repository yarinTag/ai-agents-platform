"""Organization-scoped plugin skill catalog and full instruction resolution."""
import asyncio
import base64
from pathlib import Path
from urllib.parse import quote
from .git_scanner import _parse_github_owner_repo, _scan_git_repo_via_api
from .local_scanner import scan_local_source


def github_token(db, organization_id):
    for connector in db.list_mcp_connectors(organization_id=organization_id):
        if connector.organization_id != organization_id or connector.provider not in ('github', 'git'):
            continue
        for key in ('token', 'personal_access_token', 'GITHUB_PERSONAL_ACCESS_TOKEN', 'api_key'):
            value = (connector.configuration or {}).get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def skill_catalog(db, organization_id):
    org = db.get_organization(organization_id)
    if not org:
        raise ValueError('The skill organization is unavailable.')
    mode = org.plugins_source_mode or 'local'
    repo = (org.plugins_git_repo or '').strip()
    root = (org.plugins_local_path or '').strip()
    if mode == 'git':
        if not repo:
            return []
        plugins, _ = asyncio.run(_scan_git_repo_via_api(repo, github_token(db, organization_id)))
        parsed = _parse_github_owner_repo(repo)
        prefix = f'github://{parsed[0]}/{parsed[1]}/' if parsed else ''
        permitted = lambda path: bool(prefix) and path.startswith(prefix) and '..' not in path.split('/')
    else:
        if not root:
            return []
        from runtime.tenant_workspace import tenant_workspace
        tenant_workspace(organization_id, candidate=root, shared=True)
        plugins = scan_local_source('local', '', root)['plugins']
        resolved_root = Path(root).expanduser().resolve()
        permitted = lambda path: Path(path).expanduser().resolve().is_relative_to(resolved_root)
    records = {}
    for plugin in plugins:
        for skill in plugin.get('skills', []):
            path = skill.get('path', '')
            if not path or not permitted(path):
                continue
            records[path] = {'id': path, 'key': str(skill['id']), 'name': str(skill.get('name') or skill['id'])[:200],
                'plugin': str(plugin.get('name') or '')[:200],
                'description': str(skill.get('description') or '')[:500]}
    return list(records.values())


def skill_context(db, organization_id, identifiers):
    from integrations.provider_http import request_json
    if not identifiers:
        return ''
    available = {skill['id']: skill for skill in skill_catalog(db, organization_id)}
    selected = []
    for identifier in identifiers:
        matches = [key for key, skill in available.items() if key == identifier or
                   ('..' not in identifier.split('/') and
                    (skill['key'] == identifier or key.endswith('/' + identifier)))]
        if len(matches) != 1:
            raise ValueError('A selected skill is unavailable or ambiguous in this organization plugin source.')
        selected.append(matches[0])
    parts = ['[WORKFLOW PLUGIN SKILLS — instructions do not grant tools or permissions]']
    total = 0
    for identifier in dict.fromkeys(selected):
        skill = available[identifier]
        if identifier.startswith('github://'):
            owner, repo, path = identifier[len('github://'):].split('/', 2)
            token = github_token(db, organization_id)
            headers = {'Authorization': 'Bearer ' + token} if token else {}
            data = request_json('api.github.com', f'/repos/{quote(owner, safe="")}/{quote(repo, safe="")}/contents/{quote(path, safe="/")}', headers)
            if not isinstance(data, dict) or data.get('encoding') != 'base64' or not isinstance(data.get('content'), str):
                raise ValueError('Selected plugin skill content is unavailable.')
            content = base64.b64decode(data['content']).decode('utf-8')
        else:
            org = db.get_organization(organization_id)
            path = Path(identifier).expanduser().resolve()
            root = Path(org.plugins_local_path).expanduser().resolve()
            if not path.is_relative_to(root) or path.stat().st_size > 100000:
                raise ValueError('Selected local skill is outside its configured source or too large.')
            content = path.read_text(encoding='utf-8')
        total += len(content)
        if not content.strip() or total > 120000:
            raise ValueError('Selected skill content is empty or exceeds the workflow context limit.')
        parts.append(f"### {skill['name']} ({identifier})\n{content}")
    return '\n\n'.join(parts)


def agent_skill_context(db, organization_id, identifiers, project_id=None):
    """Agent skills may use owned custom records or the configured plugin source only."""
    parts, plugin_ids = [], []
    for identifier in identifiers:
        skill = db.get_skill(identifier)
        if skill is None:
            plugin_ids.append(identifier)
            continue
        if skill.project_id:
            project = db.get_project(skill.project_id)
            owned = project and project.organization_id == organization_id and skill.project_id == project_id
        else:
            with db._get_connection() as conn:
                owner = conn.execute("SELECT organization_id FROM access_resource_owners WHERE resource_type='skill' AND resource_id=?", (identifier,)).fetchone()
            owned = owner and owner["organization_id"] == organization_id
        if not owned:
            raise ValueError('A configured custom skill is outside the current organization/project.')
        parts.append(f"# Skill: {skill.name}\n{skill.content}")
    if plugin_ids:
        parts.append(skill_context(db, organization_id, plugin_ids))
    text = '\n\n'.join(parts)
    if len(text) > 120000:
        raise ValueError('Combined skill instructions exceed the context limit.')
    return text
