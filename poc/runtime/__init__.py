"""
Runtime package exposing RuntimeAdapter protocol and real implementations.
Zero mocks.
"""

from .protocol import RuntimeAdapter, RuntimeCapabilities
from .claude_adapter import ClaudeCodeAdapter

__all__ = ["RuntimeAdapter", "RuntimeCapabilities", "ClaudeCodeAdapter"]
