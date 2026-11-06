"""Tenant filter for streamed platform events.

Events carry no organization, so ownership is resolved from the event's task,
agent or project. Events that cannot be attributed to the caller's organization
are never streamed (fail closed).
"""
from typing import Any, Dict, Optional, Tuple
import time

_CACHE_LIMIT = 5000


class EventScope:
    def __init__(self, db_manager, scope: Dict[str, Any]):
        self.db = db_manager
        self.org_id: Optional[str] = scope.get("org_id")
        self.is_org_admin = bool(scope.get("is_org_admin"))
        self.department_ids = set(scope.get("department_ids") or [])
        self.user_id = scope.get("user_id")
        self.selected_department = scope.get("selected_department_id")
        self.expires_at = scope.get("expires_at")
        self._owners: Dict[Tuple[Optional[str], ...], Optional[dict]] = {}

    def allows(self, event) -> bool:
        if not self.org_id or (self.expires_at and time.time() > self.expires_at):
            return False
        if self.user_id:
            user = self.db.get_user(self.user_id)
            if not user or user.status != "ACTIVE" or user.organization_id != self.org_id:
                return False
            self.is_org_admin = user.role == "ORG_ADMIN"
            self.department_ids = {m["department_id"] for m in self.db.get_user_departments(self.user_id)
                                   if m.get("organization_id") == self.org_id and m.get("department_role") in ("MEMBER", "OPERATOR", "MANAGER", "ORG_ADMIN")}
        key = (event.task_id, event.agent_id, event.project_id)
        # Ownership/membership can move or be revoked while a stream remains open.
        owner = self.db.get_event_owner(*key)
        if not owner or owner["organization_id"] != self.org_id:
            return False
        department = owner.get("department_id")
        # Org-wide subjects (no department) are visible to every member of the organization.
        if department and self.selected_department and department != self.selected_department:
            return False
        return self.is_org_admin or (bool(self.department_ids) and (department is None or department in self.department_ids))
