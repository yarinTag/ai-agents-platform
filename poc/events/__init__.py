"""
Events system for AI Agents Office Platform.

Provides strongly-typed event models, persistent SQLite event log with monotonic sequence numbers,
in-process asyncio.Queue event bus with drop protection, and EventService coordinator.
"""

from .models import EventType, PlatformEvent
from .bus import EventBus
from .service import EventService

__all__ = [
    "EventType",
    "PlatformEvent",
    "EventBus",
    "EventService",
]
