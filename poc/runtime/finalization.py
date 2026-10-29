"""Persist final run/chat state and release resources after execution."""

import logging
import threading
from datetime import datetime

from .models import AgentRun, TaskStatus
from .processes import terminate_process

logger = logging.getLogger(__name__)


def record_response(adapter, run: AgentRun):
    database = adapter.services.database()
    database.save_task_run(run)
    if run.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.WAITING_INPUT):
        return
    if not run.agent_id:
        return
    try:
        conversation = database.get_or_create_conversation(run.agent_id, project_id=run.project_id)
        status = run.status.value if hasattr(run.status, "value") else str(run.status)
        content = (
            run.result if status in ("completed", "waiting_input") and run.result
            else run.error or "Task completed."
        )
        if database.has_chat_message_for_task(run.agent_id, run.run_id, "ASSISTANT", content=content):
            return
        message = database.save_chat_message({
            "conversation_id": conversation["id"],
            "agent_id": run.agent_id,
            "task_id": run.run_id,
            "sender_type": "ASSISTANT",
            "message_type": "CHAT",
            "content": content,
            "metadata": {
                "task_id": run.run_id,
                "status": status,
                "prompt": run.prompt,
                "exit_code": run.exit_code,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            },
        })
        try:
            if adapter.services.publish_chat:
                adapter.services.publish_chat(run, message)
        except Exception:
            logger.debug("Chat event publication unavailable", exc_info=True)
    except Exception as error:
        logger.warning("Failed to record task response to chat: %s", error)


def finalize_run(adapter, run: AgentRun):
    run_id = run.run_id
    terminal = (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
    run.ended_at = datetime.now() if run.status in terminal else None
    try:
        record_response(adapter, run)
    except Exception as error:
        logger.warning("Failed to save task run to DB: %s", error)

    if run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        completion = adapter.on_task_completed or adapter.services.complete
        if completion:
            try:
                completion(run)
            except Exception as error:
                logger.error("Completion callback failed for %s: %s", run_id, error)

    if run_id in adapter._stop_events:
        adapter._stop_events[run_id].set()
    try:
        process = adapter._processes.get(run_id)
        if process:
            terminate_process(process)
    finally:
        if run.status in terminal:
            adapter._subscriptions.close_run(run_id)
        adapter._execution_threads.pop(threading.current_thread(), None)
        stderr_thread = adapter._stderr_threads.pop(run_id, None)
        if stderr_thread is not None and stderr_thread.is_alive():
            stderr_thread.join(timeout=1)
        adapter._processes.pop(run_id, None)
        adapter._event_queues.pop(run_id, None)
        adapter._reader_threads.pop(run_id, None)
        adapter._stop_events.pop(run_id, None)
