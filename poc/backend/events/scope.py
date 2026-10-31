"""Tenant filter for streamed platform events.

Events carry no organization, so ownership is resolved from the event's task,
agent or project. Events that cannot be attributed to the caller's organization
are never streamed (fail closed).
"""
from typing import Any, Dict, Optional, Tuple

_CACHE_LIMIT = 5000


class EventScope:
    def __init__(self, db_manager, scope: Dict[str, Any]):
        self.db = db_manager
        self.org_id: Optional[str] = scope.get("org_id")
        self.is_org_admin = bool(scope.get("is_org_admin"))
        self.department_ids = set(scope.get("department_ids") or [])
        self._owners: Dict[Tuple[Optional[str], ...], Optional[dict]] = {}

    def allows(self, event) -> bool:
        if not self.org_id:
            return False
        key = (event.task_id, event.agent_id, event.project_id)
        if key not in self._owners:
            if len(self._owners) >= _CACHE_LIMIT:
                self._owners.clear()
            self._owners[key] = self.db.get_event_owner(*key)
        owner = self._owners[key]
        if not owner or owner["organization_id"] != self.org_id:
            return False
        department = owner.get("department_id")
        # Org-wide subjects (no department) are visible to every member of the organization.
        return self.is_org_admin or department is None or department in self.department_ids
