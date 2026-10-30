"""
RabbitMQ / AMQP Message Broker & Connection Manager for AI Agents Platform.

Features:
- Robust aio-pika async AMQP client connection with automatic reconnection.
- Explicit PLATFORM_QUEUE_MODE=memory for non-durable local queues.
- RabbitMQ outages raise a queue-unavailable error, without implicit fallback.
- Quorum / durable queues and topic exchange declarations.
- Dead Letter Exchange (DLX) and Dead Letter Queue (DLQ) binding.
- Multi-tenant department routing and message priorities (1 to 10).
"""

import os
import json
import asyncio
import logging
import copy
import itertools
from typing import Dict, Any, Optional, Callable, Awaitable, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Constants for Exchanges and Queues
TASKS_EXCHANGE_NAME = "platform.tasks.exchange"
DLX_EXCHANGE_NAME = "platform.tasks.dlx"
DLQ_QUEUE_NAME = "platform.tasks.dlq"

QUEUE_HIGH_PRIORITY = "platform.tasks.high_priority"
QUEUE_STANDARD = "platform.tasks.standard"
QUEUE_BACKGROUND = "platform.tasks.background"
QUEUE_WORKFLOW_STEPS = "platform.workflows.step"
QUEUE_WORKFLOW_EXECUTION = "platform.workflows.execution"


class QueueUnavailableError(RuntimeError):
    """The selected queue transport cannot accept work."""


class MessageBroker:
    """
    Unified AMQP broker interface supporting RabbitMQ via aio-pika
    with explicitly configured non-durable memory mode.
    """

    def __init__(self, amqp_url: Optional[str] = None):
        self.amqp_url = amqp_url or os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self._connection = None
        self._channel = None
        self._exchange = None
        self._dlx_exchange = None
        self._is_connected = False
        self._using_fallback = False
        self._fallback_queues: Dict[str, asyncio.PriorityQueue] = {}
        self._dead_letter_store: List[Dict[str, Any]] = []
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        self._lock = asyncio.Lock()
        self._sequence = itertools.count()

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_fallback(self) -> bool:
        return self._using_fallback

    async def connect(self) -> bool:
        """
        Connect the explicitly selected transport or raise QueueUnavailableError.
        """
        async with self._lock:
            if self._is_connected:
                return True

            mode = os.getenv("PLATFORM_QUEUE_MODE", "rabbitmq").strip().lower()
            if mode == "memory":
                self._setup_fallback_queues()
                self._using_fallback = True
                self._is_connected = True
                logger.warning("Explicit non-durable in-memory queue mode enabled")
                return True
            if mode != "rabbitmq":
                raise QueueUnavailableError("Unsupported queue transport mode")
            try:
                import aio_pika
                logger.info("Connecting to RabbitMQ broker")
                self._connection = await asyncio.wait_for(
                    aio_pika.connect_robust(self.amqp_url),
                    timeout=3.0
                )
                self._channel = await self._connection.channel(publisher_confirms=True, on_return_raises=True)
                await self._channel.set_qos(prefetch_count=10)

                # Declare Exchanges
                self._exchange = await self._channel.declare_exchange(
                    TASKS_EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )
                self._dlx_exchange = await self._channel.declare_exchange(
                    DLX_EXCHANGE_NAME,
                    aio_pika.ExchangeType.DIRECT,
                    durable=True
                )

                # Declare DLQ
                dlq = await self._channel.declare_queue(DLQ_QUEUE_NAME, durable=True)
                await dlq.bind(self._dlx_exchange, routing_key="dead_letter")

                # Declare Standard Queues with DLX binding
                arguments = {
                    "x-dead-letter-exchange": DLX_EXCHANGE_NAME,
                    "x-dead-letter-routing-key": "dead_letter",
                    "x-max-priority": 10
                }

                # High Priority Queue (Priority >= 8)
                q_high = await self._channel.declare_queue(QUEUE_HIGH_PRIORITY, durable=True, arguments=arguments)
                await q_high.bind(self._exchange, routing_key="task.urgent.#")
                await q_high.bind(self._exchange, routing_key="task.security.#")

                # Standard Queue (Priority 4-7)
                q_std = await self._channel.declare_queue(QUEUE_STANDARD, durable=True, arguments=arguments)
                await q_std.bind(self._exchange, routing_key="task.standard.#")
                await q_std.bind(self._exchange, routing_key="task.dept.*")

                # Background Queue (Priority 1-3)
                q_bg = await self._channel.declare_queue(QUEUE_BACKGROUND, durable=True, arguments=arguments)
                await q_bg.bind(self._exchange, routing_key="task.background.#")
                await q_bg.bind(self._exchange, routing_key="task.cron.#")

                # Workflow Steps Queue
                q_wf = await self._channel.declare_queue(QUEUE_WORKFLOW_STEPS, durable=True, arguments=arguments)
                await q_wf.bind(self._exchange, routing_key="workflow.step.#")

                # Workflow Execution Queue
                q_wf_exec = await self._channel.declare_queue(QUEUE_WORKFLOW_EXECUTION, durable=True, arguments=arguments)
                await q_wf_exec.bind(self._exchange, routing_key="workflow.execution.#")

                self._is_connected = True
                self._using_fallback = False
                logger.info("Successfully connected to RabbitMQ broker and configured durable priority queues.")
                return True

            except Exception as error:
                if self._connection:
                    try:
                        await self._connection.close()
                    except Exception:
                        pass
                self._connection = self._channel = self._exchange = None
                self._is_connected = False
                self._using_fallback = False
                logger.warning("RabbitMQ unavailable (%s)", type(error).__name__)
                raise QueueUnavailableError("RabbitMQ is unavailable") from error

    def _setup_fallback_queues(self):
        """Initialize in-memory priority queues for fallback mode."""
        for q_name in [QUEUE_HIGH_PRIORITY, QUEUE_STANDARD, QUEUE_BACKGROUND, QUEUE_WORKFLOW_STEPS, QUEUE_WORKFLOW_EXECUTION, DLQ_QUEUE_NAME]:
            if q_name not in self._fallback_queues:
                self._fallback_queues[q_name] = asyncio.PriorityQueue()

    async def disconnect(self):
        """Close connection cleanly."""
        async with self._lock:
            if self._connection and not self._using_fallback:
                try:
                    await self._connection.close()
                except Exception as e:
                    logger.debug(f"Error closing RabbitMQ connection: {e}")
            self._is_connected = False
            self._using_fallback = False
            self._connection = None
            self._channel = None
            self._exchange = None

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Return metrics on queue depths and broker health."""
        if self._using_fallback:
            return {
                "broker": "in_memory_fallback",
                "connected": True,
                "queues": {
                    name: q.qsize() for name, q in self._fallback_queues.items()
                },
                "dead_letter_count": len(self._dead_letter_store),
                "timestamp": datetime.utcnow().isoformat()
            }

        stats = {
            "broker": "rabbitmq",
            "connected": self._is_connected,
            "url": self.amqp_url.split("@")[-1] if "@" in self.amqp_url else self.amqp_url,
            "queues": {},
            "dead_letter_count": len(self._dead_letter_store),
            "timestamp": datetime.utcnow().isoformat()
        }

        if self._channel:
            try:
                for q_name in [QUEUE_HIGH_PRIORITY, QUEUE_STANDARD, QUEUE_BACKGROUND, QUEUE_WORKFLOW_STEPS, QUEUE_WORKFLOW_EXECUTION, DLQ_QUEUE_NAME]:
                    q = await self._channel.declare_queue(q_name, passive=True)
                    stats["queues"][q_name] = q.declaration_result.message_count
            except Exception as error:
                stats["connected"] = False
                logger.debug("Queue metrics unavailable (%s)", type(error).__name__)

        return stats

    async def publish_payload(self, payload, queue_name, routing_key):
        """Confirm acceptance or raise; a missing destination is never QUEUED."""
        await self.connect()
        priority = max(1, min(10, int(payload.get("priority", 5))))
        if self.is_fallback:
            destination = self._fallback_queues.get(queue_name)
            if destination is None:
                raise QueueUnavailableError("Queue destination is unavailable")
            await destination.put((10 - priority, next(self._sequence), copy.deepcopy(payload)))
            return
        if not self._exchange:
            raise QueueUnavailableError("Queue exchange is unavailable")
        import aio_pika
        message = aio_pika.Message(
            body=json.dumps(payload).encode("utf-8"),
            priority=priority,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=payload.get("correlation_id"),
            headers={
                "organization_id": payload.get("organization_id") or "",
                "department_id": payload.get("department_id") or "",
                "task_id": payload.get("task_id") or payload.get("run_id") or "",
                "agent_id": payload.get("agent_id") or "",
                "workflow_id": payload.get("workflow_id") or "",
                "execution_id": payload.get("execution_id") or "",
                "retry_count": payload.get("retry_count", 0),
            },
            content_type="application/json",
        )
        confirmation = await self._exchange.publish(message, routing_key=routing_key, mandatory=True)
        if confirmation is False:
            raise QueueUnavailableError("Queue publish was rejected")

    def get_dead_letters(self) -> List[Dict[str, Any]]:
        """Return list of dead-lettered payloads."""
        return copy.deepcopy(self._dead_letter_store)

    def record_dead_letter(self, payload: Dict[str, Any], reason: str):
        """Store failed message in dead-letter store."""
        record = {
            "message_id": payload.get("task_id") or payload.get("run_id") or payload.get("execution_id") or f"dlq_{len(self._dead_letter_store)+1}",
            "payload": copy.deepcopy(payload),
            "reason": reason,
            "dead_lettered_at": datetime.utcnow().isoformat()
        }
        self._dead_letter_store.append(record)
        # Cap dead letter store in memory
        if len(self._dead_letter_store) > 500:
            self._dead_letter_store.pop(0)


# Global singleton instance
_broker_instance: Optional[MessageBroker] = None


def get_message_broker() -> MessageBroker:
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = MessageBroker()
    return _broker_instance
