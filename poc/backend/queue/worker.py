"""
Distributed Queue Worker Daemon.

Consumes tasks from RabbitMQ (or fallback queues), handles manual ACKs/NACKs,
routes dead letters on repeated failure, and dispatches execution to runtime adapters.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime

from .broker import (
    MessageBroker,
    get_message_broker,
    QUEUE_HIGH_PRIORITY,
    QUEUE_STANDARD,
    QUEUE_BACKGROUND,
    QUEUE_WORKFLOW_STEPS,
    QUEUE_WORKFLOW_EXECUTION,
)

logger = logging.getLogger(__name__)


class QueueWorkerDaemon:
    """
    Background worker consumer executing queued tasks and workflows.
    """

    def __init__(
        self,
        broker: Optional[MessageBroker] = None,
        runtime_adapter: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        db_manager: Optional[Any] = None,
        workflow_engine: Optional[Any] = None,
        max_concurrency: int = 5,
        worker_id: Optional[str] = None,
    ):
        self.broker = broker or get_message_broker()
        self.runtime_adapter = runtime_adapter
        self.event_bus = event_bus
        self.db_manager = db_manager
        self.workflow_engine = workflow_engine
        self.max_concurrency = max_concurrency
        self.worker_id = worker_id or f"worker_{datetime.utcnow().strftime('%H%M%S')}"
        self._is_running = False
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._consumer_tasks = []

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def active_tasks_count(self) -> int:
        return len(self._active_tasks)

    async def start(self):
        """Start consuming from queues."""
        if self._is_running:
            return

        self._is_running = True
        await self.broker.connect()
        logger.info(f"Queue Worker Daemon [{self.worker_id}] started with concurrency={self.max_concurrency}")

        if self.broker.is_fallback:
            # Start in-memory polling tasks
            for q_name in [QUEUE_HIGH_PRIORITY, QUEUE_STANDARD, QUEUE_BACKGROUND, QUEUE_WORKFLOW_STEPS, QUEUE_WORKFLOW_EXECUTION]:
                t = asyncio.create_task(self._consume_fallback_queue(q_name))
                self._consumer_tasks.append(t)
        else:
            # Setup aio-pika queue consumers
            for q_name in [QUEUE_HIGH_PRIORITY, QUEUE_STANDARD, QUEUE_BACKGROUND, QUEUE_WORKFLOW_STEPS, QUEUE_WORKFLOW_EXECUTION]:
                t = asyncio.create_task(self._setup_rabbitmq_consumer(q_name))
                self._consumer_tasks.append(t)

    async def stop(self):
        """Stop worker daemon cleanly."""
        self._is_running = False
        for t in self._consumer_tasks:
            t.cancel()
        self._consumer_tasks.clear()
        logger.info(f"Queue Worker Daemon [{self.worker_id}] stopped cleanly.")

    async def _setup_rabbitmq_consumer(self, queue_name: str):
        """Subscribe to a RabbitMQ queue with manual acknowledgment."""
        try:
            if not self.broker._channel:
                return

            queue = await self.broker._channel.declare_queue(queue_name, passive=True)
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self._is_running:
                        break

                    async with self._semaphore:
                        try:
                            payload = json.loads(message.body.decode("utf-8"))
                            task_id = payload.get("task_id") or payload.get("run_id", "unknown")
                            self._active_tasks[task_id] = {
                                "payload": payload,
                                "started_at": datetime.utcnow().isoformat(),
                                "worker_id": self.worker_id,
                            }

                            success = await self._execute_task_payload(payload)

                            if success:
                                await message.ack()
                                logger.info(f"[RabbitMQ] Successfully processed and ACKed task {task_id}")
                            else:
                                retry_count = payload.get("retry_count", 0) + 1
                                if retry_count <= 3:
                                    payload["retry_count"] = retry_count
                                    logger.warning(f"Task {task_id} failed (attempt {retry_count}/3). Re-queueing.")
                                    await message.nack(requeue=True)
                                else:
                                    logger.error(f"Task {task_id} failed 3 times. Routing to Dead-Letter Queue.")
                                    self.broker.record_dead_letter(payload, reason="Exceeded maximum retries (3)")
                                    await message.nack(requeue=False)

                            self._active_tasks.pop(task_id, None)

                        except Exception as e:
                            logger.error(f"Unhandled error processing message from {queue_name}: {e}")
                            await message.nack(requeue=False)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"RabbitMQ consumer loop error on {queue_name}: {e}")

    async def _consume_fallback_queue(self, queue_name: str):
        """Consumes messages from in-memory fallback priority queue."""
        q = self.broker._fallback_queues.get(queue_name)
        if not q:
            return

        while self._is_running:
            try:
                # Wait for next item with timeout to check is_running
                try:
                    priority_val, ts, payload = await asyncio.wait_for(q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                async with self._semaphore:
                    task_id = payload.get("task_id") or payload.get("run_id", "unknown")
                    self._active_tasks[task_id] = {
                        "payload": payload,
                        "started_at": datetime.utcnow().isoformat(),
                        "worker_id": self.worker_id,
                    }

                    success = await self._execute_task_payload(payload)

                    if not success:
                        retry_count = payload.get("retry_count", 0) + 1
                        if retry_count <= 3:
                            payload["retry_count"] = retry_count
                            logger.warning(f"[Fallback Queue] Retrying task {task_id} (attempt {retry_count}/3)")
                            await q.put((priority_val, ts, payload))
                        else:
                            logger.error(f"[Fallback Queue] Task {task_id} dead-lettered after 3 attempts.")
                            self.broker.record_dead_letter(payload, reason="Exceeded maximum retries in fallback queue")

                    self._active_tasks.pop(task_id, None)
                    q.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in fallback queue consumer {queue_name}: {e}")
                await asyncio.sleep(0.5)

    async def _execute_task_payload(self, payload: Dict[str, Any]) -> bool:
        """Executes the task using the platform runtime adapter or workflow engine."""
        task_id = payload.get("task_id") or payload.get("run_id")
        agent_id = payload.get("agent_id")
        prompt = payload.get("prompt")
        project_id = payload.get("project_id", "default")
        payload_type = payload.get("type", "agent_task")

        logger.info(f"Worker [{self.worker_id}] claimed {payload_type} {task_id} for agent {agent_id}...")

        # Update Database status to RUNNING
        if self.db_manager and task_id:
            try:
                self.db_manager.update_task_run(
                    run_id=task_id,
                    status="RUNNING",
                    started_at=datetime.utcnow().isoformat()
                )
            except Exception as db_err:
                logger.debug(f"Could not update task run status to RUNNING: {db_err}")

        # Broadcast event if event_bus is present
        if self.event_bus:
            try:
                from events import PlatformEvent, EventType
                self.event_bus.publish(PlatformEvent(
                    event_id=f"evt_worker_{datetime.utcnow().timestamp()}",
                    event_type=EventType.TASK_STARTED.value,
                    agent_id=agent_id,
                    task_id=task_id,
                    project_id=project_id,
                    message=f"Task claimed by worker {self.worker_id}",
                    data={"worker_id": self.worker_id, "priority": payload.get("priority", 5)}
                ))
            except Exception as e:
                logger.debug(f"Event emission failed: {e}")

        # Branch 1: Workflow Execution
        if payload_type == "workflow_execution":
            workflow_id = payload.get("workflow_id")
            execution_id = payload.get("execution_id")
            trigger_type = payload.get("trigger_type", "QUEUED")
            trigger_payload = payload.get("trigger_payload")
            user_context = payload.get("user_context")
            logger.info(f"Worker [{self.worker_id}] processing workflow execution '{execution_id}' for workflow '{workflow_id}'")

            wf_engine = getattr(self, "workflow_engine", None)
            if not wf_engine:
                try:
                    from workflows.engine import WorkflowEngine
                    from workflows.sandbox import SandboxManager
                    wf_engine = WorkflowEngine(
                        db_manager=self.db_manager,
                        runtime_adapter=self.runtime_adapter,
                        sandbox_manager=SandboxManager()
                    )
                except Exception as ex:
                    logger.error(f"Could not initialize WorkflowEngine in worker: {ex}")
                    return False

            try:
                # Update status to RUNNING if it was QUEUED
                if self.db_manager and execution_id:
                    try:
                        self.db_manager.update_workflow_execution(
                            execution_id=execution_id,
                            status="RUNNING",
                            started_at=datetime.utcnow().isoformat()
                        )
                    except Exception as db_err:
                        logger.debug(f"Could not update workflow execution status to RUNNING: {db_err}")

                exec_result = wf_engine.execute_workflow(
                    workflow_id=workflow_id,
                    trigger_type=trigger_type,
                    trigger_payload=trigger_payload,
                    user_context=user_context,
                    execution_id=execution_id
                )
                success = exec_result and exec_result.status == "COMPLETED"
                logger.info(f"Workflow execution {execution_id} completed with status: {getattr(exec_result, 'status', 'UNKNOWN')}")
                return success
            except Exception as wf_err:
                logger.error(f"Workflow execution {execution_id} failed: {wf_err}", exc_info=True)
                if self.db_manager and execution_id:
                    try:
                        self.db_manager.update_workflow_execution(
                            execution_id=execution_id,
                            status="FAILED",
                            error_message=str(wf_err),
                            completed_at=datetime.utcnow().isoformat()
                        )
                    except Exception:
                        pass
                return False

        # Branch 2: Workflow Step Execution
        if payload_type == "workflow_step":
            workflow_id = payload.get("workflow_id")
            step_key = payload.get("step_key")
            logger.info(f"Worker [{self.worker_id}] processing workflow step '{step_key}' for workflow '{workflow_id}'")
            if self.runtime_adapter and hasattr(self.runtime_adapter, "start_task"):
                try:
                    run_id = self.runtime_adapter.start_task(
                        agent_id=agent_id,
                        project_id=project_id,
                        prompt=prompt
                    )
                    logger.info(f"Workflow step {step_key} dispatched with run_id {run_id}")
                    return True
                except Exception as ex:
                    logger.error(f"Workflow step execution failure: {ex}")
                    return False
            await asyncio.sleep(0.1)
            return True

        # Branch 2: Standard Agent Task Execution
        if self.runtime_adapter:
            try:
                if hasattr(self.runtime_adapter, "start_task"):
                    run_id = self.runtime_adapter.start_task(
                        agent_id=agent_id,
                        project_id=project_id,
                        prompt=prompt
                    )
                    logger.info(f"Task {task_id} successfully dispatched to runtime adapter with run_id {run_id}")
                    if self.db_manager and task_id:
                        try:
                            self.db_manager.update_task_run(
                                run_id=task_id,
                                status="COMPLETED",
                                ended_at=datetime.utcnow().isoformat()
                            )
                        except Exception:
                            pass
                    return True
            except Exception as e:
                logger.error(f"Runtime execution failure for task {task_id}: {e}")
                if self.db_manager and task_id:
                    try:
                        self.db_manager.update_task_run(
                            run_id=task_id,
                            status="FAILED",
                            error=str(e),
                            ended_at=datetime.utcnow().isoformat()
                        )
                    except Exception:
                        pass
                return False

        # In absence of direct adapter, simulate or mark done
        await asyncio.sleep(0.1)
        if self.db_manager and task_id:
            try:
                self.db_manager.update_task_run(
                    run_id=task_id,
                    status="COMPLETED",
                    ended_at=datetime.utcnow().isoformat()
                )
            except Exception:
                pass
        return True


# Global worker instance
_worker_daemon: Optional[QueueWorkerDaemon] = None


def get_queue_worker() -> QueueWorkerDaemon:
    global _worker_daemon
    if _worker_daemon is None:
        _worker_daemon = QueueWorkerDaemon()
    return _worker_daemon
