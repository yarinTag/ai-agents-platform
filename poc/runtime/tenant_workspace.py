"""Server-owned tenant/department file roots; independent of HTTP or model providers."""
import os
import re
from pathlib import Path


def tenant_root(organization_id):
    if not organization_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", organization_id):
        raise ValueError("A valid organization is required for workspace access.")
    base = Path(os.getenv("PLATFORM_TENANT_STORAGE_ROOT", str(Path(__file__).resolve().parents[1] / "workspaces" / "tenants"))).resolve()
    root = (base / organization_id).resolve()
    if not root.is_relative_to(base) or root == base:
        raise ValueError("Invalid tenant workspace root.")
    return root


def tenant_workspace(organization_id, department_id=None, candidate=None, shared=False, create=False):
    root = tenant_root(organization_id)
    if shared:
        permitted = [root / "shared"]
    else:
        if not department_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", department_id):
            raise ValueError("A valid department is required for workspace access.")
        permitted = [root / "departments" / department_id, root / "shared"]
    resolved_roots = [directory.resolve() for directory in permitted]
    # Reject symlinked department/shared roots that leave the tenant partition.
    if any(not directory.is_relative_to(root) for directory in resolved_roots):
        raise ValueError("Tenant workspace root escapes its organization.")
    target = Path(candidate).expanduser().resolve() if candidate else resolved_roots[0] / "workspace"
    if not any(target.is_relative_to(directory) for directory in resolved_roots):
        raise ValueError("Workspace access is limited to the tenant's department or shared files.")
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target
