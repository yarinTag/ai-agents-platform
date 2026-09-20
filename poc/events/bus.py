"""
In-process EventBus delivering PlatformEvents to subscribers via asyncio.Queue.
Provides event filtering, non-blocking delivery, queue drop protection for slow subscribers,
and unsubscription callbacks.
"""

import asyncio
import logging
from typing import Callable, Optional, Set, Tuple

try:
    from events.models import PlatformEvent
except ImportError:
    from poc.events.models import PlatformEvent

logger = logging.getLogger(__name__)


class _Subscription:
    """Internal representation of an active subscriber subscription."""

    def __init__(
        self,
        queue: asyncio.Queue,
        filter_fn: Optional[Callable[[PlatformEvent], bool]] = None
    ) -> None:
        self.queue = queue
        self.filter_fn = filter_fn

    def matches(self, event: PlatformEvent) -> bool:
        """Check if this subscription is interested in the event."""
        if self.filter_fn is None:
            return True
        try:
            return bool(self.filter_fn(event))
        except Exception as e:
            logger.warning("Subscriber filter function raised an error: %s", e)
            return False


class EventBus:
    """
    In-process asynchronous event bus using asyncio.Queue.
    Delivers events non-blocking to all matching active subscribers.
    """

    def __init__(self, default_queue_size: int = 1000) -> None:
        self._default_queue_size = default_queue_size
        self._subscriptions: Set[_Subscription] = set()

    @property
    def subscriber_count(self) -> int:
        """Return the number of currently active subscribers."""
        return len(self._subscriptions)

    def subscribe(
        self,
        filter_fn: Optional[Callable[[PlatformEvent], bool]] = None
    ) -> Tuple[asyncio.Queue, Callable[[], None]]:
        """
        Subscribe to events on the bus.

        Args:
            filter_fn: Optional predicate function (event -> bool).
                       Only events where filter_fn(event) is True are delivered to the queue.

        Returns:
            A tuple of (queue, unsubscribe_callback).
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._default_queue_size)
        sub = _Subscription(queue=queue, filter_fn=filter_fn)
        self._subscriptions.add(sub)

        def unsubscribe() -> None:
            self._subscriptions.discard(sub)

        return queue, unsubscribe

    def publish(self, event: PlatformEvent) -> None:
        """
        Publish an event to all matching subscriber queues.
        Uses non-blocking put_nowait with queue drop protection to prevent slow
        consumers from blocking the bus or exhausting memory.
        """
        for sub in list(self._subscriptions):
            if not sub.matches(event):
                continue

            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                # Queue drop protection: discard oldest item to make room for newest
                try:
                    sub.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

                try:
                    sub.queue.put_nowait(event)
                    logger.warning(
                        "Subscriber queue was full; dropped oldest event to deliver event_id=%s, seq=%s",
                        event.event_id,
                        event.sequence_number
                    )
                except asyncio.QueueFull:
                    logger.error(
                        "Failed to enqueue event into subscriber queue despite drop protection attempt"
                    )
