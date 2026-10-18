"""
Part 5 tests: BYOK LLM key vault, DirectHTTPLLMRuntimeAdapter (Anthropic / OpenAI / NVIDIA wire
formats + tool calling through the RuntimeToolGateway), notification policies, step logs.

Zero-mocks: real SQLite, real envelope crypto, real HTTP over a local socket server standing in
for the provider endpoint (the adapter is pointed at it via the credential's base_url).
"""

import json
import os
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from persistence import DatabaseManager
from config import AgentConfig
from gateways.secrets_broker import SecretsBroker
from gateways.llm_proxy import LLMProxy
from gateways.tool_gateway import RuntimeToolGateway
from runtime.direct_llm_adapter import DirectHTTPLLMRuntimeAdapter
from shared.notifications import should_send_notification
from workflows.engine import WorkflowEngine
from workflows.step_logs_service import get_execution_step_logs


# ---------------------------------------------------------------- local provider endpoint
class _ProviderHandler(BaseHTTPRequestHandler):
    scripts = {}   # path -> list of JSON responses (consumed in order)
    seen = []      # (path, headers, body) of every request

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, dict(self.headers), body))
        queue = type(self).scripts.get(self.path, [])
        payload = queue.pop(0) if queue else {}
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


@pytest.fixture()
def provider_server():
    _ProviderHandler.scripts, _ProviderHandler.seen = {}, []
    server = HTTPServer(("127.0.0.1", 0), _ProviderHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", _ProviderHandler
    server.shutdown()


@pytest.fixture()
def db():
    with tempfile.TemporaryDirectory() as tmp:
        yield DatabaseManager(db_path=os.path.join(tmp, "byok.db"))


def _org_dept(db, org_id="org_byok", dept_id="dept_byok"):
    db.create_organization(id=org_id, name=org_id, slug=org_id, domain=f"{org_id}.io")
    db.create_department(
        id=dept_id, name="Eng", description="d", monthly_budget_usd=50.0,
        budget_action="HARD_STOP", organization_id=org_id,
    )
    return org_id, dept_id


# ---------------------------------------------------------------- BYOK vault
def test_vault_encrypts_masks_and_isolates_tenants(db):
    secret = "sk-ant-api03-SUPERSECRETVALUE1234567890abcd"
    cred = db.save_org_llm_credential("org_a", "anthropic", secret, key_alias="prod")
    assert secret not in json.dumps(cred.to_dict())          # never returned in clear
    assert cred.masked_key.startswith("sk-ant") and cred.masked_key.endswith("abcd")

    with db._get_connection() as conn:                        # nor stored in clear
        raw = conn.execute("SELECT encrypted_envelope_json FROM org_llm_credentials").fetchone()[0]
    assert "SUPERSECRETVALUE" not in raw

    assert db.resolve_org_llm_api_key("org_a", "anthropic")["api_key"] == secret
    with pytest.raises(PermissionError):                      # tenant B cannot see tenant A's key
        db.resolve_org_llm_api_key("org_b", "anthropic")
    assert db.delete_org_llm_credential(cred.id, "org_b") is False   # cross-tenant delete blocked
    assert db.delete_org_llm_credential(cred.id, "org_a") is True


def test_vault_rotation_dept_override_and_provider_validation(db):
    db.save_org_llm_credential("org_a", "openai", "sk-org-key-0000000000")
    db.save_org_llm_credential("org_a", "openai", "sk-dept-key-111111111", department_id="dept_x")
    assert db.resolve_org_llm_api_key("org_a", "openai", "dept_x")["api_key"] == "sk-dept-key-111111111"
    assert db.resolve_org_llm_api_key("org_a", "openai", "dept_y")["api_key"] == "sk-org-key-0000000000"

    db.save_org_llm_credential("org_a", "openai", "sk-rotated-2222222222")      # rotate in place
    assert len(db.list_org_llm_credentials("org_a")) == 2
    assert db.resolve_org_llm_api_key("org_a", "openai")["api_key"] == "sk-rotated-2222222222"

    with pytest.raises(ValueError):
        db.save_org_llm_credential("org_a", "mistral", "k" * 20)


# ---------------------------------------------------------------- direct adapter
def _adapter(broker):
    return DirectHTTPLLMRuntimeAdapter(
        tool_executor=lambda conn, tool, args: {"issues": [f"{conn}.{tool}", args.get("repo")]},
        llm_proxy_instance=LLMProxy(secrets_broker_instance=broker),
        tool_gateway_instance=RuntimeToolGateway(secrets_broker_instance=broker),
    )


TOOLS = [{"connector_id": "github", "name": "list_issues", "description": "List issues",
          "parameters": {"type": "object", "properties": {"repo": {"type": "string"}}}}]


def _run(db, broker, provider, model, base_url, path):
    org, dept = _org_dept(db)
    db.grant_department_mcp_access(dept, "github", ["list_issues"], organization_id=org)
    db.save_org_llm_credential(org, provider, f"{provider}-key-ABCDEFGHIJ", base_url=f"{base_url}{path}")
    tok = broker.issue_run_token(org, dept, f"run_{uuid.uuid4().hex[:6]}", allowed_mcps=["github"])
    return _adapter(broker).execute_with_tools(
        db=db, run_token=tok.token, provider=provider, model=model,
        system_prompt="sys", user_prompt="list issues for acme/x", tools=TOOLS,
    )


def test_openai_and_nvidia_wire_format_and_tool_loop(db, provider_server):
    base, handler = provider_server
    for provider, model in (("openai", "gpt-4o"), ("nvidia", "meta/llama-3.1-70b-instruct")):
        path = f"/{provider}"
        handler.scripts[path] = [
            {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "github__list_issues", "arguments": json.dumps({"repo": "acme/x", "org_id": "evil"})}}]}}],
             "usage": {"prompt_tokens": 11, "completion_tokens": 5}},
            {"choices": [{"message": {"role": "assistant", "content": f"done via {provider}"}}],
             "usage": {"prompt_tokens": 20, "completion_tokens": 7}},
        ]
        out = _run(DatabaseManager(db_path=str(db.db_path) + provider), SecretsBroker(), provider, model, base, path)
        assert out["output_text"] == f"done via {provider}"
        assert out["input_tokens"] == 31 and out["output_tokens"] == 12
        call = out["tool_calls_executed"][0]
        assert (call["connector_id"], call["tool_name"]) == ("github", "list_issues")
        assert "org_id" not in call["arguments"]                      # spoofed identity stripped by gateway

    for path, headers, body in handler.seen:
        assert headers["Authorization"].startswith("Bearer ")         # OpenAI-style auth
        assert body["tools"][0]["type"] == "function"


def test_anthropic_wire_format_and_tool_loop(db, provider_server):
    base, handler = provider_server
    handler.scripts["/anthropic"] = [
        {"content": [{"type": "tool_use", "id": "tu_1", "name": "github__list_issues", "input": {"repo": "acme/x"}}],
         "usage": {"input_tokens": 9, "output_tokens": 4}},
        {"content": [{"type": "text", "text": "anthropic done"}], "usage": {"input_tokens": 15, "output_tokens": 6}},
    ]
    out = _run(db, SecretsBroker(), "anthropic", "claude-3-5-sonnet-latest", base, "/anthropic")
    assert out["output_text"] == "anthropic done" and out["input_tokens"] == 24
    _, headers, body = handler.seen[0]
    assert "x-api-key" in {k.lower() for k in headers} and "anthropic-version" in {k.lower() for k in headers}
    assert body["tools"][0]["name"] == "github__list_issues" and "input_schema" in body["tools"][0]


def test_tool_call_denied_when_department_lacks_permission(db, provider_server):
    base, handler = provider_server
    org, dept = _org_dept(db)                                         # NOTE: no MCP grant
    db.save_org_llm_credential(org, "openai", "openai-key-ABCDEFGHIJ", base_url=f"{base}/openai")
    handler.scripts["/openai"] = [{"choices": [{"message": {"tool_calls": [{
        "id": "c1", "function": {"name": "github__list_issues", "arguments": "{}"}}]}}]}]
    broker = SecretsBroker()
    tok = broker.issue_run_token(org, dept, "run_denied", allowed_mcps=["github"])
    with pytest.raises(PermissionError):
        _adapter(broker).execute_with_tools(
            db=db, run_token=tok.token, provider="openai", model="gpt-4o",
            system_prompt="", user_prompt="go", tools=TOOLS)


def test_pii_redacted_before_leaving_platform_and_budget_enforced(db, provider_server):
    base, handler = provider_server
    org, dept = _org_dept(db)
    db.save_org_llm_credential(org, "openai", "openai-key-ABCDEFGHIJ", base_url=f"{base}/openai")
    handler.scripts["/openai"] = [{"choices": [{"message": {"content": "ok"}}]}]
    broker = SecretsBroker()
    tok = broker.issue_run_token(org, dept, "run_pii")
    _adapter(broker).execute_with_tools(
        db=db, run_token=tok.token, provider="openai", model="gpt-4o", system_prompt="",
        user_prompt="mail bob@corp.com token ghp_abcdefghijklmnopqrstuvwxyz1234")
    sent = json.dumps(handler.seen[-1][2])
    assert "bob@corp.com" not in sent and "ghp_abcdefghijklmnop" not in sent

    with pytest.raises(PermissionError):                              # estimated cost > remaining budget
        _adapter(broker).execute_with_tools(
            db=db, run_token=tok.token, provider="openai", model="gpt-4o", system_prompt="",
            user_prompt="x", estimated_cost_usd=999.0)


# ---------------------------------------------------------------- notification policy matrix
@pytest.mark.parametrize("policy,event,status,override,expected", [
    ("FINAL_ONLY", "WORKFLOW_START", "RUNNING", False, False),
    ("FINAL_ONLY", "STEP_COMPLETE", "COMPLETED", False, False),
    ("FINAL_ONLY", "STEP_COMPLETE", "COMPLETED", True, True),
    ("FINAL_ONLY", "WORKFLOW_END", "COMPLETED", False, True),
    ("START_AND_END", "WORKFLOW_START", "RUNNING", False, True),
    ("START_AND_END", "STEP_COMPLETE", "COMPLETED", False, False),
    ("START_AND_END", "WORKFLOW_END", "FAILED", False, True),
    ("EVERY_STEP", "STEP_COMPLETE", "COMPLETED", False, True),
    ("ON_FAILURE_ONLY", "WORKFLOW_END", "COMPLETED", False, False),
    ("ON_FAILURE_ONLY", "WORKFLOW_END", "FAILED", False, True),
])
def test_notification_policy_matrix(policy, event, status, override, expected):
    binding = {"provider": "telegram", "channel_id": "1", "notify_policy": policy}
    assert should_send_notification(binding, event, status, override) is expected


# ---------------------------------------------------------------- engine-level counts + step logs
def _telegram_sends(db):
    with db._get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM mcp_tool_calls WHERE tool_id = 'tool_telegram_send_message'").fetchone()[0]


@pytest.mark.parametrize("policy,expected", [
    ("FINAL_ONLY", 1), ("START_AND_END", 2), ("EVERY_STEP", 4), ("ON_FAILURE_ONLY", 0),
])
def test_engine_sends_expected_number_of_notifications(db, policy, expected):
    db.save_agent(AgentConfig(id="ceo-orchestrator", name="CEO", description="d",
                              system_prompt="p", model="default"))
    wf_id = f"wf_{uuid.uuid4().hex[:6]}"
    definition = {
        "id": wf_id, "name": "Notify WF",
        "metadata": {"channel_binding": {"provider": "telegram", "channel_id": "123", "notify_policy": policy}},
        "steps": [
            {"key": "a", "name": "A", "agent_id": "agent-a", "prompt_template": "one"},
            {"key": "b", "name": "B", "agent_id": "agent-b", "depends_on": ["a"], "prompt_template": "two"},
        ],
    }
    db.create_workflow(id=wf_id, name="Notify WF", definition_json=json.dumps(definition))
    res = WorkflowEngine(db_manager=db).execute_workflow(wf_id, trigger_type="MANUAL")
    assert res.status == "COMPLETED"
    assert _telegram_sends(db) == expected

    logs = get_execution_step_logs(db, res.id)
    assert {s["step_key"] for s in logs["steps"]} == {"a", "b"}
    only_b = get_execution_step_logs(db, res.id, step_key="b")
    assert [s["step_key"] for s in only_b["steps"]] == ["b"]


# ---------------------------------------------------------------- SSRF + tenant authorization
def test_base_url_ssrf_validation(monkeypatch):
    from persistence_modules.llm_keys_repo import validate_provider_base_url

    monkeypatch.setenv("ENV", "dev")
    assert validate_provider_base_url("https://api.openai.com/v1/chat/completions")
    assert validate_provider_base_url("http://127.0.0.1:9999/x")            # loopback http ok in dev only
    for bad in ("http://example.com/x", "ftp://example.com", "https://user:pw@example.com", "not a url"):
        with pytest.raises(ValueError):
            validate_provider_base_url(bad)

    monkeypatch.setenv("ENV", "production")
    for bad in ("http://api.openai.com/v1", "https://169.254.169.254/latest", "https://127.0.0.1/x",
                "https://10.0.0.5/x", "https://localhost/x", "https://metadata.google.internal/x"):
        with pytest.raises(ValueError):
            validate_provider_base_url(bad)
    assert validate_provider_base_url("https://integrate.api.nvidia.com/v1/chat/completions")


def test_vault_routes_enforce_org_membership_and_admin_role():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.security.tokens import create_access_token

    def hdr(org, role):
        tok = create_access_token({"sub": "u1", "email": "u@x.io", "org_id": org, "role": role}, 3600)
        return {"Authorization": f"Bearer {tok}"}

    body = {"provider": "openai", "api_key": "sk-test-key-0123456789"}
    with TestClient(app) as c:
        org = f"org_authz_{uuid.uuid4().hex[:6]}"
        url = f"/api/v1/organizations/{org}/llm-keys"
        assert c.post(url, json=body, headers=hdr(org, "ORG_ADMIN")).status_code == 201
        assert c.post(url, json=body, headers=hdr("org_other", "ORG_ADMIN")).status_code == 403   # other tenant
        assert c.post(url, json=body, headers=hdr(org, "MEMBER")).status_code == 403              # not admin
        assert c.get(url, headers=hdr("org_other", "ORG_ADMIN")).status_code == 403
        listed = c.get(url, headers=hdr(org, "MEMBER"))                                           # members may list
        assert listed.status_code == 200 and "sk-test-key-0123456789" not in listed.text
        evil = c.post(url, json=dict(body, base_url="http://evil.example.com/x"), headers=hdr(org, "ORG_ADMIN"))
        assert evil.status_code == 400                                                            # SSRF-ish url rejected
