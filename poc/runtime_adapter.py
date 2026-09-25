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
from datetime import datetime
import re
import uuid
import logging

# Import from local modules using absolute imports
from config import AgentConfig, ProjectConfig


class TaskStatus(Enum):
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    SCHEDULED = "scheduled"
    WAITING_INPUT = "waiting_input"
    PENDING_APPROVAL = "pending_approval"
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
    session_id: Optional[str] = None
    dangerously_skip_permissions: bool = False

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
        data['dangerously_skip_permissions'] = self.dangerously_skip_permissions
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
        data_copy.setdefault('session_id', None)
        data_copy.setdefault('dangerously_skip_permissions', False)
        return cls(**data_copy)


def extract_supervisor_question(data: Any) -> Optional[Dict[str, Any]]:
    """
    Detects if an event or model output represents a supervisor clarification question,
    permission request, or waiting input condition.
    Returns dictionary with {"question": ..., "context": ..., "suggested_options": ..., "is_permission": ...} or None.
    """
    if not data:
        return None

    # Case 1: Dict event
    if isinstance(data, dict):
        # 1a. Structured permission denials from Claude Code
        denials = data.get("permission_denials")
        if denials and isinstance(denials, list) and len(denials) > 0:
            tool_names = list({d.get("tool_name") for d in denials if isinstance(d, dict) and d.get("tool_name")})
            tools_str = ", ".join(tool_names) if tool_names else "tools"
            res_text = data.get("result", "")
            q_text = res_text if res_text else f"Permission required to execute tool(s): {tools_str}"
            return {
                "question": q_text,
                "context": f"Runtime sandbox denied permissions for {tools_str}.",
                "suggested_options": ["Grant permission", "Deny"],
                "is_permission": True
            }

        # 1b. Direct tool_use event
        if data.get("type") == "tool_use" and data.get("name") in ("ask_supervisor", "ask_manager", "ask_question", "AskUserQuestion"):
            inp = data.get("input", {})
            q = None
            opts = []
            if isinstance(inp, dict):
                if inp.get("questions") and isinstance(inp["questions"], list) and len(inp["questions"]) > 0:
                    q = inp["questions"][0].get("question")
                    opts = [o.get("label", "") for o in inp["questions"][0].get("options", []) if isinstance(o, dict)]
                if not q:
                    q = inp.get("question") or inp.get("prompt")
            return {
                "question": q or str(inp),
                "context": f"Agent invoked {data.get('name')}.",
                "suggested_options": opts
            }

        # 1c. Tool call nested inside assistant message
        if data.get("type") == "assistant":
            msg = data.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        name = item.get("name")
                        if name in ("ask_supervisor", "ask_manager", "ask_question", "AskUserQuestion"):
                            inp = item.get("input", {})
                            q = None
                            opts = []
                            if isinstance(inp, dict):
                                if inp.get("questions") and isinstance(inp["questions"], list) and len(inp["questions"]) > 0:
                                    q = inp["questions"][0].get("question")
                                    opts = [o.get("label", "") for o in inp["questions"][0].get("options", []) if isinstance(o, dict)]
                                if not q:
                                    q = inp.get("question") or inp.get("prompt")
                            return {
                                "question": q or str(inp),
                                "context": f"Agent invoked {name}.",
                                "suggested_options": opts
                            }

        # 1e. Check nested content or result fields
        if "result" in data and isinstance(data["result"], str):
            res_q = extract_supervisor_question(data["result"])
            if res_q:
                return res_q
        if "content" in data and isinstance(data["content"], str):
            cnt_q = extract_supervisor_question(data["content"])
            if cnt_q:
                return cnt_q

    # Case 2: String content or result
    if isinstance(data, str):
        text = data.strip()
        text_lower = text.lower()

        if "ask_supervisor" in text or "ask_manager" in text:
            try:
                match = re.search(r'\{.*"question".*\}', text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if "question" in parsed:
                        return {
                            "question": parsed["question"],
                            "context": parsed.get("context", ""),
                            "suggested_options": parsed.get("suggested_options", [])
                        }
            except Exception:
                pass

        if "[SUPERVISOR_REQUEST]" in text or "[ASK_SUPERVISOR]" in text:
            clean = text.replace("[SUPERVISOR_REQUEST]", "").replace("[ASK_SUPERVISOR]", "").strip()
            return {
                "question": clean,
                "context": "Agent flagged need for supervisor direction.",
                "suggested_options": []
            }

        # Check if this text is actually a completion report describing past actions rather than an active question
        completion_indicators = [
            "task is complete", "task completed", "the task is complete", "completed the task",
            "file has been created", "file was created", "created the file", "i verified",
            "verification result", "i have implemented", "i created the file", "done.", "finished."
        ]
        if any(ci in text_lower for ci in completion_indicators):
            return None

        # If quoting past questions (e.g. 'question asked:', 'i asked my supervisor'), ignore
        if "question asked" in text_lower or "i asked my supervisor" in text_lower or "i asked the supervisor" in text_lower:
            return None

        clarification_markers = [
            "please clarify", "could you clarify", "please specify", "please provide",
            "i need to know", "need more information", "before proceeding", "cannot proceed without",
            "waiting for your response", "waiting for response", "i am waiting for",
            "אנא ספק", "תוכל להבהיר", "נא להבהיר", "חסר מידע", "איזה קובץ", "איזה פורמט", "איזו מחרוזת", "מה המחרוזת"
        ]
        if any(marker in text_lower for marker in clarification_markers):
            return {
                "question": text,
                "context": "Agent indicated missing parameters or needed clarification to proceed.",
                "suggested_options": []
            }

    return None


_ACTIVE_TASK_STATUSES = {
    TaskStatus.QUEUED,
    TaskStatus.RUNNING,
    TaskStatus.WAITING_INPUT,
    TaskStatus.PENDING_APPROVAL,
}


def summarize_runtime_event(event: Optional[Dict[str, Any]]) -> Optional[str]:
    """Human-readable one-liner for the latest Claude stream-json event."""
    if not event:
        return None
    event_type = event.get("type", "event")
    if event_type == "assistant":
        msg = event.get("message", {})
        content = msg.get("content", []) if isinstance(msg, dict) else []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    return f"Using tool: {item.get('name', 'unknown')}"
                if isinstance(item, dict) and item.get("type") == "text":
                    text = (item.get("text") or "").strip()
                    if text:
                        return text[:120] + ("..." if len(text) > 120 else "")
        return "Assistant response"
    if event_type == "tool_use":
        return f"Using tool: {event.get('name', 'unknown')}"
    if event_type == "tool_result":
        return "Tool result received"
    if event_type == "result":
        result = (event.get("result") or "").strip()
        return result[:120] + ("..." if len(result) > 120 else "") if result else "Task finished"
    if event_type == "error":
        err = event.get("error", {})
        return f"Error: {err.get('message', 'unknown')}" if isinstance(err, dict) else "Error"
    if event_type == "raw":
        content = (event.get("content") or "").strip()
        return content[:80] + ("..." if len(content) > 80 else "") if content else "Raw output"
    return event_type.replace("_", " ").title()


def build_task_progress_payload(run: "AgentRun") -> Dict[str, Any]:
    """Compact progress snapshot for API responses and SSE events."""
    events = run.events or []
    last = events[-1] if events else None
    elapsed = None
    if run.started_at:
        end = run.ended_at or datetime.now()
        elapsed = max(0, int((end - run.started_at).total_seconds()))
    type_counts: Dict[str, int] = {}
    for ev in events:
        t = ev.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    return {
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "project_id": run.project_id,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "event_count": len(events),
        "event_types": type_counts,
        "last_event_type": last.get("type") if last else None,
        "last_event_summary": summarize_runtime_event(last),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "elapsed_seconds": elapsed,
        "session_id": run.session_id,
        "result_preview": (run.result[:160] + "...") if run.result and len(run.result) > 160 else run.result,
    }


class ClaudeCodeRuntimeAdapter:
    """
    Adapter for Free Claude Code runtime.
    Manages Claude Code subprocesses with appropriate environment.
    """

    extract_supervisor_question = staticmethod(extract_supervisor_question)

    def __init__(self):
        # Free Claude Code proxy configuration from environment or defaults
        self.proxy_url = os.getenv("ANTHROPIC_BASE_URL", os.getenv("FCC_PROXY_URL", "http://127.0.0.1:8082"))
        self.auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN", os.getenv("FCC_AUTH_TOKEN", "freecc"))
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

    def _emit_task_event(self, run: AgentRun, event_type: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Publish task lifecycle/progress events to the platform EventService."""
        try:
            import backend.dependencies as bdep
            event_service = getattr(bdep, "_event_service", None)
            if not event_service:
                return
            payload = build_task_progress_payload(run)
            if extra:
                payload.update(extra)
            event_service.emit(
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
            from persistence import db_manager
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
        fork_session: bool = False,
        dangerously_skip_permissions: bool = False
    ) -> List[str]:
        """
        Build Claude Code command with appropriate arguments.

        Args:
            agent_config: Agent configuration
            project_config: Project configuration (optional)
            prompt: The prompt to execute
            session_id: Optional session ID to resume
            fork_session: Whether to fork a new session
            dangerously_skip_permissions: Whether to skip permission prompts

        Returns:
            List of command arguments
        """
        cmd = ["claude"]
        if agent_config.model and agent_config.model.lower() != "default":
            cmd.extend(["--model", agent_config.model.lower()])

        if session_id and not session_id.startswith("pending_") and not session_id.startswith("sess_"):
            cmd.extend(["--resume", session_id])
            if fork_session:
                cmd.append("--fork-session")

        cmd.extend([
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose"
        ])

        # Make --dangerously-skip-permissions configurable per-agent, per-run, or per-environment
        skip_permissions = (
            dangerously_skip_permissions or
            getattr(agent_config, "dangerously_skip_permissions", False) or
            os.getenv("PLATFORM_DANGEROUSLY_SKIP_PERMISSIONS", "true").lower() in ("true", "1")
        )
        if skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # Add working directory restriction if specified
        target_dir = None
        if project_config and getattr(project_config, "working_directory", None) and os.path.exists(project_config.working_directory):
            target_dir = project_config.working_directory
        elif getattr(agent_config, "repo_path", None) and os.path.exists(agent_config.repo_path):
            target_dir = agent_config.repo_path
        else:
            target_dir = os.getcwd()

        cmd.extend(["--add-dir", target_dir])

        # Pass agent system prompt with supervisor context and workspace if configured
        if getattr(agent_config, "system_prompt", None):
            sys_prompt = agent_config.system_prompt
            sys_prompt += (
                f"\n\n[PROJECT WORKSPACE]\n"
                f"Your assigned project workspace directory is: {target_dir}\n"
                f"All files created, edited, read, or verified MUST reside inside this directory: {target_dir}"
            )
            if getattr(agent_config, "parent_id", None):
                parent_name = agent_config.parent_id
                try:
                    from persistence import db_manager
                    parent = db_manager.get_agent(agent_config.parent_id)
                    if parent and parent.name:
                        parent_name = parent.name
                except Exception:
                    pass
                sys_prompt += (
                    f"\n\n[ORGANIZATION HIERARCHY & SUPERVISOR INSTRUCTIONS]\n"
                    f"Your supervisor is {parent_name} (ID: {agent_config.parent_id}).\n"
                    f"If you lack required information, parameters, or permissions, ask your supervisor directly by stating your question clearly or using AskUserQuestion.\n"
                    f"State the question clearly so your supervisor can provide the answer or permission."
                )
            cmd.extend(["--system-prompt", sys_prompt])

        # Enforce agent tool restrictions if configured
        if getattr(agent_config, "allowed_tools", None) and len(agent_config.allowed_tools) > 0:
            cmd.extend(["--allowedTools", ",".join(agent_config.allowed_tools)])

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
                from persistence import db_manager
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
                from persistence import db_manager
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
                from persistence import db_manager
                db_manager.save_task_run(run)
            except Exception as db_err:
                logger.warning(f"Failed to persist queued task run {run_id}: {db_err}")

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
        fork_session: bool,
        dangerously_skip_permissions: bool = False
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
            dangerously_skip_permissions: Whether to bypass permission dialogs
        """
        run = self._runs[run_id]

        try:
            # Update status to running
            run.status = TaskStatus.RUNNING
            run.started_at = datetime.now()

            # Build command and environment
            skip_perm = dangerously_skip_permissions or getattr(run, "dangerously_skip_permissions", False)
            cmd = self._build_claude_command(
                agent_config, project_config, prompt, session_id, fork_session,
                dangerously_skip_permissions=skip_perm
            )
            env = self._build_claude_env()

            # Determine working directory
            if project_config and getattr(project_config, "working_directory", None) and os.path.exists(project_config.working_directory):
                work_dir = project_config.working_directory
            elif getattr(agent_config, "repo_path", None) and os.path.exists(agent_config.repo_path):
                work_dir = agent_config.repo_path
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

                    # Capture Claude session ID if emitted
                    captured_sid = None
                    if event.get("session_id"):
                        captured_sid = event["session_id"]
                    elif event.get("data", {}).get("session_id"):
                        captured_sid = event["data"]["session_id"]
                    elif event.get("type") == "result" and event.get("session_id"):
                        captured_sid = event["session_id"]

                    if captured_sid:
                        run.session_id = captured_sid
                        try:
                            from persistence import db_manager
                            with db_manager._get_connection() as conn:
                                conn.execute("""
                                    UPDATE agent_conversations
                                    SET claude_session_id = ?, updated_at = ?
                                    WHERE agent_id = ? AND (task_id = ? OR status = 'ACTIVE')
                                """, (captured_sid, datetime.now().isoformat(), run.agent_id, run.run_id))
                                conn.commit()
                        except Exception:
                            pass

                    # Check for explicit tool call for supervisor clarification or permission
                    tool_q = extract_supervisor_question(event)
                    if tool_q:
                        from orchestration.supervisor_resolver import SupervisorResolver
                        from persistence import db_manager
                        resolver = SupervisorResolver(db_manager, runtime_adapter=self)
                        resolution = resolver.resolve_or_escalate_question(
                            task_id=run.run_id,
                            requester_agent_id=run.agent_id,
                            question=tool_q["question"],
                            project_id=run.project_id,
                            context=tool_q.get("context"),
                            suggested_options=tool_q.get("suggested_options")
                        )
                        if resolution.get("status") == "AUTO_RESOLVED":
                            run.status = TaskStatus.RUNNING
                        else:
                            run.status = TaskStatus.WAITING_INPUT
                            run.result = f"Waiting for {resolution.get('target_approver', 'supervisor')} response: {tool_q['question']}"
                        break

                    # Handle special events
                    if event.get("type") == "result":
                        res_val = event.get("result", "")
                        q_data = extract_supervisor_question(event) or extract_supervisor_question(res_val)
                        if q_data:
                            from orchestration.supervisor_resolver import SupervisorResolver
                            from persistence import db_manager
                            resolver = SupervisorResolver(db_manager, runtime_adapter=self)
                            resolution = resolver.resolve_or_escalate_question(
                                task_id=run.run_id,
                                requester_agent_id=run.agent_id,
                                question=q_data["question"],
                                project_id=run.project_id,
                                context=q_data.get("context"),
                                suggested_options=q_data.get("suggested_options")
                            )
                            if resolution.get("status") == "AUTO_RESOLVED":
                                run.status = TaskStatus.RUNNING
                            else:
                                run.status = TaskStatus.WAITING_INPUT
                                run.result = f"Waiting for {resolution.get('target_approver', 'supervisor')} response: {q_data['question']}"
                            break
                        else:
                            # Task completed successfully
                            run.result = res_val
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
            # Clean up: only mark ended_at for terminal statuses (not paused WAITING_INPUT)
            if run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                run.ended_at = datetime.now()
            else:
                run.ended_at = None
            try:
                from persistence import db_manager
                db_manager.save_task_run(run)

                # Record task response in chat_messages for the agent
                if run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.WAITING_INPUT) and run.agent_id:
                    try:
                        conv = db_manager.get_or_create_conversation(run.agent_id, project_id=run.project_id)
                        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
                        content_text = run.result if (status_val in ("completed", "waiting_input") and run.result) else (run.error or "Task completed.")
                        if not db_manager.has_chat_message_for_task(run.agent_id, run.run_id, "ASSISTANT", content=content_text):
                            assistant_msg = db_manager.save_chat_message({
                                "conversation_id": conv["id"],
                                "agent_id": run.agent_id,
                                "task_id": run.run_id,
                                "sender_type": "ASSISTANT",
                                "message_type": "CHAT",
                                "content": content_text,
                                "metadata": {
                                    "task_id": run.run_id,
                                    "status": status_val,
                                    "prompt": run.prompt,
                                    "exit_code": run.exit_code,
                                    "started_at": run.started_at.isoformat() if run.started_at else None,
                                    "ended_at": run.ended_at.isoformat() if run.ended_at else None
                                }
                            })
                            try:
                                from events import PlatformEvent
                                # Look for global event_bus if available
                                import backend.dependencies as bdep
                                if getattr(bdep, '_event_bus', None):
                                    bdep._event_bus.publish(PlatformEvent(
                                        event_id=f"evt_{datetime.now().timestamp()}",
                                        event_type="chat.message",
                                        agent_id=run.agent_id,
                                        task_id=run.run_id,
                                        payload={
                                            "id": assistant_msg["id"],
                                            "sender_type": "ASSISTANT",
                                            "content": content_text,
                                            "task_id": run.run_id,
                                            "metadata": assistant_msg.get("metadata"),
                                            "created_at": datetime.now().isoformat()
                                        },
                                        source="runtime"
                                    ))
                            except Exception:
                                pass
                    except Exception as chat_err:
                        logging.getLogger(__name__).warning(f"Failed to record task response to chat: {chat_err}")
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

    def resume_task(self, run_id: str, answer: str) -> str:
        """
        Resume an existing paused task (WAITING_INPUT) by passing the supervisor/human answer back into the session.
        """
        run = self._runs.get(run_id)
        if not run:
            try:
                from persistence import db_manager
                run = db_manager.get_task_run(run_id)
                if run:
                    self._runs[run_id] = run
            except Exception:
                pass

        if not run:
            raise ValueError(f"Task run {run_id} not found to resume")

        from config import config_manager
        agent_config = config_manager.get_agent(run.agent_id)
        if not agent_config:
            try:
                from persistence import db_manager
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