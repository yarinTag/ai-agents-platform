"""Baseline seed data; callers own the surrounding transaction."""
from datetime import datetime
from .paths import POC_ROOT
import json
import logging
import sqlite3

def _seed_default_templates(conn: sqlite3.Connection):
    """Seed default reusable agent templates if none exist."""
    cursor = conn.execute("SELECT COUNT(*) FROM agent_templates")
    if cursor.fetchone()[0] > 0:
        return

    defaults = [
        (
            "engineering-manager",
            "Engineering Manager",
            "Coordinates engineering teams, delegates tasks, and synthesizes results.",
            "MANAGER",
            "You are an Engineering Manager. Decompose complex user goals, delegate subtasks to specialized developers, and produce executive summaries of technical work.",
            "default",
            json.dumps(["basic-reading"]),
            json.dumps(["read_files", "grep_search"]),
            json.dumps(["frontend-developer", "backend-developer", "qa-engineer"]),
            "Engineering"
        ),
        (
            "frontend-developer",
            "Frontend Developer",
            "Builds, refactors, and tests modern React, TypeScript, and UI interfaces.",
            "WORKER",
            "You are a Frontend Developer specialized in React 19, TypeScript, Vite, and Ant Design. Build responsive, pixel-perfect, accessible components.",
            "default",
            json.dumps(["basic-reading"]),
            json.dumps(["read_files", "write_to_file", "replace_file_content", "run_command"]),
            json.dumps([]),
            "Engineering"
        ),
        (
            "backend-developer",
            "Backend Developer",
            "Builds scalable Python, FastAPI, and database persistence architectures.",
            "WORKER",
            "You are a Senior Backend Engineer specialized in Python, FastAPI, SQLite, and streaming APIs. Write clean, strongly typed, robust services.",
            "default",
            json.dumps(["basic-reading"]),
            json.dumps(["read_files", "write_to_file", "replace_file_content", "run_command"]),
            json.dumps([]),
            "Engineering"
        ),
        (
            "qa-engineer",
            "QA Engineer",
            "Designs automated test suites, validates acceptance criteria, and verifies zero defects.",
            "SPECIALIST",
            "You are a QA Engineer. Run pytest suites, identify edge cases, write integration tests, and ensure code coverage and regressions are prevented.",
            "default",
            json.dumps(["basic-reading"]),
            json.dumps(["read_files", "run_command"]),
            json.dumps([]),
            "Engineering"
        ),
    ]

    now = datetime.now().isoformat()
    conn.executemany("""
        INSERT OR IGNORE INTO agent_templates
        (id, name, description, role, system_prompt, model, skills, tools, suggested_children, category, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [(d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], d[9], now, now) for d in defaults])


def _seed_default_agents(conn: sqlite3.Connection):
    """Seed default baseline agents (canonical 11 agents) if agents table is empty."""
    cursor = conn.execute("SELECT COUNT(*) FROM agents")
    if cursor.fetchone()[0] > 0:
        return

    agents_file = POC_ROOT / "backend" / "config" / "agents.json"
    defaults = []
    if agents_file.exists():
        try:
            with open(agents_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults = list(data.values()) if isinstance(data, dict) else []
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to read baseline agents from {agents_file}: {e}")

    if not defaults:
        return

    now = datetime.now().isoformat()
    for item in defaults:
        aid = item.get("id")
        if not aid:
            continue
        role_type = item.get("role_type")
        if not role_type:
            if aid == "chief-orchestrator":
                role_type = "ROOT_ORCHESTRATOR"
            elif "lead" in aid:
                role_type = "MANAGER"
            else:
                role_type = "WORKER"

        parent_id = item.get("parent_id")
        if not parent_id:
            if role_type == "MANAGER":
                parent_id = "chief-orchestrator"
            elif aid in ("secuirty", "marketing-content"):
                parent_id = "lead-engineer" if aid == "secuirty" else "marketing-lead"
            elif aid == "general-task-agent":
                parent_id = "operations-lead"

        conn.execute("""
            INSERT OR IGNORE INTO agents
            (id, name, description, system_prompt, skills, model, effort, max_tokens, temperature,
             repo_path, github_url, department, avatar, created_at, updated_at,
             parent_id, role_type, max_concurrent_children, delegation_strategy,
             allowed_child_ids, allowed_tools, template_id, dangerously_skip_permissions,
             allow_sibling_communication, allowed_peer_ids, mcp_permissions, runtime_provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            aid,
            item.get("name", aid),
            item.get("description", ""),
            item.get("system_prompt", "Autonomous agent"),
            json.dumps(item.get("skills", [])),
            item.get("model", "default"),
            item.get("effort", "medium"),
            item.get("max_tokens", 8000),
            item.get("temperature", 0.7),
            item.get("repo_path"),
            item.get("github_url"),
            item.get("department", "Engineering"),
            item.get("avatar", "brain" if aid == "chief-orchestrator" else None),
            now, now,
            parent_id,
            role_type,
            item.get("max_concurrent_children", 3),
            item.get("delegation_strategy", "hierarchical"),
            json.dumps(item.get("allowed_child_ids", [])),
            json.dumps(item.get("allowed_tools", [])),
            item.get("template_id"),
            1 if item.get("dangerously_skip_permissions") else 0,
            1 if item.get("allow_sibling_communication", True) else 0,
            json.dumps(item.get("allowed_peer_ids", [])),
            json.dumps(item.get("mcp_permissions", [])),
            item.get("runtime_provider")
        ))


