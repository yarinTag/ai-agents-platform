"""Internal, process-bound stdio MCP server. Not a public/OAuth MCP endpoint.

The authenticated platform creates a private context file for exactly one generation.
No token, identity, database path or department can be supplied by model tool arguments.
"""
import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from persistence import DatabaseManager
from .service import WorkflowAssistantService
from .tools import WorkflowAuthoringTools


def create_server(context_path: str):
    path = Path(context_path)
    if path.stat().st_mode & 0o077:
        raise ValueError('Authoring context must be private to its owner.')
    context = json.loads(path.read_text())
    db = DatabaseManager(context['db_path'])
    policy = WorkflowAssistantService(db, context['claims'], source='mcp',
        granted_scopes=set(context['granted_scopes']))
    tools = WorkflowAuthoringTools(policy)
    server = FastMCP('workflow_authoring', instructions=(
        'Use workflow_catalog and workflow_schema before planning. Only build a workflow draft. '
        'Use validate_workflow_yaml to check generated YAML. No external actions or publication are available.'))

    def require_live_session(conn):
        user, _, _, _ = policy._workspace(context['department_id'], write=True)
        row = conn.execute("""SELECT status, deadline_at FROM workflow_assistant_generations
            WHERE id=? AND organization_id=? AND created_by=? AND department_id=?""",
            (context['generation_id'], user.organization_id, user.id, context['department_id'])).fetchone()
        if not row or row['status'] != 'RUNNING' or row['deadline_at'] <= datetime.now().isoformat():
            raise ValueError('Authoring session is no longer active.')

    def execute(name, operation):
        # Check before returning any data and again atomically with candidate persistence.
        with db._get_connection() as conn:
            require_live_session(conn)
        result = operation()
        validation_id = 'wfc_' + uuid.uuid4().hex if name == 'validate_workflow_yaml' else None
        with db._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            require_live_session(conn)
            conn.execute("""INSERT INTO workflow_assistant_tool_calls
                (generation_id, tool_name, proposal_hash, validation_id, proposal_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (context['generation_id'], name, result.get('validation', {}).get('proposal_hash'), validation_id,
                 json.dumps(result['proposal'], ensure_ascii=False) if validation_id else None,
                 datetime.now().isoformat()))
            conn.commit()
        if validation_id:
            return {'validation_id': validation_id, 'validation': result['validation'],
                'workflow_schema_version': result['workflow_schema_version']}
        return result

    @server.tool()
    def workflow_catalog() -> dict:
        """Get approved execution agents, tools, repositories and channels for this session's department."""
        return execute('workflow_catalog', lambda: tools.catalog(context['department_id']))

    @server.tool()
    def workflow_schema() -> dict:
        """Get the authoritative workflow YAML/JSON schema. Internal IDs must come from the catalog."""
        return execute('workflow_schema', lambda: {key: value for key, value in tools.schema().items() if key != 'yaml_schema'})

    @server.tool()
    def validate_workflow_yaml(yaml_content: str) -> dict:
        """Validate YAML and permissions; return validation_id for the exact stored candidate. Never activates it."""
        return execute('validate_workflow_yaml', lambda: tools.validate_yaml(context['department_id'], yaml_content))

    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--context', required=True)
    args = parser.parse_args()
    create_server(args.context).run(transport='stdio')


if __name__ == '__main__':
    main()
