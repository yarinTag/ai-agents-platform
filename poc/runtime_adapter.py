"""
Runtime adapter for Free Claude Code integration.
Handles launching and managing Claude Code subprocesses.
"""

import subprocess
import os
import json
import time
import threading
import queue
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import uuid
import logging
from datetime import datetime

# Import from local modules using absolute imports
from config import AgentConfig, ProjectConfig


class TaskStatus(Enum):
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentRun:
    """Represents a running agent task."""
    run_id: str
    agent_id: str
    project_id: Optional[str]
    prompt: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    events: List[Dict[str, Any]] = None
    parent_task_id: Optional[str] = None
    root_task_id: Optional[str] = None
    assigned_by: Optional[str] = None

    def __post_init__(self):
        if self.events is None:
            self.events = []

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.ended_at:
            data['ended_at'] = self.ended_at.isoformat()
        data['status'] = self.status.value
        data['parent_task_id'] = self.parent_task_id
        data['root_task_id'] = self.root_task_id
        data['assigned_by'] = self.assigned_by
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentRun':
        data_copy = dict(data)
        # Convert ISO strings back to datetime objects
        if data_copy.get('created_at') and isinstance(data_copy['created_at'], str):
            data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if data_copy.get('started_at') and isinstance(data_copy['started_at'], str):
            data_copy['started_at'] = datetime.fromisoformat(data_copy['started_at'])
        if data_copy.get('ended_at') and isinstance(data_copy['ended_at'], str):
            data_copy['ended_at'] = datetime.fromisoformat(data_copy['ended_at'])
        if isinstance(data_copy.get('status'), str):
            data_copy['status'] = TaskStatus(data_copy['status'])
        data_copy.setdefault('project_id', None)
        data_copy.setdefault('parent_task_id', None)
        data_copy.setdefault('root_task_id', None)
        data_copy.setdefault('assigned_by', None)
        return cls(**data_copy)


class ClaudeCodeRuntimeAdapter:
    """
    Adapter for Free Claude Code runtime.
    Manages Claude Code subprocesses with appropriate environment.
    """

    def __init__(self):
        # Free Claude Code proxy configuration from environment or defaults
        self.proxy_url = os.getenv("ANTHROPIC_BASE_URL", os.getenv("FCC_PROXY_URL", "http://127.0.0.1:8082"))
        self.auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN", os.getenv("FCC_AUTH_TOKEN", "freecc"))
        self.max_concurrent_runs = int(os.getenv("PLATFORM_MAX_CONCURRENT_TASKS", "10"))

        # Active runs
        self._runs: Dict[str, AgentRun] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._event_queues: Dict[str, queue.Queue] = {}
        self._reader_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}

    def _build_claude_env(self) -> Dict[str, str]:
        """Build environment variables for Claude Code subprocess."""
        env = os.environ.copy()
        env.update({
            "ANTHROPIC_BASE_URL": self.proxy_url,
            "ANTHROPIC_AUTH_TOKEN": self.auth_token,
            "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "190000",
            "DISABLE_AUTOUPDATER": "1",
            "DISABLE_FEEDBACK_COMMAND": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "DISABLE_TELEMETRY": "1",
            "TERM": "dumb",
            "PYTHONIOENCODING": "utf-8"
        })
        return env

    def _build_claude_command(
        self,
        agent_config: AgentConfig,
        project_config: Optional[ProjectConfig],
        prompt: str,
        session_id: Optional[str] = None,
        fork_session: bool = False
    ) -> List[str]:
        """
        Build Claude Code command with appropriate arguments.

        Args:
            agent_config: Agent configuration
            project_config: Project configuration (optional)
            prompt: The prompt to execute
            session_id: Optional session ID to resume
            fork_session: Whether to fork a new session

        Returns:
            List of command arguments
        """
        cmd = ["claude"]
        if agent_config.model and agent_config.model.lower() != "default":
            cmd.extend(["--model", agent_config.model.lower()])

        if session_id and not session_id.startswith("pending_"):
            cmd.extend(["--resume", session_id])
            if fork_session:
                cmd.append("--fork-session")

        cmd.extend([
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose"
        ])

        # Make --dangerously-skip-permissions configurable per-agent or per-environment
        skip_permissions = (
            getattr(agent_config, "dangerously_skip_permissions", False) or
            os.getenv("PLATFORM_DANGEROUSLY_SKIP_PERMISSIONS", "").lower() in ("true", "1")
        )
        if skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # Enforce agent tool restrictions if configured
        if getattr(agent_config, "allowed_tools", None) and len(agent_config.allowed_tools) > 0:
            cmd.extend(["--allowedTools", ",".join(agent_config.allowed_tools)])

        # Add working directory restriction if specified
        if project_config and project_config.working_directory:
            work_dir = project_config.working_directory
            if os.path.exists(work_dir):
                cmd.extend(["--add-dir", work_dir])
            else:
                # Fallback to current directory if work dir doesn't exist
                cmd.extend(["--add-dir", os.getcwd()])
        else:
            cmd.extend(["--add-dir", os.getcwd()])

        return cmd

    def _parse_claude_output_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single line of Claude Code stream-json output.

        Args:
            line: Raw output line from Claude Code

        Returns:
            Parsed event dictionary or None if not valid JSON
        """
        line = line.strip()
        if not line:
            return None

        try:
            return json.loads(line)
        except json.JSONDecodeError:
            # Return as raw output event
            return {
                "type": "raw",
                "content": line
            }

    def _output_reader(
        self,
        run_id: str,
        process: subprocess.Popen,
        event_queue: queue.Queue,
        stop_event: threading.Event
    ):
        """
        Read output from Claude Code subprocess and put events in queue.

        Args:
            run_id: ID of the run
            process: Claude Code subprocess
            event_queue: Queue to put parsed events
            stop_event: Event to signal when to stop reading
        """
        try:
            while not stop_event.is_set() and process.poll() is None:
                line = process.stdout.readline()
                if line:
                    event = self._parse_claude_output_line(line)
                    if event:
                        # Add metadata
                        event['_timestamp'] = time.time()
                        event['_run_id'] = run_id
                        event_queue.put(event)
                else:
                    time.sleep(0.01)  # Short sleep to prevent busy waiting

            # Read any remaining output after process ends
            remaining_output = process.stdout.read()
            if remaining_output:
                for line in remaining_output.splitlines():
                    if line.strip():
                        event = self._parse_claude_output_line(line.decode('utf-8', errors='replace'))
                        if event:
                            event['_timestamp'] = time.time()
                            event['_run_id'] = run_id
                            event_queue.put(event)

        except Exception as e:
            # Put error event in queue
            error_event = {
                "type": "error",
                "error": {"message": f"Output reader error: {str(e)}"},
                "_timestamp": time.time(),
                "_run_id": run_id
            }
            event_queue.put(error_event)
        finally:
            # Signal end of output
            end_event = {
                "type": "end_of_output",
                "_timestamp": time.time(),
                "_run_id": run_id
            }
            event_queue.put(end_event)

    def start_task(
        self,
        agent_id: str,
        project_id: Optional[str] = None,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        fork_session: bool = False
    ) -> str:
        """
        Start a new agent task, or launch execution of an existing task run by ID.

        Args:
            agent_id: ID of the agent to use (or run_id if prompt is omitted)
            project_id: ID of the project context (optional)
            prompt: The task prompt to execute (optional if existing run ID provided)
            session_id: Optional session ID to resume
            fork_session: Whether to fork a new session

        Returns:
            Run ID for tracking the task
        """
        # Import here to avoid circular imports
        from config import config_manager

        # Check if agent_id is an existing subtask/run ID when prompt is omitted
        if prompt is None:
            existing_run = self._runs.get(agent_id)
            if not existing_run:
                try:
                    from persistence import db_manager
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
                        from persistence import db_manager
                        agent_config = db_manager.get_agent(existing_run.agent_id)
                    except Exception:
                        pass
                project_config = None
                if existing_run.project_id:
                    project_config = config_manager.get_project(existing_run.project_id)
                    if not project_config:
                        try:
                            from persistence import db_manager
                            project_config = db_manager.get_project(existing_run.project_id)
                        except Exception:
                            pass
                thread = threading.Thread(
                    target=self._execute_task,
                    args=(run_id, agent_config, project_config, existing_run.prompt, session_id, fork_session)
                )
                thread.daemon = True
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
                from persistence import db_manager
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
                    from persistence import db_manager
                    project_config = db_manager.get_project(project_id)
                except Exception:
                    pass
            if not project_config:
                raise ValueError(f"Project not found: {project_id}")

        # Create run ID
        run_id = str(uuid.uuid4())

        # Create agent run record
        run = AgentRun(
            run_id=run_id,
            agent_id=agent_id,
            project_id=project_id,
            prompt=prompt,
            status=TaskStatus.QUEUED,
            created_at=datetime.now()
        )

        self._runs[run_id] = run

        # Start the task in a background thread to avoid blocking
        thread = threading.Thread(
            target=self._execute_task,
            args=(run_id, agent_config, project_config, prompt, session_id, fork_session)
        )
        thread.daemon = True
        thread.start()

        return run_id

    def _execute_task(
        self,
        run_id: str,
        agent_config: AgentConfig,
        project_config: Optional[ProjectConfig],
        prompt: str,
        session_id: Optional[str],
        fork_session: bool
    ):
        """
        Execute a task in a Claude Code subprocess.

        Args:
            run_id: ID of the run
            agent_config: Agent configuration
            project_config: Project configuration
            prompt: The task prompt
            session_id: Optional session ID to resume
            fork_session: Whether to fork a new session
        """
        run = self._runs[run_id]

        try:
            # Update status to running
            run.status = TaskStatus.RUNNING
            run.started_at = datetime.now()

            # Build command and environment
            cmd = self._build_claude_command(agent_config, project_config, prompt, session_id, fork_session)
            env = self._build_claude_env()

            # Determine working directory
            if project_config and project_config.working_directory:
                work_dir = project_config.working_directory
                if not os.path.exists(work_dir):
                    work_dir = os.getcwd()
            else:
                work_dir = os.getcwd()

            # Launch Claude Code process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=work_dir,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            self._processes[run_id] = process

            # Set up output reading
            event_queue = queue.Queue()
            stop_event = threading.Event()
            self._event_queues[run_id] = event_queue
            self._stop_events[run_id] = stop_event

            reader_thread = threading.Thread(
                target=self._output_reader,
                args=(run_id, process, event_queue, stop_event)
            )
            reader_thread.daemon = True
            reader_thread.start()
            self._reader_threads[run_id] = reader_thread

            # Process events
            while True:
                try:
                    # Get event with timeout to allow checking for cancellation
                    event = event_queue.get(timeout=0.1)

                    # Add event to run
                    run.events.append(event)

                    # Handle special events
                    if event.get("type") == "result":
                        # Task completed successfully
                        run.result = event.get("result")
                        run.status = TaskStatus.COMPLETED
                        break
                    elif event.get("type") == "error":
                        # Task failed
                        error_info = event.get("error", {})
                        run.error = error_info.get("message", "Unknown error")
                        run.status = TaskStatus.FAILED
                        break
                    elif event.get("type") == "end_of_output":
                        # Process ended without explicit result/error
                        run.status = TaskStatus.COMPLETED if run.result else TaskStatus.FAILED
                        if not run.error and not run.result:
                            run.error = "Process ended without result or error"
                        break

                except queue.Empty:
                    # Check if process has ended
                    if process.poll() is not None:
                        # Process ended, check if we got all output
                        time.sleep(0.1)  # Give a moment for final events
                        if not self._stop_events[run_id].is_set():
                            # Process ended unexpectedly
                            run.status = TaskStatus.FAILED
                            run.error = f"Process exited with code {process.poll()}"
                        break
                    elif self._stop_events[run_id].is_set():
                        # We were signaled to stop
                        break
                    continue

        except Exception as e:
            # Report the real error — do not fabricate fake success results
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Runtime execution failed for run {run_id}: {e}", exc_info=True)
            run.status = TaskStatus.FAILED
            run.error = f"Runtime execution failed: {str(e)}"
            run.events.append({
                "type": "error",
                "error": {"message": f"Runtime execution failed: {str(e)}"},
                "_timestamp": time.time(),
                "_run_id": run_id
            })
        finally:
            # Clean up
            run.ended_at = datetime.now()
            try:
                from persistence import db_manager
                db_manager.save_task_run(run)
            except Exception as dbe:
                logging.getLogger(__name__).warning(f"Failed to save task run to DB: {dbe}")

            # Signal output reader to stop
            if run_id in self._stop_events:
                self._stop_events[run_id].set()

            # Terminate process if still running
            if run_id in self._processes:
                process = self._processes[run_id]
                if process.poll() is None:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                # Clean up
                del self._processes[run_id]

            # Clean up other resources
            if run_id in self._event_queues:
                del self._event_queues[run_id]
            if run_id in self._reader_threads:
                del self._reader_threads[run_id]
            if run_id in self._stop_events:
                del self._stop_events[run_id]

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
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

        run.status = TaskStatus.CANCELLED
        run.ended_at = datetime.now()
        run.error = "Task cancelled by user"

        return True

    def subscribe_to_events(
        self,
        run_id: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> Callable[[], None]:
        """
        Subscribe to events for a run.

        Args:
            run_id: ID of the run to subscribe to
            handler: Function to call for each event

        Returns:
        Unsubscribe function
        """
        if run_id not in self._event_queues:
            def unsubscribe(): pass
            return unsubscribe

        event_queue = self._event_queues[run_id]

        def event_listener():
            while True:
                try:
                    event = event_queue.get(timeout=0.1)
                    if event.get("type") == "end_of_output":
                        break
                    handler(event)
                except queue.Empty:
                    if run_id not in self._runs or self._runs[run_id].status in [
                        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
                    ]:
                        break
                    continue
                except Exception:
                    break

        # Start listener thread
        listener_thread = threading.Thread(target=event_listener)
        listener_thread.daemon = True
        listener_thread.start()

        def unsubscribe():
            # Nothing to do - listener will exit when queue gets end_of_output
            pass

        return unsubscribe


# Global runtime adapter instance
runtime_adapter = ClaudeCodeRuntimeAdapter()