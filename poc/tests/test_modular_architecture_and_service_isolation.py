"""
Integration Tests for Modular Architecture, Shared Utilities, and Fault-Tolerant Service Isolation.
Zero-Mocks Policy: Runs against real FastAPI instances, real ServiceRegistry, and real SQLite.
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

POC_DIR = Path(__file__).resolve().parent.parent
if str(POC_DIR) not in sys.path:
    sys.path.insert(0, str(POC_DIR))

from shared.validators import (
    normalize_email,
    validate_email_domain,
    parse_allowed_tools,
    slugify_identifier,
)
from shared.notifications import resolve_telegram_target_chat
from shared.service_registry import ServiceRegistry, ServiceSpec
from backend.main import app


def test_shared_validators_rule_of_two():
    """Verify shared validators handle email normalization, corporate domain checks, and tool parsing."""
    assert normalize_email("  Alice.Lead@Acme.IO ") == "alice.lead@acme.io"
    assert validate_email_domain("alice@acme.io", "acme.io") is True
    assert validate_email_domain("bob@eng.acme.io", "@acme.io") is True
    assert validate_email_domain("intruder@evil.com", "acme.io") is False

    raw_all, list_all = parse_allowed_tools("*")
    assert raw_all == "*"
    assert list_all == ["*"]

    raw_list, list_parsed = parse_allowed_tools(["git_status", "git_diff"])
    assert list_parsed == ["git_status", "git_diff"]
    assert "git_status" in raw_list

    raw_csv, list_csv = parse_allowed_tools("read_file, list_dir")
    assert list_csv == ["read_file", "list_dir"]

    assert slugify_identifier("Acme Cyber Corp 2026!") == "acme-cyber-corp-2026"


def test_shared_notification_target_resolution():
    """Verify Telegram placeholder and bot username resolution to configured chat_id."""
    assert resolve_telegram_target_chat("@agents_office_alerts", "1176967752") == "1176967752"
    assert resolve_telegram_target_chat("my_custom_bot", "1176967752") == "1176967752"
    assert resolve_telegram_target_chat("-100998877", "1176967752") == "-100998877"


def test_service_registry_fault_tolerance_and_isolation(monkeypatch):
    """
    Verify that if a service is disabled or broken/disconnected, the rest of the application
    continues to boot and serve requests normally.
    """
    monkeypatch.setenv("DISABLED_SERVICES", "war_room")
    isolated_app = FastAPI()
    registry = ServiceRegistry()

    specs = [
        ServiceSpec("audit", "backend.api.audit", "/api/v1/audit", ["audit"], requires_auth=False),
        ServiceSpec("war_room", "backend.war_room.router", "/api/v1/war-room", ["war-room"], requires_auth=False),
        ServiceSpec("non_existent_service", "backend.api.does_not_exist_xyz", "/api/v1/ghost", ["ghost"], requires_auth=False),
    ]

    registry.mount_all(isolated_app, specs, auth_dependencies=[])
    statuses = {s["name"]: s for s in registry.get_status_list()}

    assert statuses["audit"]["status"] == "MOUNTED"
    assert statuses["war_room"]["status"] == "DISABLED"
    assert statuses["non_existent_service"]["status"] == "DEGRADED"
    assert "No module named" in (statuses["non_existent_service"]["error"] or "")


def test_platform_services_status_endpoint():
    """Verify main application exposes /api/v1/services/status with all core services mounted."""
    client = TestClient(app)
    res = client.get("/api/v1/services/status")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 15
    assert data["mounted"] == data["total"]
    assert data["degraded"] == 0
    service_names = {s["name"] for s in data["services"]}
    assert {"agents", "workflows", "mcp", "organizations", "projects", "tasks"}.issubset(service_names)
