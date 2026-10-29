"""
Queue Management & Monitoring REST API Router.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .broker import get_message_broker, MessageBroker
from .publisher import TaskQueuePublisher
from .worker import get_queue_worker, QueueWorkerDaemon
from ..security import authenticate_request

router = APIRouter(tags=["Queue & Message Broker"])


class EnqueueTestTaskRequest(BaseModel):
    agent_id: str = Field(..., description="ID of agent to execute task")
    prompt: str = Field(..., description="Task instructions")
    priority: int = Field(5, ge=1, le=10, description="Priority from 1 to 10")
    project_id: str = Field("default", description="Project ID")
    department_id: Optional[str] = Field(None, description="Department ID for routing")


class QueueStatusResponse(BaseModel):
    broker: str
    connected: bool
    queues: Dict[str, int]
    dead_letter_count: int
    worker_running: bool
    active_worker_tasks: int
    timestamp: str


@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status():
    """
    Returns live health, queue depths, DLQ metrics, and worker daemon status.
    """
    broker = get_message_broker()
    stats = await broker.get_queue_stats()
    worker = get_queue_worker()

    return QueueStatusResponse(
        broker=stats.get("broker", "unknown"),
        connected=stats.get("connected", False),
        queues=stats.get("queues", {}),
        dead_letter_count=stats.get("dead_letter_count", 0),
        worker_running=worker.is_running,
        active_worker_tasks=worker.active_tasks_count,
        timestamp=stats.get("timestamp", "")
    )


@router.get("/dlq", response_model=List[Dict[str, Any]])
async def get_dead_letter_queue():
    """
    Lists all dead-lettered messages that failed execution or exceeded max retries.
    """
    broker = get_message_broker()
    return broker.get_dead_letters()


@router.post("/retry/{message_id}")
async def retry_dead_letter(message_id: str):
    """
    Re-queues a failed message from the Dead Letter Queue for reprocessing.
    """
    broker = get_message_broker()
    dead_letters = broker.get_dead_letters()
    target = next((item for item in dead_letters if item.get("message_id") == message_id), None)

    if not target:
        raise HTTPException(status_code=404, detail=f"Dead-letter message '{message_id}' not found")

    payload = target.get("payload", {})
    payload["retry_count"] = 0  # Reset retry counter

    publisher = TaskQueuePublisher(broker)
    await publisher.publish_task(
        task_id=payload.get("task_id", message_id),
        agent_id=payload.get("agent_id", "unknown"),
        project_id=payload.get("project_id", "default"),
        prompt=payload.get("prompt", ""),
        org_id=payload.get("organization_id"),
        department_id=payload.get("department_id"),
        priority=payload.get("priority", 5)
    )

    # Remove from DLQ store
    broker._dead_letter_store = [item for item in broker._dead_letter_store if item.get("message_id") != message_id]

    return {"status": "SUCCESS", "message": f"Message '{message_id}' successfully re-queued"}


@router.post("/publish-test")
async def publish_test_task(req: EnqueueTestTaskRequest):
    """
    Dispatches a test task into the RabbitMQ / AMQP message queue.
    """
    publisher = TaskQueuePublisher()
    import uuid
    task_id = f"test_{uuid.uuid4().hex[:8]}"

    res = await publisher.publish_task(
        task_id=task_id,
        agent_id=req.agent_id,
        project_id=req.project_id,
        prompt=req.prompt,
        department_id=req.department_id,
        priority=req.priority
    )
    return res
