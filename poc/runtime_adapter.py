"""Compatibility facade for Claude Code subprocess task lifecycle.

Implementation collaborators live in runtime/. The facade owns active run state
and preserves existing entry points, models and provider-setting exports.
"""

import logging
import os
import queue
import subprocess
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from config import AgentConfig, ProjectConfig
import runtime_providers as providers
from runtime.models import AgentRun, TaskStatus
from runtime.questions import extract_supervisor_question
from runtime.progress import build_task_progress_payload, summarize_runtime_event
from runtime.command_builder import RuntimeCommandBuilder
from runtime.execution import TaskExecutor
from runtime.legacy_services import create_legacy_services
from runtime.output_stream import parse_output_line, read_output
from runtime.processes import terminate_process
from runtime.services import RuntimeServices
from runtime.subscriptions import RuntimeSubscriptions, subscribe_to_events

RUNTIME_PROVIDER_SETTING_KEY = providers.SETTING_PROVIDER
RUNTIME_GATEWAY_URL_SETTING_KEY = providers.SETTING_GATEWAY_URL
RUNTIME_SETUP_COMPLETED_KEY = providers.SETTING_SETUP_COMPLETED
logger = logging.getLogger(__name__)
_ACTIVE_TASK_STATUSES = {
    TaskStatus.QUEUED, TaskStatus.RUNNING,
    TaskStatus.WAITING_INPUT, TaskStatus.PENDING_APPROVAL,
}


class ClaudeCodeRuntimeAdapter:
    """Stateful lifecycle facade composed from focused runtime collaborators."""

    extract_supervisor_question = staticmethod(extract_supervisor_question)

    def __init__(self, services: Optional[RuntimeServices] = None):
        # Legacy attributes retained for callers that still read them; actual
        # backend routing now comes from the runtime provider registry.
        self.proxy_url = os.getenv("FCC_PROXY_URL", providers.FREE_CLAUDE_CODE_DEFAULT_URL)
        self.auth_token = os.getenv("FCC_AUTH_TOKEN", providers.FREE_CLAUDE_CODE_DEFAULT_TOKEN)
        self.max_concurrent_runs = int(os.getenv("PLATFORM_MAX_CONCURRENT_TASKS", "10"))

        # Active runs
        self._runs: Dict[str, AgentRun] = {}
        self._last_progress_emit: Dict[str, float] = {}
        self._checkpoint_interval_sec = float(os.getenv("PLATFORM_TASK_CHECKPOINT_SEC", "2.0"))
        self._checkpoint_event_batch = int(os.getenv("PLATFORM_TASK_CHECKPOINT_EVENTS", "3"))
        self._processes: Dict[str, subprocess.Popen] = {}
        self._event_queues: Dict[str, queue.Queue] = {}
        self._reader_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._shutting_down = False
        self._execution_threads = {}
        self._run_locks = {}
        self._stderr_threads = {}
        self.on_task_completed: Optional[Callable[[AgentRun], None]] = None

        self.services = services or create_legacy_services(self)
        self._command_builder = RuntimeCommandBuilder(self.services)
        self._executor = TaskExecutor(self)
        self._subscriptions = RuntimeSubscriptions()

    def _emit_task_event(self, run: AgentRun, event_type: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Publish task lifecycle/progress events to the platform EventService."""
        try:
            if not self.services.emit:
                return
            payload = build_task_progress_payload(run)
            if extra:
                payload.update(extra)
            self.services.emit(
                event_type=event_type,
                payload=payload,
                agent_id=run.agent_id,
                task_id=run.run_id,
                project_id=run.project_id,
                source="runtime_adapter",
            )
        except Exception as emit_err:
            logging.getLogger(__name__).debug(f"Task event emit skipped: {emit_err}")

    def _checkpoint_run(self, run: AgentRun, *, emit_progress: bool = True, force_emit: bool = False) -> None:
        """Persist in-flight task state and optionally broadcast progress over SSE."""
        try:
            db_manager = self.services.database()
            db_manager.save_task_run(run)
        except Exception as db_err:
            logging.getLogger(__name__).warning(f"Failed to checkpoint task {run.run_id}: {db_err}")

        if not emit_progress:
            return

        now = time.time()
        last_emit = self._last_progress_emit.get(run.run_id, 0.0)
        if not force_emit and (now - last_emit) < self._checkpoint_interval_sec:
            return

        self._last_progress_emit[run.run_id] = now
        self._emit_task_event(run, "task.progress")

    def _emit_terminal_task_event(self, run: AgentRun) -> None:
        """Emit completion/failure/waiting lifecycle events once a run reaches a terminal pause state."""
        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        if status_val == "completed":
            self._emit_task_event(run, "task.completed")
        elif status_val == "failed":
            self._emit_task_event(run, "task.failed")
        elif status_val == "cancelled":
            self._emit_task_event(run, "task.cancelled")
        elif status_val == "waiting_input":
            self._emit_task_event(run, "task.waiting_input")
        elif status_val == "pending_approval":
            self._emit_task_event(run, "approval.required")

    def configure_services(self, services: RuntimeServices) -> None:
        """Replace integrations at composition time, before starting new runs."""
        self._shutting_down = False
        self.services = services
        self._command_builder.services = services

    def resolve_runtime_provider(self, agent_config: Optional[AgentConfig] = None) -> str:
        return self._command_builder.resolve_runtime_provider(agent_config)

    def _build_claude_env(self, run_id=None, project_id=None, agent_config=None):
        return self._command_builder._build_claude_env(run_id, project_id, agent_config)

    def _resolve_working_directory(self, project_config, agent_config):
        return self._command_builder._resolve_working_directory(project_config, agent_config)

    def _build_claude_command(self, agent_config, project_config, prompt,
                              session_id=None, fork_session=False,
                              dangerously_skip_permissions=False):
        return self._command_builder._build_claude_command(
            agent_config, project_config, prompt, session_id, fork_session,
            dangerously_skip_permissions,
        )

    def _parse_claude_output_line(self, line):
        return parse_output_line(line)

    def _output_reader(self, run_id, process, event_queue, stop_event):
        return read_output(self._parse_claude_output_line, run_id, process, event_queue, stop_event)

    def _execute_task(self, run_id, agent_config, project_config, prompt,
                      session_id, fork_session, dangerously_skip_permissions=False):
        return self._executor.execute(
            run_id, agent_config, project_config, prompt, session_id,
            fork_session, dangerously_skip_permissions,
        )

    def subscribe_to_events(self, run_id, handler):
        return subscribe_to_events(self, run_id, handler)

    def start_task(
        self,
        agent_id: str,
        project_id: Optional[str] = None,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        fork_session: bool = False,
        task_id: Optional[str] = None
    ) -> str:
        """
        Start a new agent task, or launch execution of an existing task run by ID.

        Args:
            agent_id: ID of the agent to use (or run_id if prompt is omitted)
            project_id: ID of the project context (optional)
            prompt: The task prompt to execute (optional if existing run ID provided)
            session_id: Optional session ID to resume
            fork_session: Whether to fork a new session
            task_id: Optional specific task/run ID to reuse or assign (1 Session == 1 Task)

        Returns:
            Run ID for tracking the task
        """
        if self._shutting_down:
            raise RuntimeError("Runtime is shutting down")
        # Import here to avoid circular imports
        config_manager = self.services.configuration()

        # Check if agent_id is an existing subtask/run ID when prompt is omitted
        if prompt is None:
            existing_run = self._runs.get(agent_id)
            if not existing_run:
                try:
                    db_manager = self.services.database()
                    existing_run = db_manager.get_task_run(agent_id)
                    if existing_run:
                        self._runs[existing_run.run_id] = existing_run
                except Exception:
                    pass

            if existing_run:
                run_id = existing_run.run_id
                agent_config = config_manager.get_agent(existing_run.agent_id)
                if not agent_config:
                    try:
                        db_manager = self.services.database()
                        agent_config = db_manager.get_agent(existing_run.agent_id)
                    except Exception:
                        pass
                project_config = None
                if existing_run.project_id:
                    project_config = config_manager.get_project(existing_run.project_id)
                    if not project_config:
                        try:
                            db_manager = self.services.database()
                            project_config = db_manager.get_project(existing_run.project_id)
                        except Exception:
                            pass
                thread = threading.Thread(
                    target=self._execute_task,
                    args=(run_id, agent_config, project_config, existing_run.prompt, session_id, fork_session)
                )
                thread.daemon = True
                self._execution_threads[thread] = run_id
                thread.start()
                return run_id

        # Check platform-wide concurrency limit
        active_processes = sum(1 for p in self._processes.values() if p.poll() is None)
        if active_processes >= self.max_concurrent_runs:
            raise RuntimeError(f"Platform concurrency limit reached ({self.max_concurrent_runs} active runs). Try again later.")

        # Get configurations
        agent_config = config_manager.get_agent(agent_id)
        if not agent_config:
            try:
                db_manager = self.services.database()
                agent_config = db_manager.get_agent(agent_id)
            except Exception:
                pass
        if not agent_config:
            raise ValueError(f"Agent not found: {agent_id}")

        project_config = None
        if project_id:
            project_config = config_manager.get_project(project_id)
            if not project_config:
                try:
                    db_manager = self.services.database()
                    project_config = db_manager.get_project(project_id)
                except Exception:
                    pass
            if not project_config:
                raise ValueError(f"Project not found: {project_id}")

        # Terminate any hung process for this task_id if one is still running
        if task_id and task_id in self._processes:
            p = self._processes[task_id]
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=2)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass

        # Determine run ID (1 Session == 1 Task: reuses task_id if provided)
        run_id = task_id or str(uuid.uuid4())

        existing_run = self._runs.get(run_id)
        if not existing_run:
            try:
                db_manager = self.services.database()
                existing_run = db_manager.get_task_run(run_id)
            except Exception:
                pass

        if existing_run:
            existing_run.prompt = prompt or existing_run.prompt
            existing_run.status = TaskStatus.QUEUED
            existing_run.result = None
            existing_run.error = None
            existing_run.ended_at = None
            existing_run.events = []
            if session_id:
                existing_run.session_id = session_id
            self._runs[run_id] = existing_run
            try:
                db_manager = self.services.database()
                db_manager.save_task_run(existing_run)
            except Exception as db_err:
                logger.warning(f"Failed to update task run {run_id}: {db_err}")
            run = existing_run
        else:
            run = AgentRun(
                run_id=run_id,
                agent_id=agent_id,
                project_id=project_id,
                prompt=prompt or "Session Task",
                status=TaskStatus.QUEUED,
                created_at=datetime.now()
            )
            if session_id:
                run.session_id = session_id
            self._runs[run_id] = run
            try:
                db_manager = self.services.database()
                db_manager.save_task_run(run)
            except Exception as db_err:
                logger.warning(f"Failed to persist queued task run {run_id}: {db_err}")

        # Start the task in a background thread to avoid blocking
        thread = threading.Thread(
            target=self._execute_task,
            args=(run_id, agent_config, project_config, prompt, session_id, fork_session)
        )
        thread.daemon = True
        self._execution_threads[thread] = run_id
        thread.start()

        return run_id

    def resume_task(self, run_id: str, answer: str) -> str:
        """
        Resume an existing paused task (WAITING_INPUT) by passing the supervisor/human answer back into the session.
        """
        if self._shutting_down:
            raise RuntimeError("Runtime is shutting down")
        run = self._runs.get(run_id)
        if not run:
            try:
                db_manager = self.services.database()
                run = db_manager.get_task_run(run_id)
                if run:
                    self._runs[run_id] = run
            except Exception:
                pass

        if not run:
            raise ValueError(f"Task run {run_id} not found to resume")

        config_manager = self.services.configuration()
        agent_config = config_manager.get_agent(run.agent_id)
        if not agent_config:
            try:
                db_manager = self.services.database()
                agent_config = db_manager.get_agent(run.agent_id)
            except Exception:
                pass

        project_config = config_manager.get_project(run.project_id) if run.project_id else None

        continuation_prompt = f"Supervisor response to your question: {answer}. Please proceed and complete the task."
        run.status = TaskStatus.RUNNING
        run.started_at = datetime.now()
        run.ended_at = None
        run.result = None

        # Check if user answer or previous run status indicates permission was granted
        answer_lower = answer.lower()
        grants_perm = any(w in answer_lower for w in ("permission", "grant", "allow", "continue", "approved", "approve", "yes", "proceed", "ok"))
        was_perm_blocked = run.result and ("permission" in run.result.lower() or "blocked" in run.result.lower())
        skip_perm = grants_perm or bool(was_perm_blocked) or getattr(run, "dangerously_skip_permissions", False)
        run.dangerously_skip_permissions = skip_perm

        thread = threading.Thread(
            target=self._execute_task,
            args=(run_id, agent_config, project_config, continuation_prompt, run.session_id, False, skip_perm)
        )
        thread.daemon = True
        self._execution_threads[thread] = run_id
        thread.start()
        return run_id

    def list_runs(self) -> List[AgentRun]:
        """List all known runs in memory."""
        return list(self._runs.values())

    def get_run_status(self, run_id: str) -> Optional[AgentRun]:
        """
        Get the status of a run.

        Args:
            run_id: ID of the run to check

        Returns:
            AgentRun object or None if not found
        """
        return self._runs.get(run_id)

    def cancel_run(self, run_id: str) -> bool:
        """
        Cancel a running task.

        Args:
            run_id: ID of the run to cancel

        Returns:
            True if cancellation was initiated, False if not found
        """
        run = self._runs.get(run_id)
        if not run:
            return False

        if run.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False  # Already finished

        # Signal cancellation
        if run_id in self._stop_events:
            self._stop_events[run_id].set()

        # Terminate process
        if run_id in self._processes:
            process = self._processes[run_id]
            terminate_process(process)

        run.status = TaskStatus.CANCELLED
        run.ended_at = datetime.now()
        run.error = "Task cancelled by user"
        self._subscriptions.close_run(run_id)

        return True


    def shutdown(self):
        """Stop accepting runs and release this runtime's processes/subscribers."""
        self._shutting_down = True
        self.on_task_completed = None
        for run in list(self._runs.values()):
            try:
                self.cancel_run(run.run_id)
            except Exception:
                logger.exception("Runtime cancellation failed for %s", run.run_id)
            finally:
                self._subscriptions.close_run(run.run_id)
        for thread in list(self._execution_threads):
            if thread is not threading.current_thread():
                thread.join(timeout=2)


# Global compatibility instance; concrete services are resolved lazily.
runtime_adapter = ClaudeCodeRuntimeAdapter()
