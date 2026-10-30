"""Model-only authoring inference and bounded stdio process lifecycle."""
import json
import logging
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from config import AgentConfig
import runtime_providers as providers

logger = logging.getLogger(__name__)


def _read_authoring_process(adapter, process, timeout_seconds, is_cancelled=None):
    """Consume real process output with bounded wait and no supervisor callbacks."""
    from runtime.protocol import AuthoringInferenceResult
    result = AuthoringInferenceResult()
    events = queue.Queue()
    stop = threading.Event()
    stderr_tail = deque(maxlen=10)
    reader = threading.Thread(target=adapter._output_reader,
        args=("authoring", process, events, stop), daemon=True)
    stderr_reader = threading.Thread(target=adapter._stderr_reader, args=(process, stderr_tail), daemon=True)
    reader.start()
    stderr_reader.start()
    deadline = time.monotonic() + timeout_seconds
    last_check = 0.0
    try:
        while True:
            if adapter._shutting_down:
                result.error_code, result.error_message = "GENERATION_CANCELLED", "Runtime is shutting down."
                break
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
                process.kill()
                process.wait(timeout=3)
        reader.join(timeout=1)
        stderr_reader.join(timeout=1)
        if process.stdout: process.stdout.close()
        if process.stderr: process.stderr.close()
    return result


def get_authoring_models(adapter):
    from runtime.models import MODEL_CATALOG
    provider_id = adapter.resolve_runtime_provider()
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


def infer_authoring(adapter, selection, prompt, system_prompt, response_schema,
                    timeout_seconds=120, max_budget_usd=None, is_cancelled=None, authoring_context=None):
    from runtime.protocol import AuthoringInferenceResult
    if adapter._shutting_down:
        return AuthoringInferenceResult(error_code="GENERATION_CANCELLED", error_message="Runtime is shutting down.")
    if not any(item["model_id"] == selection.model_id and item["provider_id"] == selection.provider_id
               for item in adapter.get_authoring_models()):
        return AuthoringInferenceResult(error_code="AUTHORING_MODEL_NOT_ALLOWED",
            error_message="Select a model from the current configured provider.")
    # Ephemeral runtime configuration only: no selected/persisted agent and no inherited authority.
    profile = AgentConfig(id="workflow-authoring", name="Workflow authoring", description="Model-only planning",
        model=selection.model_id, runtime_provider=selection.provider_id, system_prompt=system_prompt,
        skills=[], parent_id=None, allowed_child_ids=[], dangerously_skip_permissions=False)
    process_key = "authoring_" + uuid.uuid4().hex
    cost_source = "ESTIMATED"
    try:
        provider_id = adapter.resolve_runtime_provider(profile)
        cost_source = "API_KEY" if provider_id in (providers.PROVIDER_ANTHROPIC_API, providers.PROVIDER_CUSTOM_GATEWAY) else "SUBSCRIPTION_CLI"
        command = adapter._build_claude_command(profile, None, prompt, playground=True)
        command.extend(["--json-schema", json.dumps(response_schema)])
        if max_budget_usd is not None and cost_source == "API_KEY":
            command.extend(["--max-budget-usd", str(max_budget_usd)])
        env = adapter._build_claude_env(agent_config=profile)
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
            with adapter._authoring_lock:
                if adapter._shutting_down:
                    return AuthoringInferenceResult(
                        error_code="GENERATION_CANCELLED", error_message="Runtime is shutting down.")
                if sum(1 for item in adapter._processes.values() if item.poll() is None) >= adapter.max_concurrent_runs:
                    return AuthoringInferenceResult(error_code="RUNTIME_BUSY", error_message="The runtime is busy. Try again shortly.")
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, errors="replace", cwd=workspace, env=env,
                    start_new_session=(os.name == "posix"))
                process._authoring_process_group = os.name == "posix"
                adapter._processes[process_key] = process
            result = adapter._read_authoring_process(process, timeout_seconds, is_cancelled)
            result.cost_source = cost_source
            result.model = result.model or profile.model
            return result
    except Exception:
        logger.exception("Workflow authoring inference failed")
        return AuthoringInferenceResult(cost_source=cost_source, model=profile.model,
            error_code="MODEL_RUNTIME_ERROR", error_message="Unable to start or read the model response. Check runtime configuration.")
    finally:
        process = adapter._processes.pop(process_key, None)
        if process and getattr(process, '_authoring_process_group', False):
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=3)


