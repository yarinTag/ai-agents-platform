"""Agents: mapping ownership."""

from fastapi import HTTPException, status
from typing import Any, Dict
from datetime import datetime
from ..dependencies import AgentConfig


def agent_to_response(agent: AgentConfig) -> dict:
    now_iso = datetime.now().isoformat()
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "skills": agent.skills or [],
        "model": agent.model,
        "effort": agent.effort,
        "max_tokens": agent.max_tokens,
        "temperature": agent.temperature,
        "repo_path": getattr(agent, "repo_path", None),
        "github_url": getattr(agent, "github_url", None),
        "department": getattr(agent, "department", "Engineering"),
        "avatar": getattr(agent, "avatar", None),
        "created_at": getattr(agent, "created_at", None) or now_iso,
        "updated_at": getattr(agent, "updated_at", None) or now_iso,
        "parent_id": getattr(agent, "parent_id", None),
        "role_type": getattr(agent, "role_type", "WORKER"),
        "max_concurrent_children": getattr(agent, "max_concurrent_children", 3),
        "delegation_strategy": getattr(agent, "delegation_strategy", "hierarchical"),
        "allowed_child_ids": getattr(agent, "allowed_child_ids", []) or [],
        "allowed_tools": getattr(agent, "allowed_tools", []) or [],
        "template_id": getattr(agent, "template_id", None),
        "allow_sibling_communication": getattr(agent, "allow_sibling_communication", True),
        "allowed_peer_ids": getattr(agent, "allowed_peer_ids", []) or [],
        "mcp_permissions": getattr(agent, "mcp_permissions", []) or [],
        "runtime_provider": getattr(agent, "runtime_provider", None),
        "is_workflow_agent": getattr(agent, "is_workflow_agent", False) or False,
        "workflow_id": getattr(agent, "workflow_id", None),
        "organization_id": getattr(agent, "organization_id", None),
        "department_id": getattr(agent, "department_id", None)
    }



def _check_agent_scope(agent: AgentConfig, scope: Dict[str, Any]):
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    if org_id and getattr(agent, "organization_id", None) and agent.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if not is_org_admin and getattr(agent, "department_id", None) and authorized_dept_ids and agent.department_id not in authorized_dept_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access agent in this department")

