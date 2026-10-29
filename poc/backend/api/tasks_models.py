"""Tasks: models ownership."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    agent_id: str = Field(..., min_length=1)
    prompt: Optional[str] = None
    input_data: Optional[Any] = None
    project_id: Optional[str] = None
    skill_id: Optional[str] = None
    organization_id: Optional[str] = None



class TaskDelegateRequest(BaseModel):
    target_agent_id: str = Field(..., min_length=1)
    subtask_prompt: str = Field(..., min_length=1)
    timeout_seconds: Optional[int] = Field(default=300, ge=10, le=3600)
    project_id: Optional[str] = None
    dependencies: Optional[List[str]] = None
    acceptance_criteria: Optional[str] = None



class TaskResponse(BaseModel):
    id: str
    run_id: str
    agent_id: str
    project_id: Optional[str] = None
    organization_id: Optional[str] = None
    prompt: str = ""
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    status: str
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    parent_task_id: Optional[str] = None
    root_task_id: Optional[str] = None
    assigned_by: Optional[str] = None
    events: Optional[List[Dict[str, Any]]] = None
    dependencies: Optional[List[str]] = None
    structured_result: Optional[Dict[str, Any]] = None
    acceptance_criteria: Optional[str] = None
    retry_count: Optional[int] = 0
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    cache_read_tokens: Optional[int] = 0
    cache_write_tokens: Optional[int] = 0
    cost_usd: Optional[float] = 0.0
    cost_source: Optional[str] = "UNKNOWN"
    model: Optional[str] = None

    class Config:
        from_attributes = True



class TaskEvent(BaseModel):
    type: str
    timestamp: float
    run_id: str
    # Additional fields will vary by event type
    message: Optional[dict] = None
    result: Optional[str] = None
    error: Optional[dict] = None
    estimated_tokens: Optional[int] = None
    estimated_tokens_delta: Optional[int] = None
    subtype: Optional[str] = None
    session_id: Optional[str] = None

