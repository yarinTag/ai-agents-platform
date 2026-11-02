"""Workflow request and response contracts."""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_yaml: Optional[str] = None
    definition_json: Optional[str] = None
    cron_expression: Optional[str] = None
    webhook_enabled: bool = True
    organization_id: Optional[str] = None

class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_yaml: Optional[str] = None
    definition_json: Optional[str] = None
    cron_expression: Optional[str] = None
    webhook_enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    organization_id: Optional[str] = None
    expected_revision: Optional[int] = Field(None, ge=1)
    change_summary: Optional[str] = Field(None, max_length=500)

class ChannelBindingDto(BaseModel):
    provider: str = Field(..., description="slack or telegram")
    connector_id: Optional[str] = "slack"
    channel_id: str = Field(..., min_length=1, description="e.g. #pr-review or @channel_bot")
    channel_name: Optional[str] = None
    trigger_enabled: bool = True
    notify_mode: Literal['COMPLETION_ONLY', 'START_AND_COMPLETE', 'EACH_STEP', 'ON_COMPLETE', 'ON_FAILURE', 'ALWAYS', 'NONE'] = 'COMPLETION_ONLY'
    message_template: Optional[str] = None

class WorkflowResponse(BaseModel):
    revision: int = 1
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
    organization_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class WorkflowRevisionResponse(BaseModel):
    workflow_id: str
    revision: int
    snapshot: Dict[str, Any]
    changed_fields: List[str]
    actor_id: Optional[str] = None
    actor_label: str
    change_summary: Optional[str] = None
    created_at: str

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
    cost_summary: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    notification_error: Optional[str] = None
    created_at: Optional[str] = None
    payload_hash: Optional[str] = None
    is_deduplicated: Optional[bool] = False
    message: Optional[str] = None
    step_runs: List[Dict[str, Any]] = Field(default_factory=list)

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

