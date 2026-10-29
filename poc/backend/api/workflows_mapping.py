"""Workflows: mapping ownership."""

from fastapi import HTTPException, status
from typing import Dict, Any
import json
from workflows.parser import WorkflowParser
from .workflows_models import WorkflowResponse, WorkflowExecutionResponse


def _check_workflow_scope(wf, scope: Dict[str, Any]):
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    if org_id and getattr(wf, "organization_id", None) and wf.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    if not is_org_admin and getattr(wf, "department_id", None) and authorized_dept_ids and wf.department_id not in authorized_dept_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access workflow in this department")



def _workflow_to_response(wf) -> WorkflowResponse:
    y_repr = None
    try:
        y_repr = WorkflowParser.json_to_yaml(wf.definition_json)
    except Exception:
        pass

    channel_binding = None
    runner_agent_id = None
    try:
        import json
        dj = json.loads(wf.definition_json)
        channel_binding = dj.get("metadata", {}).get("channel_binding")
        runner_agent_id = dj.get("runner_agent_id") or f"wf-agent-{wf.id}"
    except Exception:
        runner_agent_id = f"wf-agent-{wf.id}"

    return WorkflowResponse(
        id=wf.id,
        name=wf.name,
        description=wf.description,
        department_id=wf.department_id,
        definition_json=wf.definition_json,
        definition_yaml=y_repr,
        webhook_enabled=wf.webhook_enabled,
        webhook_token=wf.webhook_token,
        cron_expression=wf.cron_expression,
        is_active=wf.is_active,
        channel_binding=channel_binding,
        runner_agent_id=runner_agent_id,
        organization_id=getattr(wf, "organization_id", None),
        created_at=wf.created_at,
        updated_at=wf.updated_at
    )



def _execution_to_response(record) -> WorkflowExecutionResponse:
    """One execution projection for manual, webhook and detail responses."""
    return WorkflowExecutionResponse(
        id=record.id, workflow_id=record.workflow_id,
        trigger_type=record.trigger_type, trigger_payload=record.trigger_payload,
        status=record.status, department_id=record.department_id,
        sandbox_path=record.sandbox_path, total_input_tokens=record.total_input_tokens,
        total_output_tokens=record.total_output_tokens, total_cost_usd=record.total_cost_usd,
        started_at=record.started_at, completed_at=record.completed_at,
        error_message=record.error_message, created_at=record.created_at,
    )
