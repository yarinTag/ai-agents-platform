"""Fan out runtime events without consuming the executor's input queue."""

import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict
from .models import TaskStatus

logger = logging.getLogger(__name__)
_END = object()


@dataclass(eq=False)
class _Listener:
    events: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1000))
    stopped: threading.Event = field(default_factory=threading.Event)


class RuntimeSubscriptions:
    """Each subscriber owns a bounded queue and an independent callback thread."""

    def __init__(self):
        self._listeners: Dict[str, set] = {}
        self._lock = threading.Lock()

    def subscribe(self, run_id: str, handler: Callable[[Dict[str, Any]], None]):
        listener = _Listener()
        with self._lock:
            self._listeners.setdefault(run_id, set()).add(listener)

        def unsubscribe():
            listener.stopped.set()
            with self._lock:
                listeners = self._listeners.get(run_id)
                if listeners:
                    listeners.discard(listener)
                    if not listeners:
                        self._listeners.pop(run_id, None)

        def consume():
            try:
                while not listener.stopped.is_set():
                    try:
                        event = listener.events.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if event is _END:
                        break
                    handler(event)
            except Exception:
                logger.debug("Runtime subscriber failed for %s", run_id, exc_info=True)
            finally:
                unsubscribe()

        threading.Thread(target=consume, daemon=True).start()
        return unsubscribe

    def publish(self, run_id: str, event: Dict[str, Any]):
        with self._lock:
            listeners = tuple(self._listeners.get(run_id, ()))
        for listener in listeners:
            try:
                listener.events.put_nowait(event)
            except queue.Full:
                # A stalled optional consumer must not block the task executor.
                listener.stopped.set()
                with self._lock:
                    current = self._listeners.get(run_id)
                    if current:
                        current.discard(listener)
                        if not current:
                            self._listeners.pop(run_id, None)
                logger.warning("Stopped overloaded runtime subscriber for %s", run_id)

    def close_run(self, run_id: str):
        with self._lock:
            listeners = tuple(self._listeners.pop(run_id, ()))
        for listener in listeners:
            try:
                listener.events.put_nowait(_END)
            except queue.Full:
                listener.stopped.set()


def subscribe_to_events(adapter, run_id, handler):
    """Compatibility function preserving the facade's callback API."""
    run = adapter._runs.get(run_id)
    if run is None or run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        return lambda: None
    return adapter._subscriptions.subscribe(run_id, handler)
