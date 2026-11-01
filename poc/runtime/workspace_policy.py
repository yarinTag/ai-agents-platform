"""Allow-list for agent working directories.

Agents read, write and (when permitted) run commands in their working directory,
so a project or agent path must fall inside an operator-approved root.
PLATFORM_WORKSPACE_ROOTS lists approved roots separated by os.pathsep (':' on
POSIX). The platform-owned poc/workspaces directory is always allowed and hosts
the default workspace for runs without a project. The filesystem root and the
home directory itself are never accepted as roots.
"""
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

PLATFORM_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent / "workspaces"
DEFAULT_WORKSPACE = PLATFORM_WORKSPACE_ROOT / "default"


class WorkspacePolicyError(ValueError):
    """Raised when a requested working directory is outside the approved roots."""


def allowed_roots() -> List[Path]:
    roots = [PLATFORM_WORKSPACE_ROOT]
    forbidden = {Path(Path.home().anchor).resolve(), Path.home().resolve()}
    for raw in os.environ.get("PLATFORM_WORKSPACE_ROOTS", "").split(os.pathsep):
        if not raw.strip():
            continue
        root = Path(raw.strip()).expanduser().resolve()
        if root in forbidden:
            logger.warning("Ignoring workspace root %s: too broad to be an approved root", root)
            continue
        if root not in roots:
            roots.append(root)
    return roots


def resolve_workspace(candidate: Optional[str]) -> str:
    """Return an approved absolute working directory, creating it only inside a root."""
    roots = allowed_roots()
    if not candidate or not candidate.strip():
        path = DEFAULT_WORKSPACE
    else:
        raw = Path(candidate.strip()).expanduser()
        if not raw.is_absolute():
            raise WorkspacePolicyError("Workspace path must be absolute.")
        path = raw.resolve()
        if not any(path.is_relative_to(root) for root in roots):
            raise WorkspacePolicyError(
                f"Workspace '{candidate.strip()}' is outside the approved roots. "
                "Ask an operator to add its parent folder to PLATFORM_WORKSPACE_ROOTS."
            )
    path.mkdir(parents=True, exist_ok=True)
    final = path.resolve()
    if not any(final.is_relative_to(root) for root in roots):
        raise WorkspacePolicyError("Workspace path escapes the approved roots.")
    return str(final)
