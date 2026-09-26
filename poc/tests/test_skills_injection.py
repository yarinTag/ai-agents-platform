"""
Tests for skill resolution, prompt generation, and runtime command injection.
"""

import pytest
from pathlib import Path
from config import AgentConfig, Skill
from persistence import db_manager
from runtime_adapter import ClaudeCodeRuntimeAdapter
from skills_service import resolve_skill, build_skills_system_prompt, clear_skills_cache
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_resolve_marketplace_skill():
    """Test resolving a skill from p-skills marketplace."""
    clear_skills_cache()
    skill = resolve_skill("database-architecture")
    assert skill is not None
    assert skill["id"] == "database-architecture"
    assert "Database Architecture" in skill["name"]
    assert "persistence architecture" in skill["content"].lower() or len(skill["content"]) > 100


def test_resolve_database_custom_skill():
    """Test resolving a custom skill created in the database."""
    clear_skills_cache()
    custom_skill = Skill(
        id="custom-devops-skill",
        name="Custom DevOps Skill",
        description="Handles custom devops pipelines",
        content="# Custom DevOps\nAlways check kubernetes configs before applying."
    )
    db_manager.save_skill(custom_skill)

    resolved = resolve_skill("custom-devops-skill")
    assert resolved is not None
    assert resolved["id"] == "custom-devops-skill"
    assert resolved["name"] == "Custom DevOps Skill"
    assert "kubernetes configs" in resolved["content"]


def test_build_skills_system_prompt():
    """Test generating formatted markdown system prompt section for skills."""
    prompt = build_skills_system_prompt(["database-architecture", "custom-devops-skill"])
    assert "[EQUIPPED SKILLS & DOMAIN METHODOLOGIES]" in prompt
    assert "### SKILL: Database Architecture" in prompt
    assert "### SKILL: Custom DevOps Skill" in prompt


def test_build_claude_command_with_equipped_skills():
    """Test that runtime adapter injects equipped skills into --system-prompt."""
    adapter = ClaudeCodeRuntimeAdapter()

    agent = AgentConfig(
        id="arch_agent",
        name="Senior Architect",
        description="Architect agent",
        system_prompt="You are a senior system architect.",
        skills=["database-architecture"]
    )

    cmd = adapter._build_claude_command(
        agent_config=agent,
        project_config=None,
        prompt="Design the database schema for order processing"
    )

    # Verify --system-prompt is present
    assert "--system-prompt" in cmd
    sys_prompt_idx = cmd.index("--system-prompt") + 1
    sys_prompt = cmd[sys_prompt_idx]

    # Verify agent prompt, workspace, and equipped skills are in system prompt
    assert "You are a senior system architect." in sys_prompt
    assert "[PROJECT WORKSPACE]" in sys_prompt
    assert "[EQUIPPED SKILLS & DOMAIN METHODOLOGIES]" in sys_prompt
    assert "Database Architecture" in sys_prompt


def test_build_claude_command_without_skills():
    """Test that runtime adapter does not include skills section when none equipped."""
    adapter = ClaudeCodeRuntimeAdapter()

    agent = AgentConfig(
        id="plain_agent",
        name="Plain Agent",
        description="No skills agent",
        system_prompt="Standard agent instructions.",
        skills=[]
    )

    cmd = adapter._build_claude_command(
        agent_config=agent,
        project_config=None,
        prompt="Simple task"
    )

    sys_prompt_idx = cmd.index("--system-prompt") + 1
    sys_prompt = cmd[sys_prompt_idx]

    assert "Standard agent instructions." in sys_prompt
    assert "[EQUIPPED SKILLS & DOMAIN METHODOLOGIES]" not in sys_prompt


def test_api_plugins_scan_endpoint():
    """Test the /api/v1/skills/plugins/scan endpoint."""
    response = client.get("/api/v1/skills/plugins/scan")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "plugins" in data
    assert data["total_skills"] > 0
