"""Queue delivery acceptance; execution results remain owned by runtime engines."""

import asyncio
import logging

logger = logging.getLogger(__name__)


def status_value(record):
    status = getattr(record, "status", "")
    return str(getattr(status, "value", status)).upper()


class TaskPayloadExecutor:
    def __init__(self, worker):
        self.worker = worker

    async def execute(self, payload):
        kind = payload.get("type", "agent_task")
        if kind == "workflow_execution":
            return await self._workflow(payload)
        if kind not in {"agent_task", "workflow_step"}:
            logger.warning("Unsupported queue payload type")
            return False
        return await self._agent(payload)

    async def _workflow(self, payload):
        worker = self.worker
        engine = worker.workflow_engine
        if engine is None:
            logger.warning("Workflow queue delivery unavailable: no configured engine")
            return False
        workflow_id = payload.get("workflow_id")
        execution_id = payload.get("execution_id")
        if not workflow_id or not execution_id:
            return False
        if worker.db_manager:
            existing = worker.db_manager.get_workflow_execution(execution_id)
            if existing:
                if existing.workflow_id != workflow_id:
                    return False
                workflow = worker.db_manager.get_workflow(workflow_id)
                if not workflow or (payload.get("organization_id") and workflow.organization_id != payload["organization_id"]):
                    return False
                if status_value(existing) in {"COMPLETED", "FAILED", "CANCELLED"}:
                    return True
                if status_value(existing) != "QUEUED":
                    # A redelivery must not restart side effects already in progress.
                    logger.warning("Workflow delivery %s already has execution ownership", execution_id)
                    return True
        try:
            result = await asyncio.to_thread(
                engine.execute_workflow,
                workflow_id=workflow_id,
                trigger_type=payload.get("trigger_type", "MANUAL"),
                trigger_payload=payload.get("trigger_payload"),
                user_context=payload.get("user_context"),
                execution_id=execution_id,
            )
            # FAILED/paused executions are truthful engine outcomes, not transport
            # failures to replay automatically (which could repeat tool effects).
            return result is not None and bool(status_value(result))
        except Exception as error:
            logger.warning("Workflow dispatch failed (%s)", type(error).__name__)
            if worker.db_manager:
                from datetime import datetime
                record = worker.db_manager.get_workflow_execution(execution_id)
                if record:
                    if status_value(record) in {"QUEUED", "RUNNING"}:
                        worker.db_manager.update_workflow_execution(
                            execution_id, status="FAILED", error_message="Workflow execution unavailable",
                            completed_at=datetime.now().isoformat(),
                        )
                    # Never replay an execution once its engine has taken ownership.
                    return True
            return False

    async def _agent(self, payload):
        worker = self.worker
        runtime = worker.runtime_adapter
        task_id = payload.get("task_id") or payload.get("run_id")
        agent_id = payload.get("agent_id")
        if runtime is None or not task_id or not agent_id:
            logger.warning("Agent queue delivery unavailable: runtime or identity missing")
            return False
        try:
            current = runtime.get_run_status(task_id)
            if current is not None:
                return current.agent_id == agent_id
            if worker.db_manager:
                persisted = worker.db_manager.get_task_run(task_id)
                if persisted:
                    if persisted.agent_id != agent_id:
                        return False
                    if payload.get("organization_id") and persisted.organization_id != payload["organization_id"]:
                        return False
                    if status_value(persisted) in {"COMPLETED", "FAILED", "CANCELLED"}:
                        return True
                    if status_value(persisted) not in {"QUEUED", "PENDING"}:
                        logger.warning("Task delivery %s has existing execution ownership", task_id)
                        return True
            run_id = await asyncio.to_thread(
                runtime.start_task,
                agent_id=agent_id,
                project_id=payload.get("project_id"),
                prompt=payload.get("prompt"),
                task_id=task_id,
            )
            if run_id != task_id:
                logger.error("Runtime did not preserve queued task identity")
                return False
            # ACK means accepted by the runtime. Only that runtime may mark the
            # persisted task COMPLETED/FAILED after actual inference finishes.
            logger.info("Runtime accepted queued task %s", task_id)
            return True
        except Exception as error:
            logger.warning("Agent dispatch failed (%s)", type(error).__name__)
            return False
