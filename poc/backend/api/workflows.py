"""
Workflows and Webhooks API Router.
Supports:
- CRUD for workflows (JSON / YAML formats)
- Workflow preset/template generation (delegated to workflows.presets)
- Dedicated runner agent lifecycle (delegated to workflows.runner_provisioner)
- Workflow execution (manual trigger & incoming webhooks)
- Execution inspection with full token usage and cost accounting
- Human evaluations and lessons learned
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
import json
import logging

from ..dependencies import get_db_manager, get_workflow_engine, DatabaseManager, AgentConfig
from workflows.parser import WorkflowParser
from workflows.engine import (
    WorkflowEngine,
    BudgetExceededError,
    MCPGovernanceViolationError,
    UnauthorizedUserDepartmentError,
)
from workflows.presets import build_generated_workflow_definition
from workflows.runner_provisioner import (
    provision_workflow_runner_agent,
    cleanup_workflow_runner_agent,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_yaml: Optional[str] = None
    definition_json: Optional[str] = None
    cron_expression: Optional[str] = None
    webhook_enabled: bool = True


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_yaml: Optional[str] = None
    definition_json: Optional[str] = None
    cron_expression: Optional[str] = None
    webhook_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class ChannelBindingDto(BaseModel):
    provider: str = Field(..., description="slack or telegram")
    connector_id: Optional[str] = "slack"
    channel_id: str = Field(..., min_length=1, description="e.g. #pr-review or @channel_bot")
    channel_name: Optional[str] = None
    trigger_enabled: bool = True
    notify_mode: str = Field("ON_COMPLETE", description="ON_COMPLETE, ON_FAILURE, ALWAYS, NONE")
    message_template: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_json: str
    definition_yaml: Optional[str] = None
    webhook_enabled: bool
    webhook_token: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: bool
    channel_binding: Optional[Dict[str, Any]] = None
    runner_agent_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    trigger_type: str
    trigger_payload: Optional[str] = None
    status: str
    department_id: Optional[str] = None
    sandbox_path: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class EvaluationRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_notes: Optional[str] = None
    lessons_extracted: Optional[str] = None


class WorkflowGenerateRequest(BaseModel):
    prompt: Optional[str] = None
    template_type: Optional[str] = None
    name: Optional[str] = None
    channel_provider: Optional[str] = None
    channel_id: Optional[str] = None
    allowed_mcps: Optional[List[str]] = None
    skills: Optional[List[Dict[str, Any]]] = None
    target_repo: Optional[str] = None


class WorkflowGenerateResponse(BaseModel):
    id: str
    name: str
    description: str
    definition_json: str
    definition_yaml: str
    steps_count: int


class WorkflowFormatConvertRequest(BaseModel):
    yaml_content: Optional[str] = None
    json_content: Optional[str] = None


class WorkflowFormatConvertResponse(BaseModel):
    yaml_content: str
    json_content: str


def _workflow_to_response(wf) -> WorkflowResponse:
    y_repr = None
    try:
        y_repr = WorkflowParser.json_to_yaml(wf.definition_json)
    except Exception:
        pass

    channel_binding = None
    runner_agent_id = None
    try:
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
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


def _execution_to_response(exec_record) -> WorkflowExecutionResponse:
    return WorkflowExecutionResponse(
        id=exec_record.id,
        workflow_id=exec_record.workflow_id,
        trigger_type=exec_record.trigger_type,
        trigger_payload=exec_record.trigger_payload,
        status=exec_record.status,
        department_id=exec_record.department_id,
        sandbox_path=exec_record.sandbox_path,
        total_input_tokens=exec_record.total_input_tokens,
        total_output_tokens=exec_record.total_output_tokens,
        total_cost_usd=exec_record.total_cost_usd,
        started_at=exec_record.started_at,
        completed_at=exec_record.completed_at,
        error_message=exec_record.error_message,
        created_at=exec_record.created_at,
    )


@router.post("/generate", response_model=WorkflowGenerateResponse)
def generate_workflow_definition(
    req: WorkflowGenerateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Generate an intelligent, production-ready workflow definition from prompt or template."""
    generated = build_generated_workflow_definition(
        db=db,
        prompt_raw=req.prompt,
        template_type=req.template_type,
        name=req.name,
        channel_provider=req.channel_provider,
        channel_id=req.channel_id,
        allowed_mcps=req.allowed_mcps,
        skills=req.skills,
        target_repo=req.target_repo,
    )
    return WorkflowGenerateResponse(**generated)


@router.post("/convert-format", response_model=WorkflowFormatConvertResponse)
def convert_format(req: WorkflowFormatConvertRequest):
    """Convert bidirectionally between YAML and JSON workflow definitions."""
    if req.yaml_content:
        try:
            json_str = WorkflowParser.yaml_to_json(req.yaml_content)
            return WorkflowFormatConvertResponse(yaml_content=req.yaml_content, json_content=json_str)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    elif req.json_content:
        try:
            yaml_str = WorkflowParser.json_to_yaml(req.json_content)
            return WorkflowFormatConvertResponse(yaml_content=yaml_str, json_content=req.json_content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    raise HTTPException(status_code=400, detail="Either yaml_content or json_content is required")


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    req: WorkflowCreateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new workflow from YAML or JSON definition and provision its runner agent."""
    def_json = req.definition_json
    if not def_json and req.definition_yaml:
        try:
            def_json = WorkflowParser.yaml_to_json(req.definition_yaml)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML definition: {e}")
    elif not def_json:
        raise HTTPException(status_code=400, detail="Either definition_yaml or definition_json is required")

    wf_id = f"wf_{uuid.uuid4().hex[:10]}"
    runner_agent_id, enriched_json = provision_workflow_runner_agent(
        db=db,
        agent_config_cls=AgentConfig,
        wf_id=wf_id,
        workflow_name=req.name,
        def_json=def_json,
        cron_expression=req.cron_expression,
    )

    wf = db.create_workflow(
        id=wf_id,
        name=req.name,
        definition_json=enriched_json,
        department_id=req.department_id,
        description=req.description,
        cron_expression=req.cron_expression,
        webhook_enabled=req.webhook_enabled
    )
    return _workflow_to_response(wf)


@router.get("", response_model=List[WorkflowResponse])
@router.get("/", response_model=List[WorkflowResponse])
def list_workflows(
    department_id: Optional[str] = None,
    active_only: bool = False,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List workflows."""
    workflows = db.list_workflows(department_id=department_id, active_only=active_only)
    return [_workflow_to_response(wf) for wf in workflows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get workflow by ID."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _workflow_to_response(wf)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str,
    req: WorkflowUpdateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update workflow settings or definition."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    def_json = req.definition_json
    if not def_json and req.definition_yaml:
        try:
            def_json = WorkflowParser.yaml_to_json(req.definition_yaml)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML definition: {e}")

    updated = db.update_workflow(
        id=workflow_id,
        name=req.name,
        description=req.description,
        department_id=req.department_id,
        definition_json=def_json,
        cron_expression=req.cron_expression,
        webhook_enabled=req.webhook_enabled,
        is_active=req.is_active
    )
    return _workflow_to_response(updated)


@router.post("/{workflow_id}/channel-binding", response_model=WorkflowResponse)
def bind_workflow_channel(
    workflow_id: str,
    req: ChannelBindingDto,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Bind a communication channel (Slack / Telegram) to a workflow."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        def_dict = json.loads(wf.definition_json or "{}")
    except Exception:
        def_dict = {"id": wf.id, "name": wf.name, "steps": []}

    metadata = def_dict.get("metadata") or {}
    metadata["channel_binding"] = req.model_dump()
    def_dict["metadata"] = metadata

    new_def_json = json.dumps(def_dict, indent=2)
    updated = db.update_workflow(id=workflow_id, definition_json=new_def_json)
    return _workflow_to_response(updated)


@router.delete("/{workflow_id}/channel-binding", response_model=WorkflowResponse)
def unbind_workflow_channel(
    workflow_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Remove communication channel binding from a workflow."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        def_dict = json.loads(wf.definition_json or "{}")
    except Exception:
        def_dict = {}

    if "metadata" in def_dict and "channel_binding" in def_dict["metadata"]:
        del def_dict["metadata"]["channel_binding"]

    new_def_json = json.dumps(def_dict, indent=2)
    updated = db.update_workflow(id=workflow_id, definition_json=new_def_json)
    return _workflow_to_response(updated)


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Delete a workflow and clean up its dedicated runner agent."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    cleanup_workflow_runner_agent(db, workflow_id)
    db.delete_workflow(workflow_id)
    return {"status": "success", "message": f"Workflow {workflow_id} deleted"}


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow(
    workflow_id: str,
    request: Request,
    payload: Optional[Dict[str, Any]] = None,
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """Manually trigger a workflow execution."""
    try:
        user_ctx = getattr(request.state, "user", None)
        execution = engine.execute_workflow(
            workflow_id=workflow_id,
            trigger_type="MANUAL",
            trigger_payload=payload,
            user_context=user_ctx
        )
        return _execution_to_response(execution)
    except UnauthorizedUserDepartmentError as uude:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Department Access Denied: {str(uude)}"
        )
    except MCPGovernanceViolationError as mcp_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MCP Governance Violation: {str(mcp_err)}"
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Budget limit reached for department '{be.department_id}': {str(be)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/{webhook_token}", response_model=WorkflowExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_webhook(
    webhook_token: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager),
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """Incoming webhook endpoint for a specific workflow."""
    wf = db.get_workflow_by_webhook_token(webhook_token)
    if not wf:
        raise HTTPException(status_code=404, detail="Invalid or inactive webhook token")

    body_data = {}
    try:
        body_data = await request.json()
    except Exception:
        pass

    try:
        execution = engine.execute_workflow(
            workflow_id=wf.id,
            trigger_type="WEBHOOK",
            trigger_payload=body_data
        )
        return _execution_to_response(execution)
    except MCPGovernanceViolationError as mcp_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MCP Governance Violation: {str(mcp_err)}"
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Department budget exceeded: {str(be)}"
        )


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
def get_execution_status(
    execution_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get full status and token/cost metrics of a workflow execution."""
    exec_record = db.get_workflow_execution(execution_id)
    if not exec_record:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _execution_to_response(exec_record)


@router.post("/executions/{execution_id}/evaluate", status_code=status.HTTP_201_CREATED)
def evaluate_execution(
    execution_id: str,
    req: EvaluationRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Submit human review, rating, and lessons learned for self-improvement."""
    exec_record = db.get_workflow_execution(execution_id)
    if not exec_record:
        raise HTTPException(status_code=404, detail="Execution not found")

    eval_id = f"eval_{uuid.uuid4().hex[:10]}"
    db.save_run_evaluation(
        id=eval_id,
        execution_id=execution_id,
        workflow_id=exec_record.workflow_id,
        rating=req.rating,
        feedback_notes=req.feedback_notes,
        lessons_extracted=req.lessons_extracted
    )
    return {"status": "SUCCESS", "evaluation_id": eval_id}
