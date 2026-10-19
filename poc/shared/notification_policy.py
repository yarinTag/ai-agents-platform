"""
Workflow notification policy evaluation (pure logic, no I/O).

Policies: FINAL_ONLY (default), START_AND_END, EVERY_STEP, ON_FAILURE_ONLY, plus the
backward-compatible `notify_mode` (ON_COMPLETE / ON_FAILURE / ALWAYS) for FINAL_ONLY.
"""

from typing import Any, Dict

VALID_NOTIFY_POLICIES = ("FINAL_ONLY", "START_AND_END", "EVERY_STEP", "ON_FAILURE_ONLY")


def should_send_notification(
    channel_binding: Dict[str, Any],
    event_type: str,
    final_status: str = "COMPLETED",
    step_notify_override: bool = False,
) -> bool:
    """Evaluate whether a workflow lifecycle event should trigger a channel notification."""
    if not channel_binding or not isinstance(channel_binding, dict):
        return False

    policy = str(channel_binding.get("notify_policy") or "FINAL_ONLY").upper()
    event_upper = str(event_type or "").upper()
    status_upper = str(final_status or "COMPLETED").upper()

    if policy == "ON_FAILURE_ONLY":
        return status_upper == "FAILED"
    if policy == "EVERY_STEP":
        return event_upper in ("WORKFLOW_START", "STEP_COMPLETE", "WORKFLOW_END")
    if policy == "START_AND_END":
        return event_upper in ("WORKFLOW_START", "WORKFLOW_END") or (
            event_upper == "STEP_COMPLETE" and bool(step_notify_override)
        )

    # Default policy: FINAL_ONLY (with backward-compatible notify_mode support)
    if event_upper == "STEP_COMPLETE":
        return bool(step_notify_override)
    if event_upper == "WORKFLOW_END":
        notify_mode = str(channel_binding.get("notify_mode") or "ON_COMPLETE").upper()
        return (
            notify_mode == "ALWAYS"
            or (notify_mode == "ON_COMPLETE" and status_upper == "COMPLETED")
            or (notify_mode == "ON_FAILURE" and status_upper == "FAILED")
        )
    return False
