"""Subprocess execution and result-state interpretation behind the runtime facade."""

import logging
import queue
import subprocess
import threading
import time
from datetime import datetime
from collections import deque
from typing import Optional
from config import AgentConfig, ProjectConfig
import runtime_providers as providers
from .models import AgentRun, TaskStatus
from .questions import extract_supervisor_question
from .finalization import finalize_run

logger = logging.getLogger(__name__)


class TaskExecutor:
    def __init__(self, adapter):
        self.adapter = adapter

    def _handle_question(self, run: AgentRun, question):
        resolver = self.adapter.services.supervisor
        resolution = {"status": "PENDING_INPUT", "target_approver": "HUMAN_OPERATOR"}
        if resolver:
            try:
                resolution = resolver(
                    task_id=run.run_id,
                    requester_agent_id=run.agent_id,
                    question=question["question"],
                    project_id=run.project_id,
                    context=question.get("context"),
                    suggested_options=question.get("suggested_options"),
                )
            except Exception as error:
                # Optional escalation failure must retain the resumable question.
                logger.warning(
                    "Supervisor resolution unavailable for %s (%s)",
                    run.run_id, type(error).__name__,
                )
        if resolution.get("status") == "AUTO_RESOLVED":
            run.status = TaskStatus.RUNNING
        else:
            run.status = TaskStatus.WAITING_INPUT
            run.result = (
                f"Waiting for {resolution.get('target_approver', 'supervisor')} "
                f"response: {question['question']}"
            )

    def execute(self, run_id, agent_config, project_config, prompt, session_id,
                fork_session, dangerously_skip_permissions=False, playground_workspace=None):
        # A resumed attempt cannot race the previous attempt's cleanup.
        lock = self.adapter._run_locks.setdefault(run_id, threading.RLock())
        with lock:
            return self._execute_locked(run_id, agent_config, project_config, prompt,
                                        session_id, fork_session, dangerously_skip_permissions, playground_workspace)

    def _execute_locked(
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
        adapter = self.adapter
        run = adapter._runs[run_id]
        stderr_tail = deque(maxlen=30)
        stderr_thread = None

        try:
            if adapter._shutting_down or run.status == TaskStatus.CANCELLED:
                run.status = TaskStatus.CANCELLED
                return
            # Update status to running
            run.status = TaskStatus.RUNNING
            run.started_at = datetime.now()
            try:
                db_manager = adapter.services.database()
                db_manager.save_task_run(run)
            except Exception:
                pass

            # Determine model and cost source
            resolved_model = getattr(agent_config, "model", None)
            try:
                resolved_model = adapter.services.resolve_model(agent_config.model)
            except Exception:
                pass
            run.model = resolved_model

            # Determine provider cost source
            chosen_prov_id = adapter.resolve_runtime_provider(agent_config)
            if chosen_prov_id in (providers.PROVIDER_ANTHROPIC_API, providers.PROVIDER_CUSTOM_GATEWAY):
                run.cost_source = "API_KEY"
            elif chosen_prov_id in (providers.PROVIDER_CLAUDE_CODE_NATIVE, providers.PROVIDER_FREE_CLAUDE_CODE):
                run.cost_source = "SUBSCRIPTION_CLI"
            else:
                run.cost_source = "ESTIMATED"

            # Build command and environment
            skip_perm = dangerously_skip_permissions or getattr(run, "dangerously_skip_permissions", False)
            cmd = adapter._build_claude_command(
                agent_config, project_config, prompt, session_id, fork_session,
                dangerously_skip_permissions=skip_perm,
                playground=playground_workspace is not None
            )
            env = adapter._build_claude_env(
                run_id=run_id,
                project_id=getattr(run, "project_id", None),
                agent_config=agent_config,
            )

            # Determine working directory
            work_dir = playground_workspace or adapter._resolve_working_directory(project_config, agent_config)

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

            adapter._processes[run_id] = process
            # Drain stderr separately so a full pipe cannot deadlock inference.
            stderr_thread = threading.Thread(target=adapter._stderr_reader, args=(process, stderr_tail), daemon=True)
            adapter._stderr_threads[run_id] = stderr_thread
            stderr_thread.start()

            # Set up output reading
            event_queue = queue.Queue()
            stop_event = threading.Event()
            adapter._event_queues[run_id] = event_queue
            adapter._stop_events[run_id] = stop_event

            reader_thread = threading.Thread(
                target=adapter._output_reader,
                args=(run_id, process, event_queue, stop_event)
            )
            reader_thread.daemon = True
            reader_thread.start()
            adapter._reader_threads[run_id] = reader_thread

            # Process events
            last_checkpoint = time.monotonic()
            while True:
                try:
                    # Get event with timeout to allow checking for cancellation
                    event = event_queue.get(timeout=0.1)

                    # Add event to run
                    run.events.append(event)
                    adapter._subscriptions.publish(run_id, event)
                    if playground_workspace and time.monotonic() - last_checkpoint >= 1:
                        adapter.services.database().save_task_run(run)
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
                            adapter.services.capture_session(run, captured_sid)
                        except Exception:
                            pass

                    # Check for explicit tool call for supervisor clarification or permission
                    tool_q = extract_supervisor_question(event)
                    if tool_q and playground_workspace and event.get("type") != "result":
                        run.status = TaskStatus.FAILED
                        run.error = tool_q["question"]
                        break
                    if tool_q and not playground_workspace:
                        self._handle_question(run, tool_q)
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
                        if q_data:
                            self._handle_question(run, q_data)
                            break
                        else:
                            run.result = res_val
                            if event.get("is_error"):
                                run.error = str(res_val or "Runtime reported an execution error")
                                run.status = TaskStatus.FAILED
                            else:
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
                        # The reader owns the end marker; allow it to drain final output.
                        if reader_thread.is_alive() or not event_queue.empty():
                            continue
                        run.exit_code = process.poll()
                        if not adapter._stop_events[run_id].is_set():
                            # Process ended unexpectedly
                            run.status = TaskStatus.FAILED
                            run.error = f"Process exited with code {process.poll()}"
                        break
                    elif adapter._stop_events[run_id].is_set():
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
            finalize_run(adapter, run, playground=playground_workspace is not None)
