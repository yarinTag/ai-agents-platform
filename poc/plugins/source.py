"""Resolve plugin source overrides within a single tenant."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PluginSource:
    source_mode: str
    git_repo: str
    local_path: str
    source_department_id: str | None = None


def department_source(conn, organization_id, department_id):
    return conn.execute("""
        SELECT id, parent_department_id, plugins_source_mode, plugins_git_repo
        FROM departments WHERE id=? AND organization_id=?
    """, (department_id, organization_id)).fetchone()


def resolve_source(db, organization_id, department_id=None, parent_agent_id=None):
    org = db.get_organization(organization_id)
    if not org:
        raise ValueError("The plugin organization is unavailable.")
    visited_departments, visited_agents = set(), set()
    with db._get_connection() as conn:
        while department_id or parent_agent_id:
            if department_id and department_id not in visited_departments:
                visited_departments.add(department_id)
                row = department_source(conn, organization_id, department_id)
                if not row:
                    raise ValueError("The plugin department is outside the organization.")
                if row["plugins_source_mode"] == "git":
                    return PluginSource("git", row["plugins_git_repo"] or "", "", row["id"])
                department_id = row["parent_department_id"]
                continue
            if not parent_agent_id or parent_agent_id in visited_agents:
                break
            visited_agents.add(parent_agent_id)
            parent = conn.execute("SELECT department_id, parent_id FROM agents WHERE id=? AND organization_id=?",
                                  (parent_agent_id, organization_id)).fetchone()
            if not parent:
                break
            department_id, parent_agent_id = parent["department_id"], parent["parent_id"]
    return PluginSource(org.plugins_source_mode or "local", org.plugins_git_repo or "", org.plugins_local_path or "")
