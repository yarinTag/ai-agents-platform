"""
Task & Workflow Step Queue Publisher.

Dispatches agent tasks and workflow stages to RabbitMQ topic exchanges
with tenant scoping, department routing keys, and priority settings.
"""

import json
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .broker import (
    MessageBroker,
    get_message_broker,
    TASKS_EXCHANGE_NAME,
    QUEUE_HIGH_PRIORITY,
    QUEUE_STANDARD,
    QUEUE_BACKGROUND,
    QUEUE_WORKFLOW_STEPS,
    QUEUE_WORKFLOW_EXECUTION,
)

logger = logging.getLogger(__name__)


class TaskQueuePublisher:
    """Publishes task execution jobs to RabbitMQ / AMQP broker."""

    def __init__(self, broker: Optional[MessageBroker] = None):
        self.broker = broker or get_message_broker()

    async def publish_task(
        self,
        task_id: str,
        agent_id: str,
        project_id: str,
        prompt: str,
        org_id: Optional[str] = None,
        department_id: Optional[str] = None,
        priority: int = 5,
        routing_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Publishes an autonomous agent task into the message queue.
        Priority: 1 (lowest / background) to 10 (highest / critical incident).
        """
        await self.broker.connect()

        # Enforce priority bounds
        priority = max(1, min(10, priority))

        # AI Security Firewall pre-queue check
        from ..security.firewall import get_prompt_firewall
        firewall = get_prompt_firewall()
        firewall.assert_clean_prompt(text=prompt, source="queue_publisher", org_id=org_id)

        # Default routing key computation
        if not routing_key:
            if priority >= 8:
                routing_key = f"task.urgent.{department_id or 'default'}"
            elif priority <= 3:
                routing_key = f"task.background.{department_id or 'default'}"
            else:
                routing_key = f"task.dept.{department_id or 'default'}"

        correlation_id = str(uuid.uuid4())
        payload = {
            "type": "agent_task",
            "task_id": task_id,
            "agent_id": agent_id,
            "project_id": project_id,
            "prompt": prompt,
            "organization_id": org_id,
            "department_id": department_id,
            "priority": priority,
            "correlation_id": correlation_id,
            "published_at": datetime.utcnow().isoformat(),
            "retry_count": 0,
            "metadata": metadata or {},
        }

        queue_name = (
            QUEUE_HIGH_PRIORITY if priority >= 8 else
            QUEUE_BACKGROUND if priority <= 3 else QUEUE_STANDARD
        )
        await self.broker.publish_payload(payload, queue_name, routing_key)

        return {
            "task_id": task_id,
            "correlation_id": correlation_id,
            "routing_key": routing_key,
            "priority": priority,
            "status": "QUEUED",
        }

    async def publish_workflow_step(
        self,
        workflow_id: str,
        run_id: str,
        step_key: str,
        agent_id: str,
        prompt: str,
        department_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        priority: int = 5,
    ) -> Dict[str, Any]:
        """Publishes a DAG workflow step to the workflow step queue."""
        await self.broker.connect()
        correlation_id = str(uuid.uuid4())
        routing_key = f"workflow.step.{workflow_id}.{step_key}"

        # AI Security Firewall pre-queue check
        from ..security.firewall import get_prompt_firewall
        get_prompt_firewall().assert_clean_prompt(text=prompt, source=f"queue_workflow:{step_key}")

        payload = {
            "type": "workflow_step",
            "workflow_id": workflow_id,
            "run_id": run_id,
            "step_key": step_key,
            "agent_id": agent_id,
            "prompt": prompt,
            "department_id": department_id,
            "inputs": inputs or {},
            "priority": priority,
            "correlation_id": correlation_id,
            "published_at": datetime.utcnow().isoformat(),
            "retry_count": 0,
        }

        await self.broker.publish_payload(payload, QUEUE_WORKFLOW_STEPS, routing_key)

        return {
            "run_id": run_id,
            "step_key": step_key,
            "routing_key": routing_key,
            "status": "QUEUED",
        }

    async def publish_workflow_execution(
        self,
        workflow_id: str,
        execution_id: str,
        trigger_type: str = "MANUAL",
        trigger_payload: Optional[Dict[str, Any]] = None,
        department_id: Optional[str] = None,
        org_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        priority: int = 5,
    ) -> Dict[str, Any]:
        """Publishes an entire workflow DAG execution to the RabbitMQ workflow execution queue."""
        await self.broker.connect()
        correlation_id = str(uuid.uuid4())
        routing_key = f"workflow.execution.{workflow_id}"

        payload = {
            "type": "workflow_execution",
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "trigger_type": trigger_type,
            "trigger_payload": trigger_payload or {},
            "department_id": department_id,
            "organization_id": org_id,
            "user_context": user_context,
            "priority": priority,
            "correlation_id": correlation_id,
            "published_at": datetime.utcnow().isoformat(),
            "retry_count": 0,
        }

        await self.broker.publish_payload(payload, QUEUE_WORKFLOW_EXECUTION, routing_key)

        return {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "routing_key": routing_key,
            "status": "QUEUED",
        }
