"""
Zero-Trust LLM Inference Proxy, Real-Time Budget Enforcer, and PII Redactor.

Enforces:
1. Cryptographic `ScopedRunToken` validation via `SecretsBroker`.
2. Model allowlist and prompt character ceiling before any upstream inference request.
3. Real-time department `HARD_STOP` budget enforcement (`db.check_department_budget`) BEFORE every LLM call.
4. Automated PII & secret token redaction (emails, API keys, PATs) when `redact_pii=True`.
5. Append-only security audit logging with SHA-256 `params_hash`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from gateways.secrets_broker import SecretsBroker, ScopedRunToken, secrets_broker
    from persistence_modules.postgres_rls import compute_params_hash, record_security_audit_event
except ImportError:
    from poc.gateways.secrets_broker import SecretsBroker, ScopedRunToken, secrets_broker
    from poc.persistence_modules.postgres_rls import compute_params_hash, record_security_audit_event

DEFAULT_MAX_PROMPT_CHARS: int = 100_000

DEFAULT_ALLOWED_MODELS: Set[str] = {
    "default",
    "sonnet",
    "opus",
    "haiku",
    "claude-3-5-sonnet",
    "claude-3-5-sonnet-latest",
    "claude-3-7-sonnet",
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-3-haiku",
    "gpt-4o",
    "gpt-4o-mini",
    "tier:executive",
    "tier:architect",
    "tier:worker",
}

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SECRET_TOKEN_PATTERN = re.compile(
    r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|rtk_[A-Za-z0-9_-]{16,})\b"
)


class LLMProxy:
    """
    Intercepts, authorizes, sanitizes, and meters every LLM call from agent sandboxes.
    """

    def __init__(
        self,
        secrets_broker_instance: Optional[SecretsBroker] = None,
        allowed_models: Optional[Set[str]] = None,
        max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    ) -> None:
        self.secrets_broker: SecretsBroker = secrets_broker_instance or secrets_broker
        self.allowed_models: Set[str] = (
            {m.lower() for m in allowed_models}
            if allowed_models is not None
            else set(DEFAULT_ALLOWED_MODELS)
        )
        self.max_prompt_chars: int = max_prompt_chars
        self.call_log: List[Dict[str, Any]] = []

    @staticmethod
    def redact_pii_and_secrets(text: str) -> Tuple[str, int]:
        """
        Redact email addresses and credential tokens from `text`.
        Returns `(sanitized_text, total_redactions)`.
        """
        if not text:
            return "", 0
        redactions = 0

        def _replace_email(_match: re.Match[str]) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_EMAIL]"

        def _replace_token(_match: re.Match[str]) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_TOKEN]"

        sanitized = EMAIL_PATTERN.sub(_replace_email, text)
        sanitized = SECRET_TOKEN_PATTERN.sub(_replace_token, sanitized)
        return sanitized, redactions

    def _audit(
        self,
        db: Any,
        scoped: Optional[ScopedRunToken],
        model: str,
        estimated_cost_usd: float,
        prompt_length: int,
        decision: str,
        reason: str,
        redaction_count: int = 0,
    ) -> Dict[str, Any]:
        """Record an append-only audit entry for an LLM authorization check."""
        org_id = scoped.org_id if scoped else "unknown_org"
        department_id = scoped.department_id if scoped else None
        run_id = scoped.run_id if scoped else None
        actor = f"run:{run_id}" if run_id else "unauthenticated_sandbox"

        params_summary = {
            "model": model,
            "estimated_cost_usd": estimated_cost_usd,
            "prompt_length": prompt_length,
            "redaction_count": redaction_count,
        }
        entry = record_security_audit_event(
            db=db,
            action=f"LLM_CALL_{decision}",
            actor=actor,
            entity_type="llm_model",
            entity_id=model or "unknown",
            org_id=org_id,
            department_id=department_id,
            run_id=run_id,
            parameters=params_summary,
            metadata=params_summary,
            decision=decision,
            reason=reason,
        )
        self.call_log.append(entry)
        return entry

    def authorize_and_meter_llm_call(
        self,
        db: Any,
        run_token: str,
        model: str,
        prompt_text: str,
        estimated_cost_usd: float = 0.01,
        redact_pii: bool = True,
    ) -> Dict[str, Any]:
        """
        Authorize and meter an LLM invocation before forwarding to any model provider.
        Fails closed (`PermissionError`) if token is invalid, model is not allowlisted,
        prompt exceeds size ceiling, or department budget is exhausted.
        """
        norm_model = (model or "").strip().lower()
        prompt_str = prompt_text if isinstance(prompt_text, str) else ""

        # 1. Validate run_token via SecretsBroker
        try:
            scoped = self.secrets_broker.validate_run_token(run_token)
        except PermissionError as exc:
            self._audit(db, None, norm_model, estimated_cost_usd, len(prompt_str), "DENIED", str(exc))
            raise

        # 2. Validate cost & prompt size ceiling
        if estimated_cost_usd < 0:
            reason = "Fail-closed: estimated_cost_usd cannot be negative"
            self._audit(db, scoped, norm_model, estimated_cost_usd, len(prompt_str), "DENIED", reason)
            raise PermissionError(reason)

        if not prompt_str.strip():
            reason = "Fail-closed: prompt_text cannot be empty"
            self._audit(db, scoped, norm_model, estimated_cost_usd, 0, "DENIED", reason)
            raise PermissionError(reason)

        if len(prompt_str) > self.max_prompt_chars:
            reason = (
                f"Fail-closed: Prompt length ({len(prompt_str)} chars) exceeds "
                f"ceiling ({self.max_prompt_chars} chars)"
            )
            self._audit(db, scoped, norm_model, estimated_cost_usd, len(prompt_str), "DENIED", reason)
            raise PermissionError(reason)

        # 3. Enforce model allowlist
        if not norm_model or norm_model not in self.allowed_models:
            reason = f"Fail-closed: Model '{model}' is not in the authorized LLM allowlist"
            self._audit(db, scoped, norm_model, estimated_cost_usd, len(prompt_str), "DENIED", reason)
            raise PermissionError(reason)

        # 4. Enforce department HARD_STOP budget BEFORE every LLM call
        if db is None or not hasattr(db, "check_department_budget"):
            reason = "Fail-closed: Database budget verifier is unavailable"
            self._audit(db, scoped, norm_model, estimated_cost_usd, len(prompt_str), "DENIED", reason)
            raise PermissionError(reason)

        budget_status = db.check_department_budget(
            scoped.department_id, requested_cost=float(estimated_cost_usd)
        )
        if not budget_status.get("allowed", False):
            action = budget_status.get("action", "HARD_STOP")
            msg = budget_status.get("message", "Department monthly budget exceeded")
            reason = f"Fail-closed ({action}): {msg}"
            self._audit(db, scoped, norm_model, estimated_cost_usd, len(prompt_str), "DENIED", reason)
            raise PermissionError(reason)

        # 5. Redact PII and credentials if enabled
        if redact_pii:
            sanitized_prompt, redaction_count = self.redact_pii_and_secrets(prompt_str)
        else:
            sanitized_prompt, redaction_count = prompt_str, 0

        audit_entry = self._audit(
            db=db,
            scoped=scoped,
            model=norm_model,
            estimated_cost_usd=estimated_cost_usd,
            prompt_length=len(sanitized_prompt),
            decision="ALLOWED",
            reason="LLM call authorized within department budget",
            redaction_count=redaction_count,
        )

        return {
            "allowed": True,
            "decision": "ALLOWED",
            "org_id": scoped.org_id,
            "department_id": scoped.department_id,
            "run_id": scoped.run_id,
            "user_id": scoped.user_id,
            "model": norm_model,
            "estimated_cost_usd": estimated_cost_usd,
            "sanitized_prompt": sanitized_prompt,
            "redaction_count": redaction_count,
            "budget_status": budget_status,
            "prompt_hash": compute_params_hash({"prompt": sanitized_prompt}),
            "audit_id": audit_entry["id"],
        }


# Default singleton instance shared across runtime gateways
llm_proxy = LLMProxy(secrets_broker_instance=secrets_broker)
