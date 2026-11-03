"""Execution engines are independent of model providers and credentials.

This inventory describes implemented platform integrations, not vendor promises.
Discovering a binary/image never makes a backend executable automatically.
"""
from dataclasses import asdict, dataclass
from enum import Enum
from types import MappingProxyType
from typing import Optional


class ExecutionBackend(str, Enum):
    DIRECT_API = 'direct_api'
    CLAUDE_CODE = 'claude_code'
    CODEX_CLI = 'codex_cli'
    ANTIGRAVITY_CLI = 'antigravity_cli'


class BackendUnavailable(ValueError):
    """Explicit selection cannot run; never substitute a different backend."""


@dataclass(frozen=True)
class BackendDescriptor:
    id: ExecutionBackend
    name: str
    transport: str
    implemented: bool
    requires_container: bool
    supports_playground: bool
    supports_governed_connectors: bool
    credential_provider: Optional[str]
    unavailable_reason: Optional[str] = None

    def public(self):
        configured, configuration_error = self.implemented, None
        if self.id == ExecutionBackend.CLAUDE_CODE:
            try:
                from .claude_hosted.policy import configured_image
                configured_image()
            except ValueError as exc:
                configured, configuration_error = False, str(exc)
        return {**asdict(self), 'id': self.id.value, 'configured': configured,
                'configuration_error': configuration_error,
                'supports_session_resume': self.id == ExecutionBackend.DIRECT_API, 'verification': 'source_contract_only'}


_CLI_BLOCKED = ('Isolated agent hosting, credential proxy, per-call policy enforcement '
                'and lifecycle integration are not implemented for this backend.')
BACKENDS = MappingProxyType({
    ExecutionBackend.DIRECT_API: BackendDescriptor(
        ExecutionBackend.DIRECT_API, 'Direct API', 'platform_worker', True, False,
        True, True, None),
    ExecutionBackend.CLAUDE_CODE: BackendDescriptor(
        ExecutionBackend.CLAUDE_CODE, 'Claude Code (Agent SDK)', 'claude_agent_sdk', True, True,
        False, False, 'direct_anthropic'),
    ExecutionBackend.CODEX_CLI: BackendDescriptor(
        ExecutionBackend.CODEX_CLI, 'Codex CLI', 'codex_exec', False, True,
        False, False, 'direct_openai', _CLI_BLOCKED),
    ExecutionBackend.ANTIGRAVITY_CLI: BackendDescriptor(
        ExecutionBackend.ANTIGRAVITY_CLI, 'Antigravity CLI', 'agy_headless', False, True,
        False, False, None, _CLI_BLOCKED),
})


def parse_backend(value=None) -> ExecutionBackend:
    """Only an absent value inherits the legacy direct-API default."""
    if value is None:
        return ExecutionBackend.DIRECT_API
    try:
        return ExecutionBackend(value)
    except (ValueError, TypeError):
        raise ValueError('Unknown execution_backend; use direct_api, claude_code, '
                         'codex_cli or antigravity_cli.') from None


def backend_catalog():
    return [entry.public() for entry in BACKENDS.values()]


def require_backend(value=None, *, playground=False, governed_connectors=False):
    backend = BACKENDS[parse_backend(value)]
    if not backend.implemented:
        raise BackendUnavailable(f'{backend.name}: {backend.unavailable_reason}')
    if backend.id == ExecutionBackend.CLAUDE_CODE:
        from .claude_hosted.policy import configured_image
        configured_image()
    if playground and not backend.supports_playground:
        raise BackendUnavailable(f'{backend.name} does not support tool-free Playground.')
    if governed_connectors and not backend.supports_governed_connectors:
        raise BackendUnavailable(f'{backend.name} does not support governed connector execution.')
    return backend
