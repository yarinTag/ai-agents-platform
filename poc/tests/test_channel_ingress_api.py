"""Real guarded FastAPI and SQLite contracts for provider event admission."""
import hashlib
import hmac
import json
import time

import pytest

from poc.tests.test_generic_governance_api import auth, baseline
from storage import channel_ingress
from integrations.ingress_tls import _global

BASE = "/api/v1/channel-ingress"
ADMIN = "/api/v1/governance/channel-ingress"
SECRET = "private-fixture-" + "s" * 36


def configure(client, db, provider):
    connector_id = f"atlas_{provider}"
    if provider == "telegram":
        connector = db.get_mcp_connector(connector_id)
        connector.configuration["bot_token"] = "123456:fixture"
        db.save_mcp_connector(connector)
        payload = {"secret": SECRET}
    else:
        payload = {"secret": SECRET, "team_id": "T12345678", "app_id": "A12345678"}
    response = client.put(f"/api/v1/governance/external-identities/connectors/{connector_id}/secret",
                          headers=auth(), json=payload)
    assert response.status_code == 204, response.text
    return connector_id


def slack_headers(raw, timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    signature = hmac.new(SECRET.encode(), f"v0:{timestamp}:".encode() + raw, hashlib.sha256).hexdigest()
    return {"X-Slack-Request-Timestamp": str(timestamp), "X-Slack-Signature": f"v0={signature}"}


def telegram_message(update_id=1, message_id=2, text="untrusted fixture"):
    return {"update_id": update_id, "message": {"message_id": message_id, "date": int(time.time()),
        "chat": {"id": 12345, "type": "private"}, "from": {"id": 12345, "is_bot": False}, "text": text}}


def telegram_headers():
    return {"X-Telegram-Bot-Api-Secret-Token": SECRET}


def test_telegram_atomic_dedup_and_diagnostics(baseline, monkeypatch):
    db, client = baseline
    connector = configure(client, db, "telegram")
    monkeypatch.setenv("PLATFORM_INGRESS_PUBLIC_URL", "https://ingress.example.test")
    path = f"{BASE}/{connector}"
    headers = telegram_headers()
    assert client.post(path, json=telegram_message()).status_code == 403
    assert client.post(path, json=telegram_message(), headers=headers).status_code == 202
    assert client.post(path, json=telegram_message(), headers=headers).status_code == 200
    assert client.post(path, json=telegram_message(update_id=3), headers=headers).status_code == 200
    assert client.post(path, json=telegram_message(update_id=3, message_id=4), headers=headers).status_code == 202
    assert client.get(f"{ADMIN}/{connector}/diagnostics", headers=auth(org="boreal")).status_code == 404
    assert client.get(f"{ADMIN}/{connector}/diagnostics", headers=auth("MANAGER")).status_code == 403
    result = client.get(f"{ADMIN}/{connector}/diagnostics", headers=auth())
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["webhook_url"] == f"https://ingress.example.test{path}"
    assert value["ssl_status"] == "UNVERIFIED" and value["last_verified_at"] is not None
    assert [event["status"] for event in value["recent_events"]] == ["QUEUED", "QUEUED"]
    assert value["recent_failures"][0]["code"] == "INVALID_PROOF"
    assert "untrusted fixture" not in result.text and SECRET not in result.text
    probe = client.post(f"{ADMIN}/{connector}/test", headers=auth())
    assert probe.json()["status"] == "READY" and probe.json()["live_request"] is False
    with db._get_connection() as conn:
        assert conn.execute("SELECT count(*) FROM channel_ingress_outbox").fetchone()[0] == 2
        assert conn.execute("SELECT sender_id FROM channel_ingress_events LIMIT 1").fetchone()[0] == "12345"


def test_telegram_private_identity_proof_shares_receiver_without_staging_code(baseline):
    db, client = baseline
    connector = configure(client, db, "telegram")
    issued = client.post(f"/api/v1/governance/external-identities/connectors/{connector}/challenges", headers=auth())
    challenge = issued.json()
    proof = telegram_message(text="/start " + challenge["code"])
    assert client.post(f"{BASE}/{connector}", json=proof, headers=telegram_headers()).status_code == 200
    status = client.get(f"/api/v1/governance/external-identities/challenges/{challenge['id']}", headers=auth())
    assert status.json()["subject"] == "12345"
    with db._get_connection() as conn:
        assert conn.execute("SELECT count(*) FROM channel_ingress_events").fetchone()[0] == 0


def test_slack_exact_installation_signature_handshake_and_delivery(baseline):
    db, client = baseline
    connector = configure(client, db, "slack")
    path = f"{BASE}/{connector}"
    handshake = b'{"type":"url_verification","challenge":"sample_challenge"}'
    result = client.post(path, content=handshake, headers=slack_headers(handshake))
    assert result.json() == {"challenge": "sample_challenge"}
    callback = {"type": "event_callback", "event_id": "Ev12345678", "team_id": "T12345678", "api_app_id": "A12345678",
                "event": {"type": "message", "channel": "C12345678", "ts": "1730000000.123",
                          "user": "U12345678", "text": "fixture contents", "response_url": "https://example.test/opaque"}}
    raw = json.dumps(callback).encode()
    assert client.post(path, content=raw + b" ", headers=slack_headers(raw)).status_code == 403
    assert client.post(path, content=raw, headers=slack_headers(raw, int(time.time()) - 301)).status_code == 403
    wrong = json.dumps({**callback, "team_id": "T99999999"}).encode()
    assert client.post(path, content=wrong, headers=slack_headers(wrong)).status_code == 403
    assert client.post(path, content=raw, headers=slack_headers(raw)).status_code == 202
    assert client.post(path, content=raw, headers=slack_headers(raw)).status_code == 200
    with db._get_connection() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM channel_ingress_events")]
    assert len(rows) == 1 and rows[0]["account"] == "T12345678"
    assert "fixture contents" not in repr(rows) and "opaque" not in repr(rows)


def test_signed_slack_command_uses_common_ingress_deduplication(baseline):
    from urllib.parse import urlencode

    db, client = baseline
    connector = configure(client, db, "slack")
    raw = urlencode({
        "command": "/review", "team_id": "T12345678", "api_app_id": "A12345678",
        "channel_id": "C12345678", "user_id": "U12345678", "trigger_id": "1.2.sample",
        "text": "sample", "response_url": "https://example.test/opaque",
    }).encode()
    headers = {**slack_headers(raw), "Content-Type": "application/x-www-form-urlencoded"}
    path = f"{BASE}/{connector}"
    assert client.post(path, content=raw, headers=headers).status_code == 202
    assert client.post(path, content=raw, headers=headers).status_code == 200
    claim = channel_ingress.claim(db)
    assert claim["event"]["event_type"] == "COMMAND"
    assert claim["event"]["event_id"] == "command:1.2.sample"
    assert claim["trigger_text"] is None


def test_outbox_lease_and_retry_are_fenced(baseline):
    db, client = baseline
    connector = configure(client, db, "telegram")
    assert client.post(f"{BASE}/{connector}", json=telegram_message(), headers=telegram_headers()).status_code == 202
    now = int(time.time()) + 1
    first = channel_ingress.claim(db, now)
    assert first["attempt"] == 1 and channel_ingress.claim(db, now) is None
    identifier = first["event"]["id"]
    assert not channel_ingress.settle(db, identifier, "wrong-token", success=True, now=now)
    assert channel_ingress.settle(db, identifier, first["lease_token"], success=False, retryable=True, now=now)
    assert channel_ingress.claim(db, now + 9) is None
    second = channel_ingress.claim(db, now + 10)
    third = channel_ingress.claim(db, now + 10 + channel_ingress.LEASE_SECONDS)
    assert second["attempt"] == 2 and third["attempt"] == 3
    assert not channel_ingress.settle(db, identifier, second["lease_token"], success=True, now=now + 70)
    assert channel_ingress.settle(db, identifier, third["lease_token"], success=True, now=now + 70)
    assert channel_ingress.claim(db, now + 1000) is None


def test_connector_rate_limit_returns_backoff_but_acks_duplicates(baseline, monkeypatch):
    db, client = baseline
    connector = configure(client, db, "telegram")
    monkeypatch.setattr(channel_ingress, "RATE_PER_MINUTE", 1)
    path = f"{BASE}/{connector}"
    headers = telegram_headers()
    assert client.post(path, json=telegram_message(), headers=headers).status_code == 202
    assert client.post(path, json=telegram_message(), headers=headers).status_code == 200
    blocked = client.post(path, json=telegram_message(update_id=3, message_id=4), headers=headers)
    assert blocked.status_code == 429 and blocked.headers["Retry-After"] == "60"
    assert client.post(path, content=b"x" * 65537, headers=headers).status_code == 413


def test_tls_probe_only_accepts_public_unicast_addresses():
    for address in ("127.0.0.1", "169.254.169.254", "224.0.0.1", "::1", "::ffff:127.0.0.1", "fe80::1%en0"):
        assert not _global(address)
    assert _global("8.8.8.8")
    assert _global("2606:4700:4700::1111")


def test_telegram_approval_callback_is_bound_to_message_and_votes_once(baseline):
    from integrations.telegram_approval_cards import action_token, signed_action
    from storage import channel_approval_delivery as delivery, dag_approvals

    db, client = baseline
    connector = configure(client, db, "telegram")
    binding = client.post("/api/v1/governance/channel-bindings", headers=auth(), json={
        "department_id": "atlas_engineering", "connector_id": connector, "provider": "telegram",
        "channel_id": "12345", "uses": {"approve_decisions": True, "send_notifications": True},
    })
    assert binding.status_code == 201, binding.text
    workflow = db.create_workflow(id="telegram-approval", name="Telegram approval", definition_json="{}",
                                  department_id="atlas_engineering", organization_id="atlas")
    db.create_workflow_execution("approval-run", workflow.id, "MANUAL", department_id=workflow.department_id)
    identifier = dag_approvals.suspend(db, execution_id="approval-run", step_key="review",
        revision=workflow.revision, initiator_id="atlas_OPERATOR",
        policy={"approver_roles": ["MANAGER"], "quorum": 1, "timeout_seconds": 60,
                "channel_binding_id": binding.json()["id"]},
        checkpoint={"outputs": {}, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0})
    assert delivery.next_delivery(db)["id"] == identifier
    token = action_token(db.get_mcp_connector(connector).configuration["bot_token"], identifier)
    delivery.record_delivery(db, identifier, "DELIVERED", connector=connector, channel="12345",
                             message="7", bot="123456", rendered="PENDING:0/1", token=token)
    with db._get_connection() as conn:
        conn.execute("""INSERT INTO external_identity_links
            (id,organization_id,connector_id,user_id,provider,account,subject,created_at)
            VALUES ('linked-manager','atlas',?,'atlas_MANAGER','telegram','123456','12345',?)""",
            (connector, int(time.time())))
    update = {"callback_query": {"id": "123", "data": f"dga:a:{token}:{signed_action(SECRET, token, 'a')}", "from": {"id": 12345, "is_bot": False},
        "message": {"message_id": 8, "chat": {"id": 12345}, "from": {"id": 123456}}}}
    path = f"{BASE}/{connector}"
    assert client.post(path, json=update, headers=telegram_headers()).json()["text"].startswith("Decision unavailable")
    update["callback_query"]["message"]["message_id"] = 7
    for _ in range(2):
        assert client.post(path, json=update, headers=telegram_headers()).json()["text"] == "Decision recorded."
    with db._get_connection() as conn:
        assert conn.execute("SELECT count(*) FROM dag_channel_callbacks").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM workflow_dag_approval_votes").fetchone()[0] == 1
    assert delivery.next_edit(db)[1] == "APPROVED"


def test_channel_trigger_preview_and_fenced_admission(baseline):
    from workflows.channel_trigger_dispatch import admit_dispatch, reserve_dispatches

    db, client = baseline
    connector = configure(client, db, "telegram")
    binding = client.post("/api/v1/governance/channel-bindings", headers=auth(), json={
        "department_id": "atlas_engineering", "connector_id": connector, "provider": "telegram",
        "channel_id": "12345", "uses": {"trigger_workflows": True},
    })
    assert binding.status_code == 201, binding.text
    db.create_workflow(id="trigger-contract", name="Trigger contract", department_id="atlas_engineering",
                       organization_id="atlas", definition_json="{}")
    path = "/api/v1/workflows/trigger-contract/channel-trigger"
    rule = {"binding_id": binding.json()["id"], "enabled": True, "matcher": "keyword",
            "pattern": "review", "parameters": {"subject": "text"}}
    payload = {"expected_revision": 1, "rule": rule}
    assert client.put(path, headers=auth("MEMBER"), json=payload).status_code == 404
    saved = client.put(path, headers=auth("MANAGER"), json=payload)
    assert saved.status_code == 200, saved.text
    assert client.put(path, headers=auth("MANAGER"), json=payload).status_code == 409
    preview = client.post(path + "/preview", headers=auth("MANAGER"), json={
        "rule": rule, "event": {"event_type": "MESSAGE", "channel_id": "ignored", "message_id": "preview",
                                "text": "Please REVIEW"},
    })
    assert preview.json() == {"matched": True, "parameters": {"subject": "Please REVIEW"}}
    with db._get_connection() as conn:
        assert not conn.execute("SELECT 1 FROM workflow_executions").fetchone()
        conn.execute("""INSERT INTO external_identity_links
            (id,organization_id,connector_id,user_id,provider,account,subject,created_at)
            VALUES ('linked-operator','atlas',?,'atlas_OPERATOR','telegram','123456','12345',?)""",
            (connector, int(time.time())))
    response = client.post(f"{BASE}/{connector}", json=telegram_message(text="Please REVIEW"), headers=telegram_headers())
    assert response.status_code == 202, response.text
    claim = channel_ingress.claim(db)
    execution_id, = reserve_dispatches(db, claim)
    assert reserve_dispatches(db, claim) == [execution_id]
    workflow = db.get_workflow("trigger-contract")
    assert admit_dispatch(db, execution_id, workflow, "expired-lease") is None
    db.update_user("atlas_OPERATOR", status="INACTIVE")
    assert admit_dispatch(db, execution_id, workflow, claim["lease_token"]) is None
    db.update_user("atlas_OPERATOR", status="ACTIVE")
    assert admit_dispatch(db, execution_id, workflow, claim["lease_token"]) == (
        {"subject": "Please REVIEW"}, {"sub": "atlas_MANAGER", "org_id": "atlas"},
    )
    assert admit_dispatch(db, execution_id, workflow, claim["lease_token"]) is None


def test_dag_approval_resume_preserves_prior_barrier_runs(baseline):
    from workflows.engine import WorkflowEngine
    from storage import dag_approvals

    db, client = baseline
    definition = {"name": "Approval contract", "steps": [
        {"key": key, "name": key, "agent_id": "atlas_engineering",
         "depends_on": deps, "params": {"dag_approval": {"quorum": 2}}}
        for key, deps in [("first", []), ("second", ["first"])]
    ]}
    workflow = db.create_workflow(id="dag-contract", name=definition["name"],
                                  department_id="atlas_engineering", organization_id="atlas",
                                  definition_json=json.dumps(definition))
    context = {"sub": "atlas_OPERATOR", "org_id": "atlas"}
    execution = WorkflowEngine(db_manager=db).execute_workflow(workflow.id, user_context=context)
    assert execution.status == "WAITING_APPROVAL"
    base = "/api/v1/workflows/dag-approvals"
    scope = {"department_id": "atlas_engineering"}
    first, = client.get(base, params=scope, headers=auth("MANAGER")).json()["items"]
    path = f"{base}/{first['id']}/decision"
    assert client.post(path, params=scope, headers=auth("OPERATOR"), json={"approve": True}).status_code == 403
    assert client.post(path, params=scope, headers=auth("MANAGER"), json={"approve": True}).json() == {"status": "PENDING"}
    assert client.post(path, params=scope, headers=auth("MANAGER"), json={"approve": True}).status_code == 409
    assert client.post(path, params=scope, headers=auth(), json={"approve": True}).json() == {"status": "APPROVED"}
    resumed = WorkflowEngine(db_manager=db).execute_workflow(workflow.id, dag_approval_id=first["id"])
    assert resumed.id == execution.id and resumed.status == "WAITING_APPROVAL"
    second, = client.get(base, params=scope, headers=auth()).json()["items"]
    assert second["step_key"] == "second"
    assert second["outputs"] == [{"step_key": "first", "excerpt": "Approved", "truncated": False}]
    assert dag_approvals.claim_resume(db, first["id"], workflow.id, workflow.revision) is None
    assert client.post(f"{base}/{second['id']}/decision", params=scope,
                       headers=auth(), json={"approve": False}).json() == {"status": "REJECTED"}
    assert db.get_workflow_execution(execution.id).status == "FAILED"
    with db._get_connection() as conn:
        assert [tuple(row) for row in conn.execute("""SELECT step_key,status FROM workflow_step_runs
            WHERE execution_id=? ORDER BY step_key""", (execution.id,))] == [
            ("first", "COMPLETED"), ("second", "FAILED"),
        ]
