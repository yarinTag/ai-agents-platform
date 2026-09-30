"""
Tests for runtime provider selection.

Zero mocks: detection runs against the real machine, env building against real
os.environ copies, and the API through a real TestClient and SQLite database.
"""

import os
import pytest
from fastapi.testclient import TestClient

import runtime_providers as providers
from config import AgentConfig
from persistence import db_manager
from runtime_adapter import ClaudeCodeRuntimeAdapter
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def restore_provider_settings():
    """Preserve and restore the saved provider selection around each test."""
    saved = db_manager.get_setting(providers.SETTING_PROVIDER)
    saved_done = db_manager.get_setting(providers.SETTING_SETUP_COMPLETED)
    saved_gateway = db_manager.get_setting(providers.SETTING_GATEWAY_URL)
    saved_env = os.environ.get("PLATFORM_RUNTIME_PROVIDER")
    yield
    for key, value in (
        (providers.SETTING_PROVIDER, saved),
        (providers.SETTING_SETUP_COMPLETED, saved_done),
        (providers.SETTING_GATEWAY_URL, saved_gateway),
    ):
        if value is None:
            db_manager.delete_setting(key)
        else:
            db_manager.set_setting(key, value)
    if saved_env is None:
        os.environ.pop("PLATFORM_RUNTIME_PROVIDER", None)
    else:
        os.environ["PLATFORM_RUNTIME_PROVIDER"] = saved_env


# --- Detection ---

def test_detect_providers_covers_every_registered_provider():
    """Detection returns a status for all four providers with usable detail text."""
    statuses = providers.detect_providers()
    assert [s.id for s in statuses] == providers.ALL_PROVIDER_IDS
    for status in statuses:
        assert status.detail, f"{status.id} must explain its availability"
        assert isinstance(status.available, bool)


def test_detect_unknown_provider_rejected():
    with pytest.raises(providers.ProviderConfigurationError):
        providers.detect_provider("openai_direct")


# --- Env construction (the actual routing bug) ---

def test_native_provider_strips_inherited_proxy_vars():
    """
    Native CLI auth must win over a proxy URL inherited from the platform's
    own environment — otherwise a stale export silently hijacks the run.
    """
    base = dict(os.environ)
    base["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8082"
    base["ANTHROPIC_AUTH_TOKEN"] = "freecc"

    env = providers.build_provider_env(providers.PROVIDER_CLAUDE_CODE_NATIVE, base)

    assert "ANTHROPIC_BASE_URL" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY" not in env


def test_free_claude_code_provider_sets_proxy_route():
    env = providers.build_provider_env(providers.PROVIDER_FREE_CLAUDE_CODE, dict(os.environ))
    assert env["ANTHROPIC_BASE_URL"] == providers.FREE_CLAUDE_CODE_DEFAULT_URL
    assert env["ANTHROPIC_AUTH_TOKEN"]
    assert env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "1"


def test_anthropic_api_provider_requires_key():
    base = dict(os.environ)
    base.pop("ANTHROPIC_API_KEY", None)
    had_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        with pytest.raises(providers.ProviderConfigurationError):
            providers.build_provider_env(providers.PROVIDER_ANTHROPIC_API, base)
    finally:
        if had_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = had_key


def test_custom_gateway_rejects_non_http_url():
    with pytest.raises(providers.ProviderConfigurationError):
        providers.build_provider_env(
            providers.PROVIDER_CUSTOM_GATEWAY,
            dict(os.environ),
            gateway_base_url="file:///etc/passwd",
        )


def test_custom_gateway_accepts_valid_url():
    env = providers.build_provider_env(
        providers.PROVIDER_CUSTOM_GATEWAY,
        dict(os.environ),
        gateway_base_url="https://gateway.internal:4000/",
    )
    assert env["ANTHROPIC_BASE_URL"] == "https://gateway.internal:4000"


def test_unknown_provider_rejected_in_env_build():
    with pytest.raises(providers.ProviderConfigurationError):
        providers.build_provider_env("gpt_direct", dict(os.environ))


# --- Resolution precedence ---

def test_agent_override_beats_saved_default():
    adapter = ClaudeCodeRuntimeAdapter()
    db_manager.set_setting(providers.SETTING_PROVIDER, providers.PROVIDER_FREE_CLAUDE_CODE)
    os.environ.pop("PLATFORM_RUNTIME_PROVIDER", None)

    agent = AgentConfig(
        id="provider_override_agent",
        name="Override Agent",
        description="Agent pinned to native auth",
        system_prompt="You are pinned.",
        runtime_provider=providers.PROVIDER_CLAUDE_CODE_NATIVE,
    )

    assert adapter.resolve_runtime_provider(agent) == providers.PROVIDER_CLAUDE_CODE_NATIVE
    # With no agent override, the saved default applies.
    assert adapter.resolve_runtime_provider(None) == providers.PROVIDER_FREE_CLAUDE_CODE


def test_saved_default_used_when_no_override():
    adapter = ClaudeCodeRuntimeAdapter()
    os.environ.pop("PLATFORM_RUNTIME_PROVIDER", None)
    db_manager.set_setting(providers.SETTING_PROVIDER, providers.PROVIDER_ANTHROPIC_API)
    assert adapter.resolve_runtime_provider() == providers.PROVIDER_ANTHROPIC_API


def test_resolution_falls_back_to_native():
    adapter = ClaudeCodeRuntimeAdapter()
    os.environ.pop("PLATFORM_RUNTIME_PROVIDER", None)
    db_manager.delete_setting(providers.SETTING_PROVIDER)
    assert adapter.resolve_runtime_provider() == providers.PROVIDER_CLAUDE_CODE_NATIVE


def test_agent_runtime_provider_persists_roundtrip():
    agent = AgentConfig(
        id="provider_persist_agent",
        name="Persist Agent",
        description="Round-trips its provider choice",
        system_prompt="You persist.",
        runtime_provider=providers.PROVIDER_FREE_CLAUDE_CODE,
    )
    db_manager.save_agent(agent)
    loaded = db_manager.get_agent("provider_persist_agent")
    assert loaded.runtime_provider == providers.PROVIDER_FREE_CLAUDE_CODE


# --- API ---

def test_get_runtime_setup_state(client):
    response = client.get("/api/v1/runtimes/")
    assert response.status_code == 200
    body = response.json()
    assert len(body["providers"]) == len(providers.ALL_PROVIDER_IDS)
    assert "setup_completed" in body
    assert body["effective_provider"] in providers.ALL_PROVIDER_IDS


def test_select_provider_persists_and_marks_setup_complete(client):
    db_manager.delete_setting(providers.SETTING_SETUP_COMPLETED)
    os.environ.pop("PLATFORM_RUNTIME_PROVIDER", None)

    # Only select a provider this machine can actually serve.
    target = providers.suggest_default_provider()
    if target is None:
        pytest.skip("No runtime provider is usable on this machine")

    response = client.put("/api/v1/runtimes/selection", json={"provider_id": target})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["setup_completed"] is True
    assert body["selected_provider"] == target
    assert db_manager.get_setting(providers.SETTING_PROVIDER) == target


def test_select_unknown_provider_rejected(client):
    response = client.put("/api/v1/runtimes/selection", json={"provider_id": "openai_direct"})
    assert response.status_code == 400
    assert "Unknown runtime provider" in response.json()["detail"]


def test_select_unavailable_provider_rejected(client):
    """An unusable provider fails at selection time, not mid-run."""
    status = providers.detect_provider(providers.PROVIDER_ANTHROPIC_API)
    if status.available:
        pytest.skip("ANTHROPIC_API_KEY is set, so this provider is usable here")
    response = client.put(
        "/api/v1/runtimes/selection",
        json={"provider_id": providers.PROVIDER_ANTHROPIC_API},
    )
    assert response.status_code == 400
    assert "not usable on this machine" in response.json()["detail"]


def test_custom_gateway_selection_requires_url(client):
    response = client.put(
        "/api/v1/runtimes/selection",
        json={"provider_id": providers.PROVIDER_CUSTOM_GATEWAY},
    )
    assert response.status_code == 400
    assert "gateway base URL is required" in response.json()["detail"]


def test_agent_create_rejects_unknown_provider(client):
    response = client.post(
        "/api/v1/agents/",
        json={
            "name": "Bad Provider Agent",
            "system_prompt": "You are invalid.",
            "runtime_provider": "openai_direct",
        },
    )
    assert response.status_code == 422
