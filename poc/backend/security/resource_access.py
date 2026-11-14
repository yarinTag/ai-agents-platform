"""Fail-closed resource ownership, including inherited scope of legacy records."""
import json
from fastapi import HTTPException


def field(record, key, default=None):
    return record.get(key, default) if isinstance(record, dict) else getattr(record, key, default)


class Resources:
    def __init__(self, actor):
        self.actor, self.db = actor, actor.db
        self.cache = {}
        self.execution_steps = {}

    def get(self, kind, identifier):
        key = (kind, identifier)
        if key in self.cache:
            return self.cache[key]
        methods = {"agent": "get_agent", "project": "get_project", "task": "get_task_run",
                   "workflow": "get_workflow", "execution": "get_workflow_execution",
                   "department": "get_department", "organization": "get_organization",
                   "connector": "get_mcp_connector", "schedule": "get_cron_job",
                   "team": "get_agent_team", "war_room": "get_war_room_session",
                   "interaction": "get_interaction", "message": "get_agent_message",
                   "skill": "get_skill", "template": "get_template", "user": "get_user"}
        method = methods.get(kind)
        if kind == "skill" and identifier:
            result = self.db.get_skill(identifier, organization_id=self.actor.organization_id) if self.actor.organization_id else None
        else:
            result = getattr(self.db, method)(identifier) if method and identifier else None
        self.cache[key] = result
        return result

    def owned_catalog(self, kind, identifier):
        with self.db._get_connection() as conn:
            row = conn.execute("SELECT organization_id FROM access_resource_owners WHERE resource_type=? AND resource_id=?",
                               (kind, identifier)).fetchone()
        return row and row["organization_id"] == self.actor.organization_id

    def allows(self, kind, identifier, level=1, seen=None):
        if not isinstance(identifier, str) or not identifier:
            return False
        seen = set() if seen is None else set(seen)
        if (kind, identifier) in seen:
            return False
        seen.add((kind, identifier))
        record = self.get(kind, identifier)
        if record is None:
            return False
        check = lambda child_kind, child_id: self.allows(child_kind, child_id, level, seen)
        if kind == "organization":
            return identifier == self.actor.organization_id and self.actor.allows(level=level)
        if kind == "department":
            return field(record, "organization_id") == self.actor.organization_id and self.actor.allows(identifier, level)
        if kind in ("agent", "project", "workflow", "connector", "user"):
            if field(record, "organization_id") != self.actor.organization_id:
                return False
            if kind == "connector" and not self.actor.admin:
                if level > 1:
                    return False
                return any(self.actor.allows(dept) and self.db.get_department_mcp_access(dept, identifier)
                           for dept in self.actor.departments)
            return self.actor.allows(field(record, "department_id"), level)
        if kind == "execution":
            if not check("workflow", field(record, "workflow_id")) or not self.actor.allows(field(record, "department_id"), level):
                return False
            if identifier not in self.execution_steps:
                with self.db._get_connection() as conn:
                    self.execution_steps[identifier] = [dict(row) for row in conn.execute(
                        "SELECT agent_id,task_run_id FROM workflow_step_runs WHERE execution_id=?", (identifier,)).fetchall()]
            for step in self.execution_steps[identifier]:
                if step.get("agent_id") and not self.allows("agent", step["agent_id"], 1, seen):
                    return False
                if step.get("task_run_id"):
                    task = self.get("task", step["task_run_id"])
                    if not task or field(task, "organization_id") not in (None, self.actor.organization_id):
                        return False
                    if not self.allows("agent", field(task, "agent_id"), 1, seen):
                        return False
                    if field(task, "project_id") and not self.allows("project", field(task, "project_id"), 1, seen):
                        return False
            return True
        if kind in ("task", "schedule"):
            org = field(record, "organization_id")
            if org and org != self.actor.organization_id:
                return False
            if kind == "task":
                origin = self.db.get_task_workflow_context(identifier)
                execution_id = origin.get("workflow_execution_id")
                if execution_id and not check("execution", execution_id):
                    return False
            return check("agent", field(record, "agent_id")) and (
                not field(record, "project_id") or self.allows("project", field(record, "project_id"), 1, seen))
        if kind == "interaction":
            return check("task", field(record, "task_id")) and check("agent", field(record, "requester_agent_id"))
        if kind == "message":
            sender, receiver = field(record, "from_agent_id"), field(record, "to_agent_id")
            # Human approval answers have no sender-agent record; task is their ownership anchor.
            return check("agent", receiver) and (check("agent", sender) or
                (sender and not self.get("agent", sender) and check("task", field(record, "task_id"))))
        if kind in ("team", "war_room"):
            leader = field(record, "manager_agent_id" if kind == "team" else "moderator_agent_id")
            if not check("agent", leader):
                return False
            project = field(record, "project_id")
            if project and not self.allows("project", project, 1, seen):
                return False
            members = field(record, "members", []) if kind == "team" else field(record, "participant_agent_ids", [])
            if isinstance(members, str):
                try:
                    members = json.loads(members)
                except ValueError:
                    return False
            return all(check("agent", member if isinstance(member, str) else field(member, "agent_id")) for member in members)
        if kind == "skill":
            if field(record, "organization_id") is None:
                return bool(field(record, "is_system") and not field(record, "project_id")
                            and level == 1 and self.actor.allows(level=level))
            project = field(record, "project_id")
            return check("project", project) if project else self.actor.allows(level=level)
        if kind == "template":
            return self.owned_catalog(kind, identifier) and self.actor.allows(level=level)
        return False

    def require(self, kind, identifier, level=1):
        if not self.allows(kind, identifier, level):
            # Same result for absent, orphaned, foreign-tenant and unauthorized-department IDs.
            raise HTTPException(404, "Resource not found in the authorized scope.")
        return self.get(kind, identifier)
