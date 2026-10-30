"""Optional queue startup/shutdown owned by the backend composition root."""
import logging
from .capabilities import capabilities

logger = logging.getLogger(__name__)
_broker = None
_worker = None


async def start_queue():
    global _broker, _worker
    if not capabilities.enabled("queue"):
        capabilities.mark("queue", "DISABLED")
        return
    try:
        from .queue.broker import get_message_broker
        _broker = get_message_broker()
        await _broker.connect()
        capabilities.mark("queue", "DEGRADED" if _broker.is_fallback else "READY",
                          "Process-local fallback; messages are not durable" if _broker.is_fallback else None)
    except Exception:
        logger.exception("Optional queue broker unavailable")
        capabilities.mark("queue", "UNAVAILABLE", "Broker initialization failed")
        return
    if not capabilities.enabled("queue-worker"):
        capabilities.mark("queue-worker", "DISABLED")
        return
    try:
        from .dependencies import get_runtime_adapter, get_event_bus, get_db_manager, get_workflow_engine
        from .queue.worker import get_queue_worker
        _worker = get_queue_worker()
        _worker.runtime_adapter = get_runtime_adapter()
        _worker.event_bus = get_event_bus()
        _worker.db_manager = get_db_manager()
        if capabilities.enabled("workflows"):
            try:
                _worker.workflow_engine = get_workflow_engine()
            except Exception:
                logger.warning("Queue worker workflow handler unavailable")
        await _worker.start()
        capabilities.mark("queue-worker", "READY")
    except Exception:
        logger.exception("Optional queue worker unavailable")
        capabilities.mark("queue-worker", "UNAVAILABLE", "Worker initialization failed")
        if _worker:
            try:
                await _worker.stop()
            except Exception:
                logger.exception("Partial queue worker cleanup failed")
            finally:
                _worker = None


async def stop_queue():
    global _broker, _worker
    for name, resource, close in (("queue-worker", _worker, "stop"), ("queue", _broker, "disconnect")):
        if resource is None:
            continue
        capabilities.mark(name, "STOPPING")
        try:
            await getattr(resource, close)()
        except Exception:
            logger.exception("Optional %s shutdown failed", name)
        finally:
            capabilities.mark(name, "UNAVAILABLE", "Stopped")
    _worker = _broker = None
