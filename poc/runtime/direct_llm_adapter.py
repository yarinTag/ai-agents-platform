"""
Direct HTTP Multi-Provider LLM Runtime Adapter (Anthropic, OpenAI, NVIDIA NIM).

Enforces zero-trust control plane guarantees on every inference and tool step:
1. Pre-inference token validation, department `HARD_STOP` budget check, and PII redaction via `LLMProxy`.
2. Tenant-isolated BYOK API key resolution via `LLMKeysRepositoryMixin` (with env var fallback).
3. Real-time interception of every model-requested tool call via `RuntimeToolGateway` before execution.
4. Provider endpoint validation (https / no internal hosts in production) before the API key is sent.
5. Mid-run budget re-check using the *actual* per-model token cost before every follow-up round.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

try:
    from gateways.llm_proxy import LLMProxy, llm_proxy
    from gateways.tool_gateway import RuntimeToolGateway, tool_gateway
    from persistence_modules.llm_keys_repo import (
        DEFAULT_PROVIDER_BASE_URLS, DEFAULT_PROVIDER_MODELS, LLMKeysRepositoryMixin,
        SUPPORTED_LLM_PROVIDERS, validate_provider_base_url,
    )
    from runtime.llm_wire import compute_cost_usd, format_tools, parse_tool_arguments, parse_tool_identity
except ImportError:
    from poc.gateways.llm_proxy import LLMProxy, llm_proxy
    from poc.gateways.tool_gateway import RuntimeToolGateway, tool_gateway
    from poc.persistence_modules.llm_keys_repo import (
        DEFAULT_PROVIDER_BASE_URLS, DEFAULT_PROVIDER_MODELS, LLMKeysRepositoryMixin,
        SUPPORTED_LLM_PROVIDERS, validate_provider_base_url,
    )
    from poc.runtime.llm_wire import compute_cost_usd, format_tools, parse_tool_arguments, parse_tool_identity

HttpTransportFn = Callable[[str, str, Dict[str, str], Dict[str, Any]], Dict[str, Any]]
ToolExecutorFn = Callable[[str, str, Dict[str, Any]], Any]
DEFAULT_MAX_TOKENS = 1024


def default_http_transport(
    method: str, url: str, headers: Dict[str, str], payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Perform an outbound JSON HTTP request using Python's standard library `urllib.request`."""
    http_method = method.upper() if method.upper() in ("POST", "GET", "PUT", "DELETE") else "POST"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method=http_method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        raise RuntimeError(f"Upstream LLM HTTP {exc.code} from {url}: {err_body}") from exc


class DirectHTTPLLMRuntimeAdapter:
    """Direct HTTP runtime adapter supporting Anthropic Messages and OpenAI/NVIDIA Chat Completions."""

    def __init__(
        self,
        http_transport: Optional[HttpTransportFn] = None,
        tool_executor: Optional[ToolExecutorFn] = None,
        llm_proxy_instance: Optional[LLMProxy] = None,
        tool_gateway_instance: Optional[RuntimeToolGateway] = None,
    ) -> None:
        self.http_transport: HttpTransportFn = http_transport or default_http_transport
        self.tool_executor: Optional[ToolExecutorFn] = tool_executor
        self.llm_proxy: LLMProxy = llm_proxy_instance or llm_proxy
        self.tool_gateway: RuntimeToolGateway = tool_gateway_instance or tool_gateway

    @staticmethod
    def _resolve_credentials(db: Any, org_id: str, provider: str, department_id: Optional[str]) -> Dict[str, Any]:
        """Resolve provider API key and endpoint via DB mixin or fallback."""
        if hasattr(db, "resolve_org_llm_api_key"):
            return db.resolve_org_llm_api_key(org_id, provider, department_id)
        if db is not None and hasattr(db, "_get_connection"):
            return LLMKeysRepositoryMixin.resolve_org_llm_api_key(db, org_id, provider, department_id)
        raise PermissionError("Fail-closed: Database instance does not support LLM key resolution")

    def _intercept_and_run_tool(
        self, db: Any, run_token: str, call_id: str, conn_id: str, tool_name: str,
        raw_args: Dict[str, Any], args_error: Optional[str], executed_calls: List[Dict[str, Any]],
    ) -> str:
        """Gate a tool call via `RuntimeToolGateway`; recoverable problems become an error result for the model.

        Gateway denials (`PermissionError`) always propagate: policy violations must stop the run.
        """
        if args_error:
            return json.dumps({"error": args_error})
        gate = self.tool_gateway.intercept_tool_call(
            db=db, run_token=run_token, connector_id=conn_id, tool_name=tool_name, arguments=raw_args
        )
        if self.tool_executor is None:  # never fabricate a success the platform did not perform
            return json.dumps({"error": f"tool '{conn_id}.{tool_name}' cannot be executed in this runtime"})
        clean_args = gate["sanitized_arguments"]
        out = self.tool_executor(conn_id, tool_name, clean_args)
        executed_calls.append(
            {"id": call_id, "connector_id": conn_id, "tool_name": tool_name, "arguments": clean_args, "output": out}
        )
        return out if isinstance(out, str) else json.dumps(out)

    def _enforce_midrun_budget(self, db: Any, department_id: str, spent_usd: float) -> None:
        """Fail closed if the department cannot afford the actual spend accumulated so far."""
        status = db.check_department_budget(department_id, requested_cost=float(spent_usd))
        if not status.get("allowed", False):
            raise PermissionError(f"Fail-closed: department budget exhausted mid-run ({status.get('message', '')})")

    def execute_with_tools(
        self, db: Any, run_token: str, provider: str, model: str, system_prompt: str,
        user_prompt: str, tools: Optional[List[Dict[str, Any]]] = None,
        max_tool_rounds: int = 3, estimated_cost_usd: float = 0.01,
    ) -> Dict[str, Any]:
        """Execute a multi-turn LLM completion with native tool calling across Anthropic, OpenAI, or NVIDIA NIM."""
        norm_provider = (provider or "").strip().lower()
        if norm_provider not in SUPPORTED_LLM_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider '{provider}'. Must be in {SUPPORTED_LLM_PROVIDERS}")

        effective_model = (model or "").strip() or DEFAULT_PROVIDER_MODELS[norm_provider]
        auth_res = self.llm_proxy.authorize_and_meter_llm_call(
            db=db, run_token=run_token, model=effective_model,
            prompt_text=user_prompt, estimated_cost_usd=estimated_cost_usd, redact_pii=True,
        )
        sanitized_user = auth_res["sanitized_prompt"]
        sanitized_system, _ = self.llm_proxy.redact_pii_and_secrets(system_prompt or "")

        cred = self._resolve_credentials(db, auth_res["org_id"], norm_provider, auth_res["department_id"])
        api_key = cred["api_key"]
        url = validate_provider_base_url(cred.get("base_url") or DEFAULT_PROVIDER_BASE_URLS[norm_provider])
        formatted_tools, tool_map = format_tools(norm_provider, tools)

        executed_calls: List[Dict[str, Any]] = []
        in_tok, out_tok, final_text = 0, 0, ""

        if norm_provider == "anthropic":
            headers = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
            messages: List[Dict[str, Any]] = [{"role": "user", "content": sanitized_user}]
        else:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            messages = [{"role": "system", "content": sanitized_system}] if sanitized_system else []
            messages.append({"role": "user", "content": sanitized_user})

        for _round in range(max(1, max_tool_rounds + 1)):
            if _round > 0:
                self._enforce_midrun_budget(db, auth_res["department_id"], compute_cost_usd(effective_model, in_tok, out_tok))
            payload: Dict[str, Any] = {"model": effective_model, "max_tokens": DEFAULT_MAX_TOKENS, "messages": messages}
            if norm_provider == "anthropic":
                payload["system"] = sanitized_system
            if formatted_tools:
                payload["tools"] = formatted_tools

            resp = self.http_transport("POST", url, headers, payload)
            usage = resp.get("usage") or {}
            in_tok += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            out_tok += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)

            if norm_provider == "anthropic":
                blocks = resp.get("content") or []
                text_parts = [str(b.get("text", "")) for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
                tool_uses = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"]
                if text_parts:
                    final_text = "\n".join(t for t in text_parts if t)
                if not tool_uses or _round >= max_tool_rounds:
                    break
                messages.append({"role": "assistant", "content": blocks})
                tool_results: List[Dict[str, Any]] = []
                for tu in tool_uses:
                    call_id = str(tu.get("id") or f"toolu_{len(executed_calls) + 1}")
                    conn_id, t_name = parse_tool_identity(tu, str(tu.get("name") or ""), tool_map)
                    raw_args, args_err = parse_tool_arguments(tu.get("input"))
                    serialized = self._intercept_and_run_tool(db, run_token, call_id, conn_id, t_name, raw_args, args_err, executed_calls)
                    tool_results.append({"type": "tool_result", "tool_use_id": call_id, "content": serialized})
                messages.append({"role": "user", "content": tool_results})
            else:
                choices = resp.get("choices") or [{}]
                msg = (choices[0] if choices else {}).get("message") or {}
                if msg.get("content"):
                    final_text = str(msg["content"])
                t_calls = msg.get("tool_calls") or []
                if not t_calls or _round >= max_tool_rounds:
                    break
                messages.append(msg)
                for tc in t_calls:
                    call_id = str(tc.get("id") or f"call_{len(executed_calls) + 1}")
                    fn_obj = tc.get("function") or {}
                    conn_id, t_name = parse_tool_identity(tc, str(fn_obj.get("name") or ""), tool_map)
                    raw_args, args_err = parse_tool_arguments(fn_obj.get("arguments"))
                    serialized = self._intercept_and_run_tool(db, run_token, call_id, conn_id, t_name, raw_args, args_err, executed_calls)
                    messages.append({"role": "tool", "tool_call_id": call_id, "content": serialized})

        actual_cost = compute_cost_usd(effective_model, in_tok, out_tok)
        cost_usd = actual_cost if (in_tok or out_tok) else round(float(estimated_cost_usd), 6)
        return {
            "provider": norm_provider, "model": effective_model, "output_text": final_text,
            "tool_calls_executed": executed_calls, "input_tokens": in_tok, "output_tokens": out_tok, "cost_usd": cost_usd,
        }

    execute_step = execute_with_tools
