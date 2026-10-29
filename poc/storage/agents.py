"""Agents persistence operations; dependencies are injected callbacks."""
from config import AgentConfig
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import sqlite3


class AgentsRepository:
    def __init__(self, connection_factory, create_agent_session, max_agents):
        self._get_connection = connection_factory
        self.create_agent_session = create_agent_session
        self._max_agents = max_agents

    def _row_to_agent(self, row: sqlite3.Row) -> AgentConfig:
        """Convert a database row to an AgentConfig instance."""
        keys = row.keys()
        allowed_children = json.loads(row['allowed_child_ids']) if 'allowed_child_ids' in keys and row['allowed_child_ids'] else []
        allowed_tools = json.loads(row['allowed_tools']) if 'allowed_tools' in keys and row['allowed_tools'] else []

        return AgentConfig(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            system_prompt=row['system_prompt'],
            skills=json.loads(row['skills']) if row['skills'] else [],
            model=row['model'],
            effort=row['effort'],
            max_tokens=row['max_tokens'],
            temperature=row['temperature'],
            repo_path=row['repo_path'] if 'repo_path' in keys else None,
            github_url=row['github_url'] if 'github_url' in keys else None,
            department=row['department'] if 'department' in keys and row['department'] else 'Engineering',
            avatar=row['avatar'] if 'avatar' in keys else None,
            created_at=str(row['created_at']) if 'created_at' in keys and row['created_at'] else None,
            updated_at=str(row['updated_at']) if 'updated_at' in keys and row['updated_at'] else None,
            parent_id=row['parent_id'] if 'parent_id' in keys else None,
            role_type=row['role_type'] if 'role_type' in keys and row['role_type'] else 'WORKER',
            max_concurrent_children=row['max_concurrent_children'] if 'max_concurrent_children' in keys and row['max_concurrent_children'] is not None else 3,
            delegation_strategy=row['delegation_strategy'] if 'delegation_strategy' in keys and row['delegation_strategy'] else 'hierarchical',
            allowed_child_ids=allowed_children,
            allowed_tools=allowed_tools,
            template_id=row['template_id'] if 'template_id' in keys else None,
            dangerously_skip_permissions=bool(row['dangerously_skip_permissions']) if 'dangerously_skip_permissions' in keys and row['dangerously_skip_permissions'] is not None else False,
            allow_sibling_communication=bool(row['allow_sibling_communication']) if 'allow_sibling_communication' in keys and row['allow_sibling_communication'] is not None else True,
            allowed_peer_ids=json.loads(row['allowed_peer_ids']) if 'allowed_peer_ids' in keys and row['allowed_peer_ids'] else [],
            mcp_permissions=json.loads(row['mcp_permissions']) if 'mcp_permissions' in keys and row['mcp_permissions'] else [],
            runtime_provider=row['runtime_provider'] if 'runtime_provider' in keys and row['runtime_provider'] else None,
            is_workflow_agent=bool(row['is_workflow_agent']) if 'is_workflow_agent' in keys and row['is_workflow_agent'] is not None else False,
            workflow_id=row['workflow_id'] if 'workflow_id' in keys else None,
            organization_id=row['organization_id'] if 'organization_id' in keys else None,
            department_id=row['department_id'] if 'department_id' in keys else None
        )

    def save_agent(self, agent: AgentConfig):
        """Save or update an agent with organizational hierarchy attributes."""
        with self._get_connection() as conn:
            existing = conn.execute("SELECT created_at FROM agents WHERE id = ?", (agent.id,)).fetchone()
            if not existing:
                is_wf = bool(getattr(agent, "is_workflow_agent", False) or getattr(agent, "role_type", "") == "WORKFLOW_AUTOMATION")
                if not is_wf:
                    count = conn.execute("SELECT COUNT(*) FROM agents WHERE is_workflow_agent = 0").fetchone()[0]
                    if count >= self._max_agents():
                        raise ValueError(f"Platform agent capacity reached: maximum {self._max_agents()} agents allowed")
            created_at = existing['created_at'] if existing else (getattr(agent, "created_at", None) or datetime.now().isoformat())
            updated_at = datetime.now().isoformat()

            conn.execute("""
                INSERT INTO agents
                (id, name, description, system_prompt, skills, model, effort, max_tokens, temperature,
                 repo_path, github_url, department, avatar, created_at, updated_at,
                 parent_id, role_type, max_concurrent_children, delegation_strategy,
                 allowed_child_ids, allowed_tools, template_id, dangerously_skip_permissions,
                 allow_sibling_communication, allowed_peer_ids, mcp_permissions, runtime_provider,
                 is_workflow_agent, workflow_id, organization_id, department_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    system_prompt=excluded.system_prompt,
                    skills=excluded.skills,
                    model=excluded.model,
                    effort=excluded.effort,
                    max_tokens=excluded.max_tokens,
                    temperature=excluded.temperature,
                    repo_path=excluded.repo_path,
                    github_url=excluded.github_url,
                    department=excluded.department,
                    avatar=excluded.avatar,
                    updated_at=excluded.updated_at,
                    parent_id=excluded.parent_id,
                    role_type=excluded.role_type,
                    max_concurrent_children=excluded.max_concurrent_children,
                    delegation_strategy=excluded.delegation_strategy,
                    allowed_child_ids=excluded.allowed_child_ids,
                    allowed_tools=excluded.allowed_tools,
                    template_id=excluded.template_id,
                    dangerously_skip_permissions=excluded.dangerously_skip_permissions,
                    allow_sibling_communication=excluded.allow_sibling_communication,
                    allowed_peer_ids=excluded.allowed_peer_ids,
                    mcp_permissions=excluded.mcp_permissions,
                    runtime_provider=excluded.runtime_provider,
                    is_workflow_agent=excluded.is_workflow_agent,
                    workflow_id=excluded.workflow_id,
                    organization_id=COALESCE(excluded.organization_id, agents.organization_id),
                    department_id=COALESCE(excluded.department_id, agents.department_id)
            """, (
                agent.id,
                agent.name,
                agent.description,
                agent.system_prompt,
                json.dumps(agent.skills),
                agent.model,
                agent.effort,
                agent.max_tokens,
                agent.temperature,
                getattr(agent, "repo_path", None),
                getattr(agent, "github_url", None),
                getattr(agent, "department", "Engineering"),
                getattr(agent, "avatar", None),
                str(created_at),
                str(updated_at),
                getattr(agent, "parent_id", None),
                getattr(agent, "role_type", "WORKER"),
                getattr(agent, "max_concurrent_children", 3),
                getattr(agent, "delegation_strategy", "hierarchical"),
                json.dumps(getattr(agent, "allowed_child_ids", []) or []),
                json.dumps(getattr(agent, "allowed_tools", []) or []),
                getattr(agent, "template_id", None),
                1 if getattr(agent, "dangerously_skip_permissions", False) else 0,
                1 if getattr(agent, "allow_sibling_communication", True) else 0,
                json.dumps(getattr(agent, "allowed_peer_ids", []) or []),
                json.dumps(getattr(agent, "mcp_permissions", []) or []),
                getattr(agent, "runtime_provider", None),
                1 if getattr(agent, "is_workflow_agent", False) else 0,
                getattr(agent, "workflow_id", None),
                getattr(agent, "organization_id", None),
                getattr(agent, "department_id", None)
            ))
            conn.commit()

        if not existing:
            try:
                self.create_agent_session(agent.id, title="Session 1", close_existing=False)
            except Exception:
                pass

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get an agent by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM agents WHERE id = ?", (agent_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_agent(row)
        return None

    def list_agents(
        self,
        organization_id: Optional[str] = None,
        department_ids: Optional[List[str]] = None
    ) -> List[AgentConfig]:
        """List all agents, strictly scoped by organization and optionally filtered by department_ids."""
        with self._get_connection() as conn:
            query = "SELECT * FROM agents WHERE 1=1"
            params = []
            if organization_id:
                query += " AND organization_id = ?"
                params.append(organization_id)
            if department_ids is not None:
                if not department_ids:
                    return []
                placeholders = ",".join("?" for _ in department_ids)
                query += f" AND department_id IN ({placeholders})"
                params.extend(department_ids)
            query += " ORDER BY name"
            cursor = conn.execute(query, params)
            return [self._row_to_agent(row) for row in cursor.fetchall()]

    def get_child_agents(self, parent_id: str) -> List[AgentConfig]:
        """Get all direct child agents managed by a parent agent."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agents WHERE parent_id = ? ORDER BY name", (parent_id,))
            return [self._row_to_agent(row) for row in cursor.fetchall()]

    def get_agent_hierarchy(
        self,
        root_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        department_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build an organizational hierarchy tree.
        If root_id is provided, returns the subtree rooted at that agent.
        Otherwise, returns all tree hierarchies from root agents (parent_id is NULL).
        """
        all_agents = self.list_agents(organization_id=organization_id, department_ids=department_ids)
        agents_by_parent: Dict[Optional[str], List[AgentConfig]] = {}
        for a in all_agents:
            pid = a.parent_id
            if pid not in agents_by_parent:
                agents_by_parent[pid] = []
            agents_by_parent[pid].append(a)

        def build_node(agent: AgentConfig) -> Dict[str, Any]:
            node = agent.to_dict()
            node["children"] = [build_node(c) for c in agents_by_parent.get(agent.id, [])]
            return node

        if root_id:
            root = self.get_agent(root_id)
            return [build_node(root)] if root else []

        root_agents = agents_by_parent.get(None, [])
        return [build_node(r) for r in root_agents]

    def delete_agent(self, agent_id: str):
        """Delete an agent and clean up any linked task runs, messages, permissions, and hierarchy relationships."""
        with self._get_connection() as conn:
            conn.execute("UPDATE agents SET parent_id = NULL WHERE parent_id = ?", (agent_id,))
            conn.execute("DELETE FROM team_members WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_teams WHERE manager_agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM mcp_agent_permissions WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_messages WHERE from_agent_id = ? OR to_agent_id = ?", (agent_id, agent_id))
            conn.execute("DELETE FROM agent_interactions WHERE requester_agent_id = ? OR target_approver_id = ?", (agent_id, agent_id))
            conn.execute("DELETE FROM chat_messages WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_conversations WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM task_runs WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM super_agent_configs WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()
