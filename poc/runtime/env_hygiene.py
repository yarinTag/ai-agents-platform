"""Remove platform secrets from environments handed to agent processes and shells.

Agents run model-directed tools, so anything in their environment is reachable by
prompt injection. Only the provider credential a run needs survives, plus names an
operator explicitly approves in PLATFORM_AGENT_ENV_PASSTHROUGH (comma-separated).
"""
import os
import re
from typing import Dict, Iterable

# Name fragments that mark a variable as a credential.
_SECRET_NAME = re.compile(
    r"(SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY|CREDENTIAL|SIGNING|_DSN$|^DATABASE_URL$)",
    re.IGNORECASE,
)


def _passthrough() -> set:
    raw = os.environ.get("PLATFORM_AGENT_ENV_PASSTHROUGH", "")
    return {name.strip() for name in raw.split(",") if name.strip()}


def strip_secrets(env: Dict[str, str], keep: Iterable[str] = ()) -> Dict[str, str]:
    """Return a copy of env without secret-looking variables except those in keep."""
    allowed = set(keep) | _passthrough()
    return {k: v for k, v in env.items() if k in allowed or not _SECRET_NAME.search(k)}
