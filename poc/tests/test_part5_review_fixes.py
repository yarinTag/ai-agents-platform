"""
Regression tests for the Part 5 code-review fixes (real SQLite, real loopback HTTP, real crypto, no mocks):
tenant authz on step-log/policy routes, least-privilege probe endpoint, adapter hardening,
per-model pricing, mid-run budget enforcement and exact audit correlation.
"""

import json
import uuid

import pytest

from config import AgentConfig
from gateways.llm_proxy import LLMProxy, DEFAULT_ALLOWED_MODELS
from gateways.secrets_broker import SecretsBroker
from persistence_modules.postgres_rls import record_security_audit_event
from runtime.direct_llm_adapter import DirectHTTPLLMRuntimeAdapter
from runtime.llm_wire import compute_cost_usd, parse_tool_arguments
from workflows.engine import WorkflowEngine
from workflows.step_logs_service import get_execution_step_logs

# shared real fixtures/helpers (loopback provider server, tmp DB, org+dept factory)
from test_byok_llm_and_notification_policies import (  # noqa: F401
    TOOLS, _adapter, _org_dept, db, provider_server,
)


# ---------------------------------------------------------------- adapter hardening
def _openai_run(db, base, handler, scripts, adapter=None, org_dept=None, broker=None):
    org, dept = org_dept or _org_dept(db)
    db.grant_department_mcp_access(dept, "github", ["list_issues"], organization_id=org)
    db.save_org_llm_credential(org, "openai", "openai-key-ABCDEFGHIJ", base_url=f"{base}/openai")
    handler.scripts["/openai"] = scripts
    broker = broker or SecretsBroker()
    tok = broker.issue_run_token(org, dept, f"run_{uuid.uuid4().hex[:6]}", allowed_mcps=["github"])
    return (adapter or _adapter(broker)).execute_with_tools(
        db=db, run_token=tok.token, provider="openai", model="gpt-4o",
        system_prompt="", user_prompt="go", tools=TOOLS)


def _tool_call(args):
    return {"choices": [{"message": {"role": "assistant", "tool_calls": [{
        "id": "c1", "function": {"name": "github__list_issues", "arguments": args}}]}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}


def test_adapter_does_not_mutate_shared_proxy_allowlist():
    proxy = LLMProxy(secrets_broker_instance=SecretsBroker(), allowed_models={"only-this"})
    DirectHTTPLLMRuntimeAdapter(llm_proxy_instance=proxy)
    assert proxy.allowed_models == {"only-this"}
    assert {"gpt-4o", "meta/llama-3.1-70b-instruct", "claude-sonnet-4-20250514"} <= DEFAULT_ALLOWED_MODELS


def test_cost_uses_per_model_pricing():
    assert compute_cost_usd("gpt-4o", 1000, 500) == pytest.approx(0.0075)
    assert compute_cost_usd("claude-3-5-sonnet-latest", 1000, 500) == pytest.approx(0.0105)
    assert compute_cost_usd("unknown-model", 1_000_000, 0) == 5.0          # conservative default


def test_malformed_tool_arguments_do_not_crash_the_run(db, provider_server):
    base, handler = provider_server
    out = _openai_run(db, base, handler, [
        _tool_call("{not json"),
        {"choices": [{"message": {"content": "recovered"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 1}},
    ])
    assert out["output_text"] == "recovered" and out["tool_calls_executed"] == []
    fed_back = json.dumps(handler.seen[1][2]["messages"][-1])
    assert "not valid JSON" in fed_back
    assert out["cost_usd"] == compute_cost_usd("gpt-4o", 1005, 501)         # actual, not the estimate floor
    assert parse_tool_arguments('["x"]')[1] == "tool arguments must be a JSON object"


def test_tool_call_without_executor_is_not_reported_as_success(db, provider_server):
    base, handler = provider_server
    org_dept = _org_dept(db)
    broker = SecretsBroker()
    adapter = DirectHTTPLLMRuntimeAdapter(
        llm_proxy_instance=LLMProxy(secrets_broker_instance=broker),
        tool_gateway_instance=_adapter(broker).tool_gateway)               # real gateway, NO tool_executor
    out = _openai_run(db, base, handler, [
        _tool_call("{}"), {"choices": [{"message": {"content": "done"}}]}], adapter, org_dept, broker)
    assert out["tool_calls_executed"] == []
    assert "cannot be executed" in json.dumps(handler.seen[1][2]["messages"][-1])


def test_midrun_budget_is_enforced_with_actual_token_cost(db, provider_server):
    base, handler = provider_server
    huge = _tool_call(json.dumps({"repo": "a/b"}))
    huge["usage"] = {"prompt_tokens": 30_000_000, "completion_tokens": 0}   # $75 on gpt-4o > $50 budget
    with pytest.raises(PermissionError, match="mid-run"):
        _openai_run(db, base, handler, [huge, {"choices": [{"message": {"content": "never"}}]}])
    assert len(handler.seen) == 1                                           # follow-up round never sent


# ---------------------------------------------------------------- tenant authorization
@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.dependencies import get_db_manager
    app.dependency_overrides[get_db_manager] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db_manager, None)


def _hdr(org, role="ORG_ADMIN"):
    from backend.security.tokens import create_access_token
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": "u1", "email": "u@x.io", "org_id": org, "role": role}, 3600)}


def _executed_workflow(db, org="org_a", dept="dept_a"):
    _org_dept(db, org, dept)
    db.save_agent(AgentConfig(id="ceo-orchestrator", name="CEO", description="d", system_prompt="p", model="default"))
    wf_id = f"wf_{uuid.uuid4().hex[:6]}"
    definition = {"id": wf_id, "name": "WF", "steps": [{"key": "a", "name": "A", "agent_id": "agent-a", "prompt_template": "x"}]}
    db.create_workflow(id=wf_id, name="WF", definition_json=json.dumps(definition), department_id=dept)
    return wf_id, WorkflowEngine(db_manager=db).execute_workflow(wf_id, trigger_type="MANUAL")


def test_step_log_routes_are_tenant_isolated(db, client):
    _, ex = _executed_workflow(db)
    own, other = _hdr("org_a", "MEMBER"), _hdr("org_b")
    assert client.get(f"/api/v1/workflows/executions/{ex.id}/steps", headers=own).status_code == 200
    assert client.get(f"/api/v1/workflows/executions/{ex.id}/steps/a/logs", headers=own).status_code == 200
    assert client.get(f"/api/v1/workflows/executions/{ex.id}/steps", headers=other).status_code == 404
    assert client.get(f"/api/v1/workflows/executions/{ex.id}/steps/a/logs", headers=other).status_code == 404
    assert client.get("/api/v1/workflows/executions/nope/steps", headers=own).status_code == 404


def test_notification_policy_requires_owning_org_admin(db, client):
    wf_id, _ = _executed_workflow(db)
    url, body = f"/api/v1/workflows/{wf_id}/notification-policy", {"notify_policy": "EVERY_STEP", "channel_id": "1"}
    assert client.put(url, json=body, headers=_hdr("org_b")).status_code == 404           # other tenant
    assert client.put(url, json=body, headers=_hdr("org_a", "MEMBER")).status_code == 403  # not admin
    ok = client.put(url, json=body, headers=_hdr("org_a"))
    assert ok.status_code == 200 and ok.json()["notify_policy"] == "EVERY_STEP"


def test_probe_endpoint_cannot_target_foreign_department_or_borrow_tokens(db, client):
    _org_dept(db, "org_a", "dept_a")
    _org_dept(db, "org_b", "dept_b")
    url = "/api/v1/organizations/org_a/llm-keys/test-completion"
    admin = _hdr("org_a")
    foreign = client.post(url, json={"provider": "openai", "department_id": "dept_b"}, headers=admin)
    assert foreign.status_code == 400                                       # dept of another org
    assert client.post(url, json={"provider": "openai"}, headers=admin).status_code == 422   # dept required
    save = client.post("/api/v1/organizations/org_a/llm-keys", headers=admin, json={
        "provider": "openai", "api_key": "sk-test-key-0123456789", "department_id": "dept_b"})
    assert save.status_code == 400                                          # cannot attach key to foreign dept


# ---------------------------------------------------------------- audit correlation
def test_audit_correlation_is_exact_and_wildcard_safe(db):
    _, ex = _executed_workflow(db)
    audit = lambda rid: record_security_audit_event(
        db=db, action="X", actor="t", entity_type="e", entity_id="1", org_id="org_a", department_id=None,
        run_id=rid, parameters={}, metadata={}, decision="ALLOWED", reason="r")
    mine = audit(ex.id)
    audit(ex.id + "9")                                                       # id that merely starts with ours
    audit(ex.id[:-1] + "%")                                                  # wildcard probe must not match
    ids = [a["id"] for a in get_execution_step_logs(db, ex.id)["steps"][0]["security_audit_logs"]]
    assert ids == [mine["id"]]
