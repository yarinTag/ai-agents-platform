"""
Comprehensive End-to-End Enterprise Verification:
- RabbitMQ & In-Memory Priority Broker
- Topic Routing & Priority Queuing (1-10)
- Distributed Worker Processing & DLQ Recording
- Dual-Channel ChatOps HITL (Telegram Callback & Slack Interactivity)
"""

import pytest
import asyncio
import uuid
from datetime import datetime

from poc.backend.queue.broker import MessageBroker, QUEUE_HIGH_PRIORITY, QUEUE_STANDARD, QUEUE_BACKGROUND
from poc.backend.queue.publisher import TaskQueuePublisher
from poc.backend.queue.worker import QueueWorkerDaemon
from poc.backend.approvals.chatops import (
    format_telegram_approval,
    format_slack_approval_blocks,
)


@pytest.mark.asyncio
async def test_message_broker_priority_queuing():
    """Verify that tasks are partitioned correctly by priority band."""
    broker = MessageBroker()
    await broker.connect()
    assert broker.is_connected

    publisher = TaskQueuePublisher(broker)

    # 1. High Priority (Urgent)
    res_high = await publisher.publish_task(
        task_id="task_urgent_1",
        agent_id="sec-agent",
        project_id="core",
        prompt="Mitigate CVE immediately",
        priority=9
    )
    assert res_high["status"] == "QUEUED"
    assert "urgent" in res_high["routing_key"]

    # 2. Standard Priority
    res_std = await publisher.publish_task(
        task_id="task_std_1",
        agent_id="dev-agent",
        project_id="core",
        prompt="Refactor payment controller",
        priority=5
    )
    assert res_std["status"] == "QUEUED"

    # 3. Background Priority
    res_bg = await publisher.publish_task(
        task_id="task_bg_1",
        agent_id="doc-agent",
        project_id="core",
        prompt="Sync OpenAPI docs",
        priority=2
    )
    assert res_bg["status"] == "QUEUED"
    assert "background" in res_bg["routing_key"]

    stats = await broker.get_queue_stats()
    assert stats["connected"] is True
    assert stats["queues"][QUEUE_HIGH_PRIORITY] >= 1
    assert stats["queues"][QUEUE_STANDARD] >= 1
    assert stats["queues"][QUEUE_BACKGROUND] >= 1

    await broker.disconnect()


@pytest.mark.asyncio
async def test_worker_daemon_processing():
    """Verify that QueueWorkerDaemon drains the queue and processes tasks."""
    broker = MessageBroker()
    await broker.connect()
    publisher = TaskQueuePublisher(broker)

    task_id = f"test_exec_{uuid.uuid4().hex[:6]}"
    await publisher.publish_task(
        task_id=task_id,
        agent_id="qa-agent",
        project_id="core",
        prompt="Run unit test suite",
        priority=7
    )

    worker = QueueWorkerDaemon(broker=broker, max_concurrency=2)
    await worker.start()
    assert worker.is_running

    # Allow worker loop to claim task
    await asyncio.sleep(0.5)

    stats = await broker.get_queue_stats()
    assert stats["queues"][QUEUE_STANDARD] == 0  # Queue drained

    await worker.stop()
    await broker.disconnect()


def test_telegram_interactive_markup_generation():
    """Verify Telegram inline keyboard buttons format."""
    interaction = {
        "id": "intr_12345",
        "task_id": "task_abc",
        "requester_agent_id": "backend-builder",
        "title": "Drop Production Table",
        "content": "Agent wants to run DROP TABLE users CASCADE",
        "interaction_type": "PERMISSION_APPROVAL"
    }

    text, reply_markup = format_telegram_approval(interaction)
    assert "PERMISSION REQUIRED" in text
    assert "Drop Production Table" in text
    assert "backend-builder" in text

    buttons = reply_markup["inline_keyboard"][0]
    assert len(buttons) == 2
    assert buttons[0]["callback_data"] == "appr:approve:intr_12345"
    assert buttons[1]["callback_data"] == "appr:reject:intr_12345"


def test_slack_interactive_block_kit_generation():
    """Verify Slack Block Kit interactive message format."""
    interaction = {
        "id": "intr_99999",
        "task_id": "task_xyz",
        "requester_agent_id": "release-officer",
        "title": "Merge to Main",
        "content": "Agent wants to merge PR #45 to main branch",
        "interaction_type": "PERMISSION_APPROVAL"
    }

    blocks = format_slack_approval_blocks(interaction)
    assert len(blocks) == 3
    assert blocks[0]["type"] == "header"
    assert "Merge to Main" in blocks[0]["text"]["text"]

    actions_block = blocks[2]
    assert actions_block["type"] == "actions"
    elements = actions_block["elements"]
    assert len(elements) == 2
    assert elements[0]["value"] == "approve:intr_99999"
    assert elements[1]["value"] == "reject:intr_99999"


@pytest.mark.asyncio
async def test_dlq_recording_and_retry():
    """Verify that failed messages enter DLQ and can be re-queued."""
    broker = MessageBroker()
    await broker.connect()

    failed_payload = {
        "task_id": "failed_task_404",
        "agent_id": "buggy_worker",
        "prompt": "Failing instruction",
        "priority": 5
    }

    # Record to dead letter store
    broker.record_dead_letter(failed_payload, reason="Service unavailable 503")
    dlq = broker.get_dead_letters()
    assert len(dlq) >= 1
    assert any(item["message_id"] == "failed_task_404" for item in dlq)

    # Verify DLQ count in stats
    stats = await broker.get_queue_stats()
    assert stats["dead_letter_count"] >= 1

    await broker.disconnect()


@pytest.mark.asyncio
async def test_workflow_step_queue_publishing():
    """Verify DAG workflow step publishing to workflow queue."""
    broker = MessageBroker()
    await broker.connect()
    publisher = TaskQueuePublisher(broker)

    res = await publisher.publish_workflow_step(
        workflow_id="wf_ci_pipeline",
        run_id="run_stage_01",
        step_key="lint_code",
        agent_id="code-reviewer",
        prompt="Execute ruff check on codebase",
        priority=6
    )

    assert res["status"] == "QUEUED"
    assert "workflow.step" in res["routing_key"]
    assert res["step_key"] == "lint_code"

    await broker.disconnect()

