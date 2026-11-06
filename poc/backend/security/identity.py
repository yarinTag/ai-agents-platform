"""Current-database identities and department roles; JWTs identify, not authorize."""
from dataclasses import dataclass
from fastapi import HTTPException

LEVELS = {"MEMBER": 1, "OPERATOR": 2, "MANAGER": 3, "ORG_ADMIN": 4}


@dataclass
class Actor:
    db: object
    organization_id: str
    user_id: str | None
    role: str
    departments: dict
    selected_department: str | None = None
    service: str | None = None

    @property
    def admin(self):
        return self.role == "ORG_ADMIN"

    def allows(self, department_id=None, level=1, selected=True):
        if department_id:
            if selected and self.selected_department and department_id != self.selected_department:
                return False
            return self.departments.get(department_id, 0) >= level
        # Organization-wide configuration is never delegated by an unrelated dept role.
        return self.admin or (level == 1 and bool(self.departments))

    def require(self, department_id=None, level=1, selected=True):
        if not self.allows(department_id, level, selected):
            raise HTTPException(403, "This action is not permitted in the selected scope.")

    def default_department(self, level=1):
        if self.selected_department:
            self.require(self.selected_department, level)
            return self.selected_department
        return next((department for department, rank in self.departments.items() if rank >= level), None)


def load_actor(request, db):
    claims = getattr(request.state, "user", None) or {}
    org_id = claims.get("org_id")
    if not org_id or not db.get_organization(org_id):
        raise HTTPException(401, "The organization session is no longer valid.")
    service = claims.get("service")
    if service:
        # authenticate_request is the sole producer of these server-owned service claims.
        if service not in ("api_key", "open_development"):
            raise HTTPException(401, "Invalid service identity.")
        role, user_id = "ORG_ADMIN", None
    else:
        user_id = claims.get("sub")
        user = db.get_user(user_id) if user_id else None
        if not user or user.status != "ACTIVE" or user.organization_id != org_id:
            raise HTTPException(401, "The user session is no longer valid.")
        role = user.role
        if role not in LEVELS:
            raise HTTPException(403, "Unrecognized account role.")
        # Replace stale role/email claims before existing endpoint-specific checks run.
        request.state.user = {**claims, "role": role, "email": user.email}
    if role == "ORG_ADMIN":
        departments = {d.id: 4 for d in db.list_departments(organization_id=org_id) if d}
    else:
        departments = {m["department_id"]: min(LEVELS[role], LEVELS.get(m.get("department_role"), 0))
                       for m in db.get_user_departments(user_id)
                       if m.get("organization_id") == org_id and m.get("department_id")}
        departments = {key: value for key, value in departments.items() if value > 0}
    if not service:
        role_names = {rank: name for name, rank in LEVELS.items()}
        request.state.user = {**request.state.user, "departments": [
            {"id": department, "role": role_names[rank]}
            for department, rank in departments.items()]}
    selected = request.headers.get("X-Department-ID", "").strip() or None
    if request.url.path.rstrip("/") == "/api/v1/auth/me":
        selected = None  # Profile refresh must recover from revoked/deleted selections.
    if not selected and request.url.path.rstrip("/") == "/api/v1/events/stream":
        selected = request.query_params.get("department_id") or None
    if selected and selected not in departments:
        raise HTTPException(403, "The selected department is not authorized.")
    return Actor(db, org_id, user_id, role, departments, selected, service)
