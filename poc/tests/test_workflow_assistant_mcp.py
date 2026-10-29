"""Actual MCP SDK client/server over stdio, isolated real SQLite, no model adapter fakes."""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from test_workflow_assistant import environment
from test_workflow_assistant_generation import service, request
from test_workflow_assistant_yaml import artifact


def context_file(db, job, tmp_path):
    path = tmp_path / 'authoring.json'
    path.write_text(json.dumps({'db_path': str(db.db_path.resolve()),
        'claims': {'sub':'operator', 'org_id':'org-a'},
        'granted_scopes': ['workflow-assistant:read','workflow-assistant:write'],
        'generation_id':job['id'], 'department_id':'dev'}))
    path.chmod(0o600)
    return path


def run_session(context, operation):
    async def run():
        params = StdioServerParameters(command=sys.executable,
            args=['-m','backend.workflow_assistant.mcp_server','--context',str(context)],
            env={**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1])})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await operation(session)
    return asyncio.run(run())


def test_real_mcp_exposes_only_scoped_authoring_tools_and_audits_yaml(environment, tmp_path):
    db, _ = environment
    svc = service(db); job,_ = svc.create(request())
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_assistant_generations SET status='RUNNING' WHERE id=?",(job['id'],));conn.commit()
    path = context_file(db,job,tmp_path)
    async def calls(session):
        tools = await session.list_tools()
        assert {t.name for t in tools.tools} == {'workflow_catalog','workflow_schema','validate_workflow_yaml'}
        for tool in tools.tools:
            assert 'department_id' not in tool.inputSchema.get('properties',{})
            assert 'user_id' not in tool.inputSchema.get('properties',{})
        catalog = await session.call_tool('workflow_catalog',{})
        assert not catalog.isError
        text = json.dumps(catalog.model_dump())
        assert 'acme/approved' in text and 'PRIVATE_' not in text and 'foreign-connector' not in text
        schema = await session.call_tool('workflow_schema',{})
        assert not schema.isError and 'workflow_schema_version' in json.dumps(schema.model_dump())
        checked = await session.call_tool('validate_workflow_yaml',{'yaml_content':artifact()['definition_yaml']})
        assert not checked.isError and 'proposal_hash' in json.dumps(checked.model_dump())
        assert 'validation_id' in json.dumps(checked.model_dump())
        unknown = await session.call_tool('send_telegram_message',{'text':'Do not send'})
        assert unknown.isError
    run_session(path,calls)
    with db._get_connection() as conn:
        rows = conn.execute('SELECT tool_name,proposal_hash,validation_id,proposal_json FROM workflow_assistant_tool_calls WHERE generation_id=? ORDER BY id',(job['id'],)).fetchall()
    assert [r['tool_name'] for r in rows] == ['workflow_catalog','workflow_schema','validate_workflow_yaml']
    assert rows[-1]['proposal_hash'] and rows[-1]['validation_id'].startswith('wfc_')
    assert json.loads(rows[-1]['proposal_json'])['name'] == 'PR review'
    assert db.list_workflows() == []


def test_mcp_rechecks_revocation_and_cancel_on_every_call(environment, tmp_path):
    db, _ = environment
    svc = service(db); job,_ = svc.create(request())
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_assistant_generations SET status='RUNNING' WHERE id=?",(job['id'],));conn.commit()
    path=context_file(db,job,tmp_path)
    async def calls(session):
        assert not (await session.call_tool('workflow_catalog',{})).isError
        db.remove_user_from_department('dev','operator')
        assert (await session.call_tool('workflow_catalog',{})).isError
        db.add_user_to_department('dev','operator',role='OPERATOR')
        svc.cancel(job['id'])
        assert (await session.call_tool('workflow_schema',{})).isError
    run_session(path,calls)
    assert len(svc.get(job['id'])['tool_calls']) == 1


def test_mcp_does_not_validate_arbitrary_foreign_bindings(environment, tmp_path):
    db,_=environment
    svc=service(db);job,_=svc.create(request())
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_assistant_generations SET status='RUNNING' WHERE id=?",(job['id'],));conn.commit()
    path=context_file(db,job,tmp_path)
    native=artifact()['definition_yaml'].replace('acme/approved','foreign/private')
    async def calls(session):
        result=await session.call_tool('validate_workflow_yaml',{'yaml_content':native})
        assert not result.isError
        assert 'RESOURCE_NOT_APPROVED' in json.dumps(result.model_dump())
        invalid=await session.call_tool('validate_workflow_yaml',{'yaml_content':'name: broken'})
        assert invalid.isError
    run_session(path,calls)
    assert db.list_workflows()==[]
