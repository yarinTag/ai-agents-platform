"""
Automated tests for Phase 6: Security, Authentication, and Production Hardening.
ZERO MOCKS POLICY: Validates against live FastAPI app, SQLite persistence, and runtime adapter.
"""

import pytest
import os
import tempfile
from httpx import AsyncClient, ASGITransport

from config import AgentConfig, AgentRole
from persistence import DatabaseManager
from runtime_adapter import ClaudeCodeRuntimeAdapter
from backend.main import app
from backend.dependencies import get_db_manager


@pytest.fixture
def temp_db():
    """Create an isolated real SQLite DB with default schema and seed templates."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    yield db
    if os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_correlation_id_middleware():
    """Test that all requests receive and propagate X-Correlation-ID headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Auto-generated correlation ID
        resp1 = await client.get("/health")
        assert resp1.status_code == 200
        assert "x-correlation-id" in resp1.headers
        assert resp1.headers["x-correlation-id"].startswith("req_")

        # Propagated client-provided correlation ID
        custom_id = "trace-test-uuid-9999"
        resp2 = await client.get("/health", headers={"X-Correlation-ID": custom_id})
        assert resp2.status_code == 200
        assert resp2.headers.get("x-correlation-id") == custom_id


@pytest.mark.asyncio
async def test_structured_error_responses():
    """Test that HTTP errors are returned in a standardized JSON error envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents/non-existent-agent-id-12345")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == 404
        assert "Agent not found" in data["error"]["detail"]
        assert "correlation_id" in data["error"]
        assert "timestamp" in data["error"]


@pytest.mark.asyncio
async def test_api_key_authentication(monkeypatch):
    """Test API Key and Bearer token authentication enforcement."""
    transport = ASGITransport(app=app)

    # 1. Open development mode when PLATFORM_API_KEY is not set
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200

    # 2. Strict enforcement when PLATFORM_API_KEY is set
    monkeypatch.setenv("PLATFORM_API_KEY", "platform-secret-key-42")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Public exempt endpoints still work without auth
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200

        status_resp = await client.get("/api/v1/auth/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["configured"] is True

        # Protected endpoints reject without auth
        unauth_resp = await client.get("/api/v1/agents")
        assert unauth_resp.status_code == 401

        # Reject with wrong key
        wrong_resp = await client.get("/api/v1/agents", headers={"X-API-Key": "wrong-key"})
        assert wrong_resp.status_code == 401

        # Accept with valid X-API-Key header
        header_resp = await client.get("/api/v1/agents", headers={"X-API-Key": "platform-secret-key-42"})
        assert header_resp.status_code == 200

        # Accept with valid Bearer token
        bearer_resp = await client.get("/api/v1/agents", headers={"Authorization": "Bearer platform-secret-key-42"})
        assert bearer_resp.status_code == 200

        # Accept with valid query param
        query_resp = await client.get("/api/v1/agents?api_key=platform-secret-key-42")
        assert query_resp.status_code == 200


@pytest.mark.asyncio
async def test_audit_logging_and_api(temp_db):
    """Test security audit log persistence and retrieval API."""
    app.dependency_overrides[get_db_manager] = lambda: temp_db

    try:
        # Record direct audit entries
        temp_db.log_audit(
            action="SECURITY_CONFIG_CHANGE",
            actor="admin",
            entity_type="system",
            entity_id="platform",
            details={"setting": "dangerously_skip_permissions", "old": True, "new": False}
        )
        temp_db.log_audit(
            action="API_KEY_ROTATED",
            actor="admin",
            entity_type="auth",
            entity_id="key-1"
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/audit/logs")
            assert resp.status_code == 200
            logs = resp.json()
            assert len(logs) >= 2

            actions = [l["action"] for l in logs]
            assert "SECURITY_CONFIG_CHANGE" in actions
            assert "API_KEY_ROTATED" in actions

            # Filter by action
            filter_resp = await client.get("/api/v1/audit/logs?action=SECURITY_CONFIG_CHANGE")
            assert filter_resp.status_code == 200
            filtered = filter_resp.json()
            assert len(filtered) == 1
            assert filtered[0]["details"]["setting"] == "dangerously_skip_permissions"

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_runtime_adapter_security_and_tool_permissions(monkeypatch):
    """Test configurable --dangerously-skip-permissions, allowed tools, and env credentials."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://custom-fcc-host:9999")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "custom-secret-token")
    monkeypatch.setenv("PLATFORM_DANGEROUSLY_SKIP_PERMISSIONS", "false")

    adapter = ClaudeCodeRuntimeAdapter()
    assert adapter.proxy_url == "http://custom-fcc-host:9999"
    assert adapter.auth_token == "custom-secret-token"

    env = adapter._build_claude_env()
    assert env["ANTHROPIC_BASE_URL"] == "http://custom-fcc-host:9999"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "custom-secret-token"

    # Default agent has dangerously_skip_permissions = False
    agent_safe = AgentConfig(
        id="safe-agent",
        name="Safe Agent",
        description="Safe agent without skip permissions",
        system_prompt="Execute carefully.",
        dangerously_skip_permissions=False,
        allowed_tools=["read_files", "grep_search"]
    )

    cmd_safe = adapter._build_claude_command(agent_safe, None, "test prompt")
    assert "--dangerously-skip-permissions" not in cmd_safe
    assert "--allowedTools" in cmd_safe
    tool_idx = cmd_safe.index("--allowedTools")
    assert cmd_safe[tool_idx + 1] == "read_files,grep_search"

    # Agent with explicitly enabled skip permissions
    agent_danger = AgentConfig(
        id="danger-agent",
        name="Danger Agent",
        description="Agent with skip permissions",
        system_prompt="Execute fast.",
        dangerously_skip_permissions=True
    )

    cmd_danger = adapter._build_claude_command(agent_danger, None, "test prompt")
    assert "--dangerously-skip-permissions" in cmd_danger


@pytest.mark.asyncio
async def test_rate_limiter_middleware(monkeypatch):
    """Test that rapid requests trigger 429 when rate limit is exceeded."""
    from backend.security import RateLimiterMiddleware
    RateLimiterMiddleware.clear_history()

    # Set low rate limit for test
    monkeypatch.setenv("PLATFORM_RATE_LIMIT", "3")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Rapid fire requests
        r1 = await client.get("/api/v1/models")
        r2 = await client.get("/api/v1/models")
        r3 = await client.get("/api/v1/models")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

        # 4th request must be rate limited with 429
        r4 = await client.get("/api/v1/models")
        assert r4.status_code == 429
        assert "Retry-After" in r4.headers
        data = r4.json()
        assert "error" in data
        assert data["error"]["code"] == 429
