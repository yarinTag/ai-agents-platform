"""
Autonomous Cron & Scheduled Task Engine.
Operates within the FastAPI lifespan to trigger scheduled workflows for AI agents.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from .dispatch import dispatch_scheduled_job
from .expressions import calculate_next_run, get_upcoming_runs, validate_cron_expression

from persistence import DatabaseManager
from runtime.protocol import RuntimeAdapter
from runtime.models import TaskStatus
from events import EventBus, PlatformEvent, EventType

logger = logging.getLogger(__name__)








class CronSchedulerEngine:
    """
    Background scheduler engine that executes scheduled tasks according to cron expressions.
    Maintains SQLite as the single source of truth.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        runtime_adapter: RuntimeAdapter,
        event_bus: Optional[EventBus] = None,
        poll_interval_seconds: float = 5.0
    ):
        self.db = db_manager
        self.runtime = runtime_adapter
        self.event_bus = event_bus
        self.poll_interval = poll_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Start the background scheduler task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("CronSchedulerEngine started successfully.")

    async def stop(self):
        """Stop the scheduler and wait for current iteration to conclude."""
        if not self._running:
            return
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("CronSchedulerEngine stopped.")

    async def _run_loop(self):
        """Main periodic polling loop."""
        logger.info("Cron loop initialized.")
        while self._running:
            try:
                await self._check_and_dispatch_due_jobs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in CronSchedulerEngine loop: {e}", exc_info=True)

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    async def _check_and_dispatch_due_jobs(self):
        """Check the database for any jobs whose next_run_at is now or in the past."""
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        due_jobs = self.db.get_due_cron_jobs(now_iso)
        if not due_jobs:
            return

        for job in due_jobs:
            try:
                await self._dispatch_job(job, now_dt)
            except Exception as e:
                logger.error(f"Failed to dispatch cron job '{job.get('id')}': {e}", exc_info=True)

    async def _dispatch_job(self, job: Dict[str, Any], trigger_time: datetime):
        """Execute a single due cron job according to its concurrency and dispatch policies."""
        job_id = job['id']
        agent_id = job['agent_id']
        prompt = job['prompt']
        project_id = job.get('project_id')
        policy = job.get('concurrency_policy', 'SKIP').upper()

        # Check if agent is currently busy
        active_runs = self.runtime.list_runs()
        agent_busy = any(
            r.agent_id == agent_id and r.status in [TaskStatus.RUNNING, TaskStatus.PENDING, TaskStatus.WAITING_INPUT, TaskStatus.PENDING_APPROVAL]
            for r in active_runs
        )

        if agent_busy and policy == 'SKIP':
            logger.warning(f"Cron job {job_id} for agent {agent_id} skipped due to active task (policy: SKIP).")
            # Calculate next run time
            next_run = calculate_next_run(job['cron_expression'], trigger_time)
            self.db.update_cron_job(job_id, {
                'last_status': 'SKIPPED',
                'last_run_at': trigger_time.isoformat(),
                'next_run_at': next_run
            })
            if self.event_bus:
                self.event_bus.publish(PlatformEvent(
                    event_id=f"evt_{datetime.now().timestamp()}",
                    sequence_number=0,
                    event_type=EventType.TASK_FAILED if hasattr(EventType, 'TASK_FAILED') else 'task.skipped',
                    agent_id=agent_id,
                    project_id=project_id,
                    payload={"job_id": job_id, "reason": "Skipped due to agent busy concurrency policy"},
                    source="cron_scheduler"
                ))
            return

        # Start task execution
        logger.info(f"Triggering scheduled cron job {job_id} ('{job['name']}') on agent {agent_id}...")
        run_id = await dispatch_scheduled_job(self.runtime, job)

        # Compute next run time
        next_run = calculate_next_run(job['cron_expression'], trigger_time)

        # Update job state in DB
        self.db.update_cron_job(job_id, {
            'last_run_id': run_id,
            'last_run_at': trigger_time.isoformat(),
            'last_status': 'RUNNING',
            'next_run_at': next_run
        })

        if self.event_bus:
            self.event_bus.publish(PlatformEvent(
                event_id=f"evt_{datetime.now().timestamp()}",
                sequence_number=0,
                event_type=EventType.TASK_CREATED,
                agent_id=agent_id,
                task_id=run_id,
                project_id=project_id,
                payload={
                    "job_id": job_id,
                    "job_name": job['name'],
                    "cron_expression": job['cron_expression'],
                    "scheduled": True
                },
                source="cron_scheduler"
            ))

    async def trigger_now(self, job_id: str) -> Optional[str]:
        """Manually trigger a job immediately regardless of next_run_at."""
        job = self.db.get_cron_job(job_id)
        if not job:
            return None

        now_dt = datetime.now()
        run_id = await dispatch_scheduled_job(self.runtime, job)

        # Update last run state without resetting regular schedule
        self.db.update_cron_job(job_id, {
            'last_run_id': run_id,
            'last_run_at': now_dt.isoformat(),
            'last_status': 'RUNNING'
        })

        return run_id
