"""
Runtime adapter for Claude Code integration.
Handles launching and managing Claude Code subprocesses against a selectable
runtime provider (native CLI auth, Free Claude Code proxy, API key, or gateway).
"""

import subprocess
import os
import json
import time
import threading
import queue
from dataclasses import dataclass, asdict, field, replace
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from datetime import datetime
import re
import uuid
import logging
import tempfile
import signal
import sys
from collections import deque

# Import from local modules using absolute imports
from config import AgentConfig, ProjectConfig
import runtime_providers as providers

# Setting keys live on the provider registry; re-exported for existing callers.
RUNTIME_PROVIDER_SETTING_KEY = providers.SETTING_PROVIDER
RUNTIME_GATEWAY_URL_SETTING_KEY = providers.SETTING_GATEWAY_URL
RUNTIME_SETUP_COMPLETED_KEY = providers.SETTING_SETUP_COMPLETED

logger = logging.getLogger(__name__)

# Import runtime-agnostic domain models and re-export for backward compatibility
try:
    from runtime.models import TaskStatus, AgentRun
except ImportError:
    from poc.runtime.models import TaskStatus, AgentRun




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
        self.on_task_completed: Optional[Callable[[AgentRun], None]] = None
        self._authoring_lock = threading.Lock()

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

    def resolve_runtime_provider(self, agent_config: Optional[AgentConfig] = None) -> str:
        """
        Resolve which runtime provider a run should use.

        Precedence, most specific first:
          1. The agent's own `runtime_provider` override
          2. PLATFORM_RUNTIME_PROVIDER in the environment
          3. The default saved by the first-run setup prompt
          4. Native Claude Code CLI auth

        Detection is intentionally *not* part of this chain: a saved default must
        not flip because a proxy happened to be asleep. Detection only feeds the
        setup prompt's suggestion.
        """
        agent_choice = getattr(agent_config, "runtime_provider", None)
        if agent_choice and agent_choice.strip():
            return agent_choice.strip()

        env_choice = os.getenv("PLATFORM_RUNTIME_PROVIDER", "").strip()
        if env_choice:
            return env_choice

        try:
            from persistence import db_manager
            saved = db_manager.get_setting(RUNTIME_PROVIDER_SETTING_KEY)
            if saved and saved.strip():
                return saved.strip()
        except Exception as db_err:
            logging.getLogger(__name__).debug(f"Could not read saved runtime provider: {db_err}")

        return providers.PROVIDER_CLAUDE_CODE_NATIVE

    def _build_claude_env(
        self,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        agent_config: Optional[AgentConfig] = None,
    ) -> Dict[str, str]:
        """Build environment variables for Claude Code subprocess."""
        provider_id = self.resolve_runtime_provider(agent_config)

        gateway_url = None
        try:
            from persistence import db_manager
            gateway_url = db_manager.get_setting(RUNTIME_GATEWAY_URL_SETTING_KEY)
        except Exception:
            pass

        # build_provider_env strips inherited backend-steering vars before
        # applying the selected provider, so a stale ANTHROPIC_BASE_URL in the
        # platform's own shell cannot hijack a native-auth run.
        env = providers.build_provider_env(
            provider_id, os.environ.copy(), gateway_base_url=gateway_url
        )
        env["PLATFORM_RUNTIME_PROVIDER"] = provider_id
        env.update({
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": os.getenv("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "40000"),
            "DISABLE_AUTOUPDATER": "1",
            "DISABLE_FEEDBACK_COMMAND": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "DISABLE_TELEMETRY": "1",
            "TERM": "dumb",
            "PYTHONIOENCODING": "utf-8"
        })
        poc_dir = os.path.dirname(os.path.abspath(__file__))
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{poc_dir}:{existing_pythonpath}" if existing_pythonpath else poc_dir
        if run_id:
            env["PLATFORM_PARENT_TASK_ID"] = run_id
        if project_id:
            env["PLATFORM_PROJECT_ID"] = project_id
        return env

    def _resolve_working_directory(
        self,
        project_config: Optional[ProjectConfig],
        agent_config: Optional[AgentConfig]
    ) -> str:
        """Resolve a robust, cross-platform working directory, avoiding invalid macOS paths."""
        candidate = None
        if project_config and getattr(project_config, "working_directory", None) and project_config.working_directory.strip():
            candidate = project_config.working_directory.strip()
        elif agent_config and getattr(agent_config, "repo_path", None) and agent_config.repo_path.strip():
            candidate = agent_config.repo_path.strip()

        if candidate:
            # Detect invalid macOS/Unix paths on Windows
            if os.name == "nt" and (candidate.startswith("/Users/") or candidate.startswith("/home/")):
                local_poc_lms = os.path.abspath(os.path.join(os.path.dirname(__file__), "lms"))
                if os.path.exists(local_poc_lms):
                    return local_poc_lms
                return os.getcwd()
            try:
                abs_path = os.path.abspath(candidate)
                os.makedirs(abs_path, exist_ok=True)
                return abs_path
            except Exception:
                pass
        return os.getcwd()

    def _build_claude_command(
        self,
        agent_config: AgentConfig,
        project_config: Optional[ProjectConfig],
        prompt: str,
        session_id: Optional[str] = None,
        fork_session: bool = False,
        dangerously_skip_permissions: bool = False,
        playground: bool = False
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
        # Resolve logical model tier (e.g. tier:architect, tier:worker) to runtime model
        resolved_model = agent_config.model
        try:
            from runtime.model_policy import model_policy_resolver
            resolved_model = model_policy_resolver.resolve(agent_config.model, runtime_type="claude_code").resolved_model
        except Exception:
            pass

        if resolved_model and resolved_model.lower() != "default":
            cmd.extend(["--model", resolved_model.lower()])

        if playground:
            system_prompt = agent_config.system_prompt or ""
            if agent_config.skills:
                from skills_service import build_skills_system_prompt
                system_prompt += "\n" + (build_skills_system_prompt(agent_config.skills) or "")
            # Explicit tool inventory and MCP configuration; no inherited customization.
            cmd.extend([
                "-p", prompt, "--output-format", "stream-json", "--verbose",
                "--safe-mode", "--tools", "", "--strict-mcp-config",
                "--mcp-config", '{"mcpServers":{}}',
                "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
                "--permission-mode", "dontAsk", "--no-session-persistence",
                "--disable-slash-commands", "--no-chrome",
                "--system-prompt", system_prompt +
                "\nThis is an internal, tool-free workflow exercise. Use only supplied "
                "data. Report missing information explicitly; do not claim external actions occurred."
            ])
            return cmd

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
        target_dir = self._resolve_working_directory(project_config, agent_config)
        cmd.extend(["--add-dir", target_dir])

        # Pass agent system prompt with supervisor context, workspace, and equipped skills
        prompt_parts: List[str] = []
        if getattr(agent_config, "system_prompt", None) and agent_config.system_prompt.strip():
            prompt_parts.append(agent_config.system_prompt.strip())

        prompt_parts.append(
            f"[PROJECT WORKSPACE]\n"
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
            prompt_parts.append(
                f"[ORGANIZATION HIERARCHY & SUPERVISOR INSTRUCTIONS]\n"
                f"Your supervisor is {parent_name} (ID: {agent_config.parent_id}).\n"
                f"If you lack required information, parameters, or permissions, ask your supervisor directly by stating your question clearly or using AskUserQuestion.\n"
                f"State the question clearly so your supervisor can provide the answer or permission."
            )

        # Inject delegation mandate for managers and orchestrators
        allowed_children = getattr(agent_config, "allowed_child_ids", []) or []
        role_type = (getattr(agent_config, "role_type", "") or "").upper()
        if allowed_children or role_type in ("ROOT_ORCHESTRATOR", "MANAGER"):
            subordinates_info = []
            try:
                from persistence import db_manager
                for cid in allowed_children:
                    child_agent = db_manager.get_agent(cid)
                    if child_agent:
                        subordinates_info.append(f"- `{cid}` ({child_agent.name}): {child_agent.description or child_agent.department}")
                    else:
                        subordinates_info.append(f"- `{cid}`")
            except Exception:
                subordinates_info = [f"- `{cid}`" for cid in allowed_children]

            subordinates_text = "\n".join(subordinates_info) if subordinates_info else "(subordinates defined in organization hierarchy)"

            prompt_parts.append(
                f"[ORGANIZATION HIERARCHY & TASK DELEGATION MANDATE]\n"
                f"You are an Orchestrator/Manager agent ({agent_config.name}, Role: {role_type}).\n"
                f"CRITICAL INVARIANT: You DO NOT execute lower-tier worker tasks yourself (do not write frontend/backend code, test suites, or subordinate specs directly).\n"
                f"You MUST delegate work packages down the organizational hierarchy to your authorized subordinates:\n"
                f"{subordinates_text}\n\n"
                f"HOW TO DELEGATE IN THIS PLATFORM:\n"
                f"To dispatch a task to a subordinate agent, run this command using the Bash tool:\n"
                f"python -m orchestration.delegate --target-agent <agent_id> --prompt \"<detailed requirements, deliverables, and acceptance criteria>\"\n\n"
                f"CRITICAL TIMEOUT REQUIREMENT:\n"
                f"Always pass `timeout: 600000` (10 minutes) in your Bash tool call when running delegate commands so the system does not prematurely background your task while waiting for subordinates!\n"
                f"NOTE: The delegate command automatically WAITS for the subordinate agent to finish and outputs their completed deliverables to your terminal, allowing you to seamlessly verify their work and proceed to the next milestone in your turn!\n\n"
                f"CRITICAL EXECUTION MANDATE:\n"
                f"- You interact with this platform EXCLUSIVELY via standard tool calls (Write, Read, Edit, Bash, Grep, Glob).\n"
                f"- NEVER output XML pseudo-tags such as `<assistant to=...>` or simulated responses in markdown.\n"
                f"- When initiating a new project charter, first write PROJECT_PLAN.md using the Write tool.\n"
                f"- Then immediately dispatch your subordinate manager (e.g. `product-manager`) using the Bash tool with `python -m orchestration.delegate`.\n"
                f"- Inspect the output returned by the delegate command and proceed to coordinate subsequent steps."
            )

        # Inject equipped skills if configured
        agent_skills = getattr(agent_config, "skills", None)
        if agent_skills and len(agent_skills) > 0:
            try:
                from skills_service import build_skills_system_prompt
                skills_prompt = build_skills_system_prompt(agent_skills)
                if skills_prompt:
                    prompt_parts.append(skills_prompt)
            except Exception as e:
                logger.warning(f"Failed to inject equipped skills for agent {agent_config.id}: {e}")

        if prompt_parts:
            cmd.extend(["--system-prompt", "\n\n".join(prompt_parts)])

        # Enforce agent tool restrictions if configured
        if getattr(agent_config, "allowed_tools", None) and len(agent_config.allowed_tools) > 0:
            tool_mapping = {
                "read": ["Read", "View"], "view": ["Read", "View"],
                "write": ["Write", "Edit", "FileEdit"], "edit": ["Edit", "Write", "FileEdit"],
                "grep": ["Grep"], "glob": ["Glob"],
                "bash": ["Bash"], "Bash": ["Bash"],
                "delegate_task": ["Bash"],
                "ask_supervisor": ["AskUserQuestion"], "ask_manager": ["AskUserQuestion"],
                "ask_human": ["AskUserQuestion"], "AskUserQuestion": ["AskUserQuestion"]
            }
            mapped_tools = set()
            for t in agent_config.allowed_tools:
                if t in tool_mapping:
                    mapped = tool_mapping[t]
                    if isinstance(mapped, list):
                        mapped_tools.update(mapped)
                    else:
                        mapped_tools.add(mapped)
                else:
                    mapped_tools.add(t)
            if allowed_children or role_type in ("ROOT_ORCHESTRATOR", "MANAGER"):
                mapped_tools.add("Bash")
            cmd.extend(["--allowedTools", ",".join(sorted(mapped_tools))])

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

    @staticmethod
    def _stderr_reader(process, tail):
        """Drain stderr independently so a full pipe cannot block runtime exit."""
        if process.stderr is None:
            return
        for line in process.stderr:
            text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
            if text.strip():
                tail.append(text.strip()[-2000:])

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
                        event = self._parse_claude_output_line(line.decode('utf-8', errors='replace') if isinstance(line, bytes) else line)
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

    def _read_authoring_process(self, process, timeout_seconds, is_cancelled=None):
        """Consume real process output with bounded wait and no supervisor callbacks."""
        from runtime.protocol import AuthoringInferenceResult
        result = AuthoringInferenceResult()
        events = queue.Queue()
        stop = threading.Event()
        stderr_tail = deque(maxlen=10)
        reader = threading.Thread(target=self._output_reader,
            args=("authoring", process, events, stop), daemon=True)
        stderr_reader = threading.Thread(target=self._stderr_reader, args=(process, stderr_tail), daemon=True)
        reader.start(); stderr_reader.start()
        deadline = time.monotonic() + timeout_seconds
        last_check = 0.0
        try:
            while True:
                now = time.monotonic()
                if now >= deadline:
                    result.error_code, result.error_message = "MODEL_TIMEOUT", "The model did not respond before the time limit. Check the provider or choose another authoring model."
                    break
                if is_cancelled and now - last_check >= 1:
                    last_check = now
                    if is_cancelled():
                        result.error_code, result.error_message = "GENERATION_CANCELLED", "Generation stopped."
                        break
                try:
                    event = events.get(timeout=min(0.2, deadline - now))
                except queue.Empty:
                    if process.poll() is not None and not reader.is_alive() and events.empty():
                        result.error_code, result.error_message = "MODEL_PROCESS_FAILED", "The model process ended without a response. Check its provider configuration."
                        break
                    continue
                if event.get("type") == "result":
                    usage = event.get("usage") or {}
                    result.input_tokens = max(0, int(usage.get("input_tokens") or 0))
                    result.output_tokens = max(0, int(usage.get("output_tokens") or 0))
                    reported_cost = event.get("total_cost_usd", event.get("cost_usd"))
                    if reported_cost is not None:
                        import math
                        cost = float(reported_cost)
                        result.cost_usd = cost if math.isfinite(cost) and cost >= 0 else None
                    result.model = event.get("model") if isinstance(event.get("model"), str) else None
                    if event.get("is_error"):
                        result.error_code, result.error_message = "MODEL_REQUEST_FAILED", "The model rejected the request. Check the configured model provider."
                    else:
                        result.output = event.get("structured_output") or event.get("result")
                    break
                if event.get("type") in ("error", "end_of_output"):
                    result.error_code, result.error_message = "MODEL_PROCESS_FAILED", "The model process failed or returned no response. Check its provider configuration."
                    break
        finally:
            stop.set()
            if getattr(process, '_authoring_process_group', False):
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=3)
            reader.join(timeout=1); stderr_reader.join(timeout=1)
            if process.stdout: process.stdout.close()
            if process.stderr: process.stderr.close()
        return result

    def get_authoring_models(self):
        from runtime.models import MODEL_CATALOG
        provider_id = self.resolve_runtime_provider()
        models = [{"id": "default", "name": "Runtime default"},
                  {"id": "sonnet", "name": "Sonnet"},
                  {"id": "opus", "name": "Opus"},
                  {"id": "haiku", "name": "Haiku"}]
        # Other vendor models require a configured Anthropic-compatible gateway.
        models += [{"id": item["id"], "name": item["name"]} for item in MODEL_CATALOG
                   if provider_id in (providers.PROVIDER_CUSTOM_GATEWAY, providers.PROVIDER_FREE_CLAUDE_CODE)
                   or item["provider"] == "Anthropic"]
        return [{"model_id": item["id"], "name": item["name"], "provider_id": provider_id}
                for item in models]

    def infer_authoring(self, selection, prompt, system_prompt, response_schema,
                        timeout_seconds=120, max_budget_usd=None, is_cancelled=None, authoring_context=None):
        from runtime.protocol import AuthoringInferenceResult
        if not any(item["model_id"] == selection.model_id and item["provider_id"] == selection.provider_id
                   for item in self.get_authoring_models()):
            return AuthoringInferenceResult(error_code="AUTHORING_MODEL_NOT_ALLOWED",
                error_message="Select a model from the current configured provider.")
        # Ephemeral runtime configuration only: no selected/persisted agent and no inherited authority.
        profile = AgentConfig(id="workflow-authoring", name="Workflow authoring", description="Model-only planning",
            model=selection.model_id, runtime_provider=selection.provider_id, system_prompt=system_prompt,
            skills=[], parent_id=None, allowed_child_ids=[], dangerously_skip_permissions=False)
        process_key = "authoring_" + uuid.uuid4().hex
        cost_source = "ESTIMATED"
        try:
            provider_id = self.resolve_runtime_provider(profile)
            cost_source = "API_KEY" if provider_id in (providers.PROVIDER_ANTHROPIC_API, providers.PROVIDER_CUSTOM_GATEWAY) else "SUBSCRIPTION_CLI"
            command = self._build_claude_command(profile, None, prompt, playground=True)
            command.extend(["--json-schema", json.dumps(response_schema)])
            if max_budget_usd is not None and cost_source == "API_KEY":
                command.extend(["--max-budget-usd", str(max_budget_usd)])
            env = self._build_claude_env(agent_config=profile)
            with tempfile.TemporaryDirectory(prefix="workflow_authoring_") as workspace:
                if authoring_context is not None:
                    env.pop('CLAUDE_CODE_SAFE_MODE', None)
                    context_path = os.path.join(workspace, 'authoring-context.json')
                    with open(context_path, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as context_file:
                        json.dump(authoring_context, context_file)
                    command.remove('--safe-mode')  # safe-mode suppresses explicit MCP servers too.
                    command.append('--restricted')
                    config = {"mcpServers": {"workflow_authoring": {"command": sys.executable,
                        "args": ["-m", "backend.workflow_assistant.mcp_server", "--context", context_path]}}}
                    command[command.index('--mcp-config') + 1] = json.dumps(config)
                    command.extend(['--allowedTools', ','.join('mcp__workflow_authoring__' + name for name in
                        ('workflow_catalog', 'workflow_schema', 'validate_workflow_yaml'))])
                with self._authoring_lock:
                    if sum(1 for item in self._processes.values() if item.poll() is None) >= self.max_concurrent_runs:
                        return AuthoringInferenceResult(error_code="RUNTIME_BUSY", error_message="The runtime is busy. Try again shortly.")
                    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, errors="replace", cwd=workspace, env=env,
                        start_new_session=(os.name == "posix"))
                    process._authoring_process_group = os.name == "posix"
                    self._processes[process_key] = process
                result = self._read_authoring_process(process, timeout_seconds, is_cancelled)
                result.cost_source = cost_source
                result.model = result.model or profile.model
                return result
        except Exception:
            logger.exception("Workflow authoring inference failed")
            return AuthoringInferenceResult(cost_source=cost_source, model=profile.model,
                error_code="MODEL_RUNTIME_ERROR", error_message="Unable to start or read the model response. Check runtime configuration.")
        finally:
            process = self._processes.pop(process_key, None)
            if process and getattr(process, '_authoring_process_group', False):
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            if process and process.poll() is None:
                process.kill(); process.wait(timeout=3)

    def start_playground_task(self, agent_id: str, task_id: str, prompt: str, workspace: str) -> str:
        """Run fresh inference without tools, external escalation, or completion callbacks."""
        if not task_id.startswith("pg_task_"):
            raise ValueError("Playground tasks require a pg_task_ ID")
        from persistence import db_manager
        agent = db_manager.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        active = sum(1 for process in self._processes.values() if process.poll() is None)
        if active >= self.max_concurrent_runs:
            raise RuntimeError("Platform concurrency limit reached")
        run = db_manager.get_task_run(task_id)
        if not run:
            raise ValueError("Playground task record not found")
        self._runs[task_id] = run
        thread = threading.Thread(
            target=self._execute_task,
            args=(task_id, agent, None, prompt, None, False),
            kwargs={"playground_workspace": workspace}, daemon=True
        )
        thread.start()
        return task_id

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
        if (task_id and task_id.startswith("pg_task_")) or agent_id.startswith("pg_task_"):
            raise ValueError("Use a fresh playground run for playground tasks")
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
        dangerously_skip_permissions: bool = False,
        playground_workspace: Optional[str] = None
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
        stderr_tail = deque(maxlen=30)
        stderr_thread = None

        try:
            # Update status to running
            run.status = TaskStatus.RUNNING
            run.started_at = datetime.now()
            try:
                from persistence import db_manager
                db_manager.save_task_run(run)
            except Exception:
                pass

            # Determine model and cost source
            resolved_model = getattr(agent_config, "model", None)
            try:
                from runtime.model_policy import model_policy_resolver
                resolved_model = model_policy_resolver.resolve(agent_config.model, runtime_type="claude_code").resolved_model
            except Exception:
                pass
            run.model = resolved_model

            # Determine provider cost source
            chosen_prov_id = self.resolve_runtime_provider(agent_config)
            if chosen_prov_id in (providers.PROVIDER_ANTHROPIC_API, providers.PROVIDER_CUSTOM_GATEWAY):
                run.cost_source = "API_KEY"
            elif chosen_prov_id in (providers.PROVIDER_CLAUDE_CODE_NATIVE, providers.PROVIDER_FREE_CLAUDE_CODE):
                run.cost_source = "SUBSCRIPTION_CLI"
            else:
                run.cost_source = "ESTIMATED"

            # Build command and environment
            skip_perm = dangerously_skip_permissions or getattr(run, "dangerously_skip_permissions", False)
            cmd = self._build_claude_command(
                agent_config, project_config, prompt, session_id, fork_session,
                dangerously_skip_permissions=skip_perm,
                playground=playground_workspace is not None
            )
            env = self._build_claude_env(
                run_id=run_id,
                project_id=getattr(run, "project_id", None),
                agent_config=agent_config,
            )

            # Determine working directory
            work_dir = playground_workspace or self._resolve_working_directory(project_config, agent_config)

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
            stderr_thread = threading.Thread(target=self._stderr_reader,
                args=(process, stderr_tail), daemon=True)
            stderr_thread.start()

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
            last_checkpoint = time.monotonic()
            while True:
                try:
                    # Get event with timeout to allow checking for cancellation
                    event = event_queue.get(timeout=0.1)

                    # Add event to run
                    run.events.append(event)
                    if playground_workspace and time.monotonic() - last_checkpoint >= 1:
                        from persistence import db_manager
                        db_manager.save_task_run(run)
                        last_checkpoint = time.monotonic()

                    # Capture Claude session ID if emitted
                    captured_sid = None
                    if event.get("session_id"):
                        captured_sid = event["session_id"]
                    elif event.get("data", {}).get("session_id"):
                        captured_sid = event["data"]["session_id"]
                    elif event.get("type") == "result" and event.get("session_id"):
                        captured_sid = event["session_id"]

                    if captured_sid and not playground_workspace:
                        run.session_id = captured_sid
                        try:
                            from persistence import db_manager
                            with db_manager._get_connection() as conn:
                                conn.execute("""
                                    UPDATE agent_conversations
                                    SET claude_session_id = ?, runtime_session_id = ?, updated_at = ?
                                    WHERE agent_id = ? AND (task_id = ? OR status = 'ACTIVE')
                                """, (captured_sid, captured_sid, datetime.now().isoformat(), run.agent_id, run.run_id))
                                conn.commit()
                        except Exception:
                            pass

                    # Check for explicit tool call for supervisor clarification or permission
                    tool_q = extract_supervisor_question(event)
                    if tool_q and playground_workspace and event.get("type") != "result":
                        run.status = TaskStatus.FAILED
                        run.error = tool_q["question"]
                        break
                    if tool_q and not playground_workspace:
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

                        # Extract token usage and cost metrics emitted by Claude Code
                        usage_dict = event.get("usage") or event.get("data", {}).get("usage") or {}
                        if isinstance(usage_dict, dict):
                            run.input_tokens = usage_dict.get("input_tokens", 0) or run.input_tokens
                            run.output_tokens = usage_dict.get("output_tokens", 0) or run.output_tokens
                            run.cache_read_tokens = usage_dict.get("cache_read_input_tokens", 0) or usage_dict.get("cache_read_tokens", 0) or run.cache_read_tokens
                            run.cache_write_tokens = usage_dict.get("cache_creation_input_tokens", 0) or usage_dict.get("cache_write_tokens", 0) or run.cache_write_tokens

                        reported_cost = event.get("total_cost_usd") or event.get("cost_usd") or event.get("data", {}).get("total_cost_usd")
                        if reported_cost is not None:
                            try:
                                run.cost_usd = float(reported_cost)
                            except Exception:
                                pass

                        model_reported = event.get("model") or event.get("data", {}).get("model")
                        if model_reported:
                            run.model = str(model_reported)

                        q_data = extract_supervisor_question(event) or extract_supervisor_question(res_val)
                        if q_data and playground_workspace:
                            run.status = TaskStatus.FAILED
                            run.error = q_data["question"]
                            break
                        if event.get("is_error"):
                            run.status = TaskStatus.FAILED
                            run.error = str(res_val)
                            break
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
                            if stderr_thread:
                                stderr_thread.join(timeout=0.2)
                            diagnostic = "\n".join(stderr_tail)
                            run.error = diagnostic or f"Process ended without result (exit code {process.poll()})"
                        break

                except queue.Empty:
                    # Check if process has ended
                    if process.poll() is not None:
                        # Process ended, check if we got all output
                        reader_thread.join(timeout=0.1)
                        if reader_thread.is_alive() or not event_queue.empty():
                            continue
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
            if stderr_thread:
                stderr_thread.join(timeout=0.2)
            if stderr_tail:
                run.events.append({"type": "stderr", "content": "\n".join(stderr_tail),
                                   "_timestamp": time.time(), "_run_id": run_id})
                if run.status == TaskStatus.FAILED:
                    run.error = (run.error or "Runtime failed") + "\n" + "\n".join(stderr_tail)
            # Clean up: only mark ended_at for terminal statuses (not paused WAITING_INPUT)
            if run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                run.ended_at = datetime.now()
            else:
                run.ended_at = None
            try:
                from persistence import db_manager
                db_manager.save_task_run(run)

                # Record task response in chat_messages for the agent
                if not playground_workspace and run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.WAITING_INPUT) and run.agent_id:
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
                        logger.warning(f"Failed to record task response to chat: {chat_err}")
            except Exception as dbe:
                logger.warning(f"Failed to save task run to DB: {dbe}")

            # Notify Orchestration Engine of task completion or failure
            if not playground_workspace and run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                if getattr(self, "on_task_completed", None):
                    try:
                        self.on_task_completed(run)
                    except Exception as cb_err:
                        logger.error(f"Error in on_task_completed for {run.run_id}: {cb_err}")
                else:
                    try:
                        import backend.dependencies as bdep
                        engine = bdep.get_orchestration_engine()
                        if engine:
                            engine.handle_task_completion(run)
                    except Exception:
                        pass

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
        if run_id.startswith("pg_task_"):
            raise ValueError("Playground tasks cannot be resumed; start a fresh playground run")

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
        run.error = "Task cancelled"

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