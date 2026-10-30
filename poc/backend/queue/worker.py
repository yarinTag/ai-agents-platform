"""Bounded queue consumers with explicit dispatch acceptance and retry limits."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .broker import (
    MessageBroker, get_message_broker, QUEUE_HIGH_PRIORITY, QUEUE_STANDARD,
    QUEUE_BACKGROUND, QUEUE_WORKFLOW_STEPS, QUEUE_WORKFLOW_EXECUTION,
)
from .dispatch import TaskPayloadExecutor, status_value

logger = logging.getLogger(__name__)
QUEUES = (
    QUEUE_HIGH_PRIORITY, QUEUE_STANDARD, QUEUE_BACKGROUND,
    QUEUE_WORKFLOW_STEPS, QUEUE_WORKFLOW_EXECUTION,
)
MAX_RETRIES = 3


class QueueWorkerDaemon:
    def __init__(self, broker: Optional[MessageBroker] = None,
                 runtime_adapter=None, event_bus=None, db_manager=None,
                 workflow_engine=None, max_concurrency: int = 5, worker_id=None):
        self.broker = broker or get_message_broker()
        self.runtime_adapter = runtime_adapter
        self.event_bus = event_bus
        self.db_manager = db_manager
        self.workflow_engine = workflow_engine
        self.max_concurrency = max(1, int(max_concurrency))
        self.worker_id = worker_id or f"worker_{datetime.utcnow().strftime('%H%M%S')}"
        self._is_running = False
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._consumer_tasks = []
        self._executor = TaskPayloadExecutor(self)

    @property
    def is_running(self):
        return self._is_running

    @property
    def active_tasks_count(self):
        return len(self._active_tasks)

    async def start(self):
        if self._is_running:
            return
        await self.broker.connect()
        self._semaphore = asyncio.Semaphore(max(1, int(self.max_concurrency)))
        self._is_running = True
        consume = self._consume_fallback_queue if self.broker.is_fallback else self._setup_rabbitmq_consumer
        self._consumer_tasks = [asyncio.create_task(consume(name)) for name in QUEUES]
        logger.info("Queue worker %s started", self.worker_id)

    async def stop(self):
        self._is_running = False
        tasks, self._consumer_tasks = self._consumer_tasks, []
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._active_tasks.clear()

    def _identity(self, payload):
        return payload.get("task_id") or payload.get("run_id") or payload.get("execution_id") or "unknown"

    async def _execute_task_payload(self, payload):
        if not isinstance(payload, dict):
            return False
        identity = self._identity(payload)
        self._active_tasks[identity] = {
            "payload": payload, "started_at": datetime.utcnow().isoformat(),
            "worker_id": self.worker_id,
        }
        try:
            return await self._executor.execute(payload)
        except Exception as error:
            logger.warning("Queue delivery rejected (%s)", type(error).__name__)
            return False
        finally:
            self._active_tasks.pop(identity, None)

    def _dead_letter(self, payload, reason):
        self.broker.record_dead_letter(payload, reason)
        # Only failed dispatches still queued may become FAILED here. An already
        # accepted/running task remains owned by its runtime, including on restart.
        if not self.db_manager:
            return
        try:
            if payload.get("type") == "workflow_execution":
                execution = self.db_manager.get_workflow_execution(payload.get("execution_id"))
                if execution and status_value(execution) == "QUEUED":
                    self.db_manager.update_workflow_execution(
                        execution.id, status="FAILED", error_message=reason,
                        completed_at=datetime.utcnow().isoformat(),
                    )
            else:
                identity = self._identity(payload)
                run = self.db_manager.get_task_run(identity)
                if run and status_value(run) in {"QUEUED", "PENDING"}:
                    from runtime.models import TaskStatus
                    self.db_manager.update_task_run(
                        identity, status=TaskStatus.FAILED, error=reason, ended_at=datetime.now(),
                    )
        except Exception as error:
            logger.warning("Could not persist exhausted dispatch (%s)", type(error).__name__)

    async def _setup_rabbitmq_consumer(self, queue_name):
        try:
            if not self.broker._channel:
                raise RuntimeError("RabbitMQ channel unavailable")
            queue = await self.broker._channel.declare_queue(queue_name, passive=True)
            async with queue.iterator() as messages:
                async for message in messages:
                    if not self._is_running:
                        break
                    async with self._semaphore:
                        try:
                            payload = json.loads(message.body.decode("utf-8"))
                            if not isinstance(payload, dict):
                                raise ValueError("Queue payload must be an object")
                        except (ValueError, UnicodeError):
                            self._dead_letter({"type": "invalid_payload"}, "Invalid queue payload")
                            await message.nack(requeue=False)
                            continue
                        try:
                            accepted = await self._execute_task_payload(payload)
                            if accepted:
                                await message.ack()
                                continue
                            retries = int(payload.get("retry_count", 0)) + 1
                            if retries > MAX_RETRIES:
                                self._dead_letter(payload, "Dispatch failed after initial attempt and 3 retries")
                                await message.nack(requeue=False)
                                continue
                            payload = {**payload, "retry_count": retries}
                            await asyncio.sleep(min(2 ** (retries - 1), 4))
                            # NACK(requeue=True) reuses the original bytes and loses
                            # Python-side retry_count. Republish confirmed bytes first.
                            await self.broker.publish_payload(payload, queue_name, message.routing_key)
                            await message.ack()
                        except asyncio.CancelledError:
                            await message.nack(requeue=True)
                            raise
                        except Exception as error:
                            logger.warning("Queue retry publish unavailable (%s)", type(error).__name__)
                            # Keep the original delivery when republishing was not
                            # confirmed. Do not fabricate acknowledgement or success.
                            await message.nack(requeue=True)
                            await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception as error:
            self._is_running = False
            logger.warning("Queue consumer unavailable (%s)", type(error).__name__)

    async def _consume_fallback_queue(self, queue_name):
        queue = self.broker._fallback_queues.get(queue_name)
        if queue is None:
            self._is_running = False
            return
        while self._is_running:
            payload = None
            try:
                try:
                    _, _, payload = await asyncio.wait_for(queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    continue
                try:
                    async with self._semaphore:
                        accepted = await self._execute_task_payload(payload)
                        if not accepted:
                            retries = int(payload.get("retry_count", 0)) + 1
                            if retries > MAX_RETRIES:
                                self._dead_letter(payload, "Dispatch failed after initial attempt and 3 retries")
                            else:
                                await asyncio.sleep(min(2 ** (retries - 1), 4))
                                await self.broker.publish_payload(
                                    {**payload, "retry_count": retries}, queue_name, "",
                                )
                finally:
                    queue.task_done()
            except asyncio.CancelledError:
                if payload is not None:
                    await self.broker.publish_payload(payload, queue_name, "")
                break
            except Exception as error:
                logger.warning("Memory queue delivery failed (%s)", type(error).__name__)
                if isinstance(payload, dict):
                    self._dead_letter(payload, "Invalid memory queue delivery")


_worker_daemon: Optional[QueueWorkerDaemon] = None


def get_queue_worker():
    global _worker_daemon
    if _worker_daemon is None:
        _worker_daemon = QueueWorkerDaemon()
    return _worker_daemon
