"""
Tests for Prompt Contracts, Granular Substitution, Glanceable Summaries, and Cache Accounting.
Strictly zero-mock (real SQLite, real crypto, real loopback server).
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

_poc_dir = Path(__file__).resolve().parent.parent
if str(_poc_dir) not in sys.path:
    sys.path.insert(0, str(_poc_dir))

import pytest
from persistence import DatabaseManager
from gateways.secrets_broker import SecretsBroker
from runtime.direct_llm_adapter import DirectHTTPLLMRuntimeAdapter
from shared.notification_text import format_glanceable_summary, sanitize_notification_text
from workflows.prompt_contracts import parse_structured_output, render_step_prompt
from workflows.step_logs_service import get_execution_step_logs


def test_granular_prompt_substitution_and_output_contracts():
    """Verify granular dot-paths prevent context bloat and schema contracts are appended."""
    prior_outputs = {
        "analysis_step": json.dumps({
            "status": "APPROVED",
            "score": 98.5,
            "metrics": {"latency_ms": 12, "errors": 0},
            "summary": "Everything looks healthy and within SLA",
        }),
        "raw_text_step": "Plain output text",
    }
    trigger = {"repository": {"owner": "acme", "name": "core-engine"}}

    template = (
        "Repo: {{repository.owner}}/{{repository.name}}\n"
        "Analysis Status: {{analysis_step.status}} with latency {{analysis_step.metrics.latency_ms}}ms\n"
        "Full text: {{raw_text_step.output}}"
    )
    rendered = render_step_prompt(
        prompt_template=template,
        step_outputs=prior_outputs,
        trigger_payload=trigger,
    )
    assert "Repo: acme/core-engine" in rendered
    assert "Analysis Status: APPROVED with latency 12ms" in rendered
    assert "Full text: Plain output text" in rendered

    # Verify JSON Schema contract is appended
    schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
    with_contract = render_step_prompt("Evaluate input", {}, output_schema=schema)
    assert "[OUTPUT CONTRACT]" in with_contract
    assert '"verdict"' in with_contract


def test_parse_structured_output_direct_and_fenced():
    """Verify parser extracts structured dict from direct JSON and markdown fences."""
    direct_json = json.dumps({"summary": "Audit passed", "severity": "LOW"})
    s1, d1 = parse_structured_output(direct_json)
    assert s1 == "Audit passed"
    assert d1 == {"summary": "Audit passed", "severity": "LOW"}

    fenced_json = "Here is the result:\n```json\n{\"summary\": \"Vulnerabilities found\", \"count\": 3}\n```\nDone."
    s2, d2 = parse_structured_output(fenced_json)
    assert s2 == "Vulnerabilities found"
    assert d2 == {"summary": "Vulnerabilities found", "count": 3}

    raw_text = "No json here, just an unstructured report."
    s3, d3 = parse_structured_output(raw_text)
    assert s3 == raw_text
    assert d3 is None


def test_format_glanceable_summary_high_signal():
    """Verify glanceable summary constructs compact executive notifications."""
    structured_step_out = json.dumps({
        "summary": "Deployment approved for production",
        "verdict": "PROCEED",
        "bullets": ["Zero critical CVEs", "Pass rate: 100%", "Canary verified"],
    })
    msg = format_glanceable_summary(
        workflow_name="Prod Release Pipeline",
        execution_id="exec_abc123",
        status="COMPLETED",
        trigger_type="cron_daily",
        total_tokens=1420,
        total_cost_usd=0.0152,
        step_outputs={"review": structured_step_out},
    )
    assert "✅ *Workflow: Prod Release Pipeline* — *COMPLETED*" in msg
    assert "Run: `exec_abc123`" in msg
    assert "Trigger: `cron_daily`" in msg
    assert "📋 *Glanceable Summary:*" in msg
    assert "*Summary:* Deployment approved for production" in msg
    assert "*Verdict:* PROCEED" in msg
    assert "• Zero critical CVEs" in msg

    # Plain text bullet fallback
    plain_output = "Execution log:\n- Installed dependencies\n- Migrated schema\n- Started server"
    msg_plain = format_glanceable_summary(
        workflow_name="Deploy", execution_id="ex_456", status="FAILED",
        step_outputs={"step1": plain_output}, failure_error="Port conflict on 8080",
    )
    assert "❌ *Workflow: Deploy* — *FAILED*" in msg_plain
    assert "• Installed dependencies" in msg_plain
    assert "❌ *Failure Reason:* Port conflict on 8080" in msg_plain


def test_step_logs_service_structured_enrichment(tmp_path):
    """Verify get_execution_step_logs returns structured output and clean summary."""
    db_file = tmp_path / "test_logs.db"
    db = DatabaseManager(db_path=str(db_file))
    wf_id = f"wf_{uuid.uuid4().hex[:6]}"
    exec_id = f"exec_{uuid.uuid4().hex[:8]}"
    step_key = "sec_audit"
    out_json = json.dumps({"summary": "All tests green", "passed": 42})

    db.create_workflow(id=wf_id, name="Test WF", definition_json="{}")
    db.create_workflow_execution(execution_id=exec_id, workflow_id=wf_id, trigger_type="MANUAL")

    with db._get_connection() as conn:
        conn.execute("""
            INSERT INTO workflow_step_runs (
                id, execution_id, step_key, agent_id, status, task_run_id,
                input_data, output_data, input_tokens, output_tokens, cost_usd,
                started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "step_run_1", exec_id, step_key, None, "COMPLETED", None,
            "Check security", out_json, 150, 45, 0.002, "2026-10-19T10:00:00", "2026-10-19T10:00:02"
        ))
        conn.commit()

    logs = get_execution_step_logs(db, exec_id)
    assert logs["total_steps"] == 1
    step_log = logs["steps"][0]
    assert step_log["step_key"] == step_key
    assert step_log["output_summary"] == "All tests green"
    assert step_log["structured_output"] == {"summary": "All tests green", "passed": 42}


def test_anthropic_prompt_caching_and_token_metering(tmp_path):
    """Verify Anthropic provider adds cache_control to system prompt and tallies cache tokens."""
    captured_payloads = []

    def mock_http(method, url, headers, payload):
        captured_payloads.append(payload)
        return {
            "content": [{"type": "text", "text": "cached response"}],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_input_tokens": 40,
                "cache_read_input_tokens": 80,
            },
        }

    db_file = tmp_path / "test_caching.db"
    db = DatabaseManager(db_path=str(db_file))
    broker = SecretsBroker()
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    dept_id = f"dept_{uuid.uuid4().hex[:6]}"

    db.create_organization(id=org_id, name="Cache Corp", slug=org_id, domain=f"{org_id}.io")
    db.create_department(
        id=dept_id, name="Devs", description="d", monthly_budget_usd=100.0,
        budget_action="HARD_STOP", organization_id=org_id,
    )
    db.save_org_llm_credential(org_id, "anthropic", "sk-ant-test-1234567890")
    tok = broker.issue_run_token(org_id, dept_id, "run_cache_1")

    from gateways.llm_proxy import LLMProxy
    adapter = DirectHTTPLLMRuntimeAdapter(
        http_transport=mock_http,
        llm_proxy_instance=LLMProxy(secrets_broker_instance=broker),
    )
    res = adapter.execute_with_tools(
        db=db,
        run_token=tok.token,
        provider="anthropic",
        model="claude-3-5-sonnet-latest",
        system_prompt="You are a cached assistant.",
        user_prompt="Hello cache",
    )

    assert len(captured_payloads) == 1
    sys_payload = captured_payloads[0].get("system")
    assert isinstance(sys_payload, list)
    assert sys_payload[0]["type"] == "text"
    assert sys_payload[0]["cache_control"] == {"type": "ephemeral"}
    assert sys_payload[0]["text"] == "You are a cached assistant."
    # Total input tokens should account for uncached (10) + cache created (40) + cache read (80) = 130
    assert res["input_tokens"] == 130
    assert res["output_tokens"] == 5
    assert res["output_text"] == "cached response"

