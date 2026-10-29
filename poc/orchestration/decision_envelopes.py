"""Lean transport-independent supervisor decision contracts."""
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class DecisionQuestionEnvelope:
    """Lean, sanitized decision request envelope preventing context bloat."""
    task_id: str
    requester_agent_id: str
    target_approver_id: str
    question: str
    context_summary: Optional[str] = None
    suggested_options: Optional[List[str]] = None
    urgency: str = "normal"
    channel_key: Optional[str] = None

    @classmethod
    def create(
        cls,
        task_id: str,
        requester_agent_id: str,
        target_approver_id: str,
        question: str,
        context: Optional[str] = None,
        suggested_options: Optional[List[str]] = None,
        urgency: str = "normal"
    ) -> 'DecisionQuestionEnvelope':
        clean_context = None
        if context:
            # Strip ANSI escape sequences and terminal noise
            stripped = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', str(context))
            stripped = ' '.join(stripped.split())
            clean_context = stripped[:500] + ("..." if len(stripped) > 500 else "")

        channel_key = f"channel:{target_approver_id}:{requester_agent_id}:{task_id}"
        return cls(
            task_id=task_id,
            requester_agent_id=requester_agent_id,
            target_approver_id=target_approver_id,
            question=question.strip() if question else "",
            context_summary=clean_context,
            suggested_options=suggested_options or [],
            urgency=urgency,
            channel_key=channel_key
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionAnswerEnvelope:
    """Concise decision response envelope directly unblocking the worker."""
    task_id: str
    decision: str
    rationale: Optional[str] = None
    source: str = "FAST_PATH_MEMORY"  # FAST_PATH_MEMORY, FAST_PATH_SUPER_AGENT, SLOW_PATH_MANAGER, SLOW_PATH_HUMAN
    channel_key: Optional[str] = None
    unblock: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

