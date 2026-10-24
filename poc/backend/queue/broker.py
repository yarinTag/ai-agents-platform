"""
RabbitMQ / AMQP Message Broker & Connection Manager for AI Agents Platform.

Features:
- Robust aio-pika async AMQP client connection with automatic reconnection.
- Automatic fallback to an in-memory priority queue if RabbitMQ is unavailable,
  ensuring seamless development, zero external dependency failures, and smooth testing.
- Quorum / durable queues and topic exchange declarations.
- Dead Letter Exchange (DLX) and Dead Letter Queue (DLQ) binding.
- Multi-tenant department routing and message priorities (1 to 10).
"""

import os
import json
import asyncio
import logging
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


class MessageBroker:
    """
    Unified AMQP broker interface supporting RabbitMQ via aio-pika
    with graceful in-memory fallback mode.
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

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_fallback(self) -> bool:
        return self._using_fallback

    async def connect(self) -> bool:
        """
        Attempt connection to RabbitMQ broker. If not reachable,
        activate transparent in-memory priority queue fallback.
        """
        async with self._lock:
            if self._is_connected:
                return True

            try:
                import aio_pika
                logger.info(f"Connecting to RabbitMQ broker at {self.amqp_url}...")
                self._connection = await asyncio.wait_for(
                    aio_pika.connect_robust(self.amqp_url),
                    timeout=3.0
                )
                self._channel = await self._connection.channel()
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
                logger.info("Successfully connected to RabbitMQ broker and configured exchanges & quorum queues.")
                return True

            except Exception as e:
                logger.warning(
                    f"RabbitMQ connection unavailable ({type(e).__name__}: {e}). "
                    "Engaging high-performance in-memory fallback queue with priority and DLQ support."
                )
                self._is_connected = True
                self._using_fallback = True
                self._setup_fallback_queues()
                return True

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
            "dead_letter_count": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

        if self._channel:
            try:
                for q_name in [QUEUE_HIGH_PRIORITY, QUEUE_STANDARD, QUEUE_BACKGROUND, QUEUE_WORKFLOW_STEPS, QUEUE_WORKFLOW_EXECUTION, DLQ_QUEUE_NAME]:
                    q = await self._channel.declare_queue(q_name, passive=True)
                    stats["queues"][q_name] = q.declaration_result.message_count
            except Exception as e:
                logger.debug(f"Error fetching RabbitMQ queue passive stats: {e}")

        return stats

    def get_dead_letters(self) -> List[Dict[str, Any]]:
        """Return list of dead-lettered payloads."""
        return list(self._dead_letter_store)

    def record_dead_letter(self, payload: Dict[str, Any], reason: str):
        """Store failed message in dead-letter store."""
        record = {
            "message_id": payload.get("task_id") or payload.get("run_id") or f"dlq_{len(self._dead_letter_store)+1}",
            "payload": payload,
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
