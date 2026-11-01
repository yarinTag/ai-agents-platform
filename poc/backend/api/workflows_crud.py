from fastapi import APIRouter, HTTPException, Depends, status, Request, Query

from typing import List, Optional

import uuid

import json

import logging

import yaml

from ..dependencies import get_db_manager, DatabaseManager, AgentConfig, WorkflowRevisionConflict

from ..security import get_authorized_scope

from workflows.parser import validate_workflow_definition

from .workflows_models import WorkflowCreateRequest, WorkflowUpdateRequest, WorkflowResponse, WorkflowRevisionResponse
from .workflows_mapping import _workflow_actor, _check_workflow_scope, _workflow_to_response

logger = logging.getLogger(__name__)
router = APIRouter()
_validated_definition = validate_workflow_definition

@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    req: WorkflowCreateRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    return persist_workflow(req, request, db)


def persist_workflow(req, request, db, workflow_id=None, initially_active=True):
    """Shared creation/provisioning path; chat supplies a stable ID and starts inactive."""
    def_json = req.definition_json
    if not def_json and req.definition_yaml:
        try:
            def_json = json.dumps(_validated_definition(yaml.safe_load(req.definition_yaml)))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML definition: {e}")
    elif not def_json:
        raise HTTPException(status_code=400, detail="Either definition_yaml or definition_json is required")

    try:
        _validated_definition(json.loads(def_json))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid workflow definition: {exc}") from exc

    scope = get_authorized_scope(request, db)
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    target_dept_id = req.department_id or scope["default_department_id"]
    if target_dept_id:
        dept = db.get_department(target_dept_id)
        if not dept or (org_id and dept.organization_id and dept.organization_id != org_id):
            raise HTTPException(status_code=400, detail=f"Department '{target_dept_id}' does not belong to your organization")
        if not is_org_admin and target_dept_id not in authorized_dept_ids:
            raise HTTPException(status_code=403, detail=f"Not authorized to assign workflow to department '{target_dept_id}'")

    wf_id = workflow_id or f"wf_{uuid.uuid4().hex[:10]}"
    runner_agent_id = f"wf-agent-{wf_id}"

    # Extract metadata, MCPs, skills, steps, and channel info for the dedicated runner agent
    try:
        def_dict = json.loads(def_json) if isinstance(def_json, str) else dict(def_json)
    except Exception:
        def_dict = {}

    mcps = def_dict.get("mcp_servers") or []
    skills_raw = def_dict.get("skills") or []
    skill_names = [s.get("name", s.get("id", str(s))) if isinstance(s, dict) else str(s) for s in skills_raw]
    steps = def_dict.get("steps") or []
    for step in steps:
        if step.get('agent_id') == '__workflow_runner__':
            step['agent_id'] = runner_agent_id
    cb = def_dict.get("metadata", {}).get("channel_binding") or {}
    channel_info = f"{cb.get('provider')}:{cb.get('channel_id')}" if cb.get("channel_id") else "API/Webhook/Manual"
    cron = req.cron_expression or def_dict.get("trigger", {}).get("cron_expression") or def_dict.get("trigger", {}).get("cron") or "None"

    # Build prompt for background automation agent
    step_desc = "\n".join(f"- Step {i+1} [{s.get('id', 'step')}]: {s.get('name', 'Action')} ({s.get('type', 'AGENT')})" for i, s in enumerate(steps)) or "- Multi-step automated DAG pipeline"
    system_prompt = (
        f"You are the autonomous workflow execution agent for '{req.name}' (Workflow ID: {wf_id}).\n"
        f"Trigger schedule: Cron [{cron}], Channel trigger [{channel_info}].\n"
        f"Assigned MCP scope: {', '.join(mcps) if mcps else 'All platform MCPs'}.\n"
        f"Connected skills: {', '.join(skill_names) if skill_names else 'Standard'}.\n"
        f"Pipeline stages:\n{step_desc}\n\n"
        f"Execution rules:\n"
        f"1. You run automatically in background cloud workers on schedule or when triggered via the channel.\n"
        f"2. You are completely detached from the 2D pixel office simulation canvas and do not occupy an office desk.\n"
        f"3. Strictly enforce the assigned MCP scope and skills during DAG execution."
    )

    # Save dedicated workflow automation agent (bound to BOTH org_id and department_id)
    try:
        runner_agent = AgentConfig(
            id=runner_agent_id,
            name=f"{req.name} Runner",
            description=f"Autonomous workflow agent for '{req.name}'. Runs periodically or via channel '{channel_info}'. Detached from office floor.",
            system_prompt=system_prompt,
            skills=skill_names,
            department="Workflow Automations",
            role_type="WORKFLOW_AUTOMATION",
            is_workflow_agent=True,
            workflow_id=wf_id,
            organization_id=org_id,
            department_id=target_dept_id,
            mcp_permissions=mcps,
            # Workspace file tools only; no host shell for workflow runners.
            allowed_tools=["Read", "Grep", "Glob", "Write", "Edit", "AskUserQuestion"],
            avatar=f"https://api.dicebear.com/7.x/bottts/svg?seed={wf_id}",
            temperature=0.3
        )
        db.save_agent(runner_agent)
    except Exception as e:
        logger.warning("Could not provision dedicated workflow runner")
        raise HTTPException(503, "Could not provision the dedicated workflow runner. Retry creation after checking agent capacity.") from e

    # Inject runner agent ID and status into definition
    def_dict["id"] = wf_id
    def_dict["runner_agent_id"] = runner_agent_id
    def_dict["is_workflow_agent"] = True
    def_json = json.dumps(def_dict, indent=2)

    wf = db.create_workflow(
        id=wf_id,
        name=req.name,
        definition_json=def_json,
        department_id=target_dept_id,
        description=req.description,
        cron_expression=req.cron_expression,
        webhook_enabled=req.webhook_enabled,
        organization_id=org_id,
        is_active=initially_active,
        **_workflow_actor(request)
    )

    yaml_repr = None
    try:
        yaml_repr = yaml.safe_dump(json.loads(wf.definition_json), sort_keys=False, allow_unicode=True)
    except Exception:
        pass

    return WorkflowResponse(
        revision=getattr(wf, "revision", 1),
        id=wf.id,
        name=wf.name,
        description=wf.description,
        department_id=wf.department_id,
        definition_json=wf.definition_json,
        definition_yaml=yaml_repr,
        webhook_enabled=wf.webhook_enabled,
        webhook_token=wf.webhook_token,
        cron_expression=wf.cron_expression,
        is_active=wf.is_active,
        runner_agent_id=runner_agent_id,
        organization_id=getattr(wf, "organization_id", None),
        created_at=wf.created_at,
        updated_at=wf.updated_at
    )

@router.get("", response_model=List[WorkflowResponse])
@router.get("/", response_model=List[WorkflowResponse])
def list_workflows(
    request: Request,
    department_id: Optional[str] = None,
    active_only: bool = False,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List workflows strictly scoped by organization and authorized departments."""
    scope = get_authorized_scope(request, db)
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    target_dept_ids = None
    if department_id:
        if not is_org_admin and department_id not in authorized_dept_ids:
            raise HTTPException(status_code=403, detail="Not authorized to access workflows in this department")
        target_dept_ids = [department_id]
    elif not is_org_admin and org_id:
        target_dept_ids = authorized_dept_ids

    workflows = db.list_workflows(
        department_id=None,
        active_only=active_only,
        organization_id=org_id,
        department_ids=target_dept_ids
    )
    return [_workflow_to_response(wf) for wf in workflows]

@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get workflow by ID."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scope = get_authorized_scope(request, db)
    _check_workflow_scope(wf, scope)
    return _workflow_to_response(wf)

@router.get("/{workflow_id}/revisions", response_model=List[WorkflowRevisionResponse])
def list_workflow_revisions(
    workflow_id: str, request: Request,
    limit: int = Query(50, ge=1, le=100),
    before_revision: Optional[int] = Query(None, ge=1),
    db: DatabaseManager = Depends(get_db_manager)
):
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _check_workflow_scope(wf, get_authorized_scope(request, db))
    return db.list_workflow_revisions(workflow_id, limit=limit, before_revision=before_revision)

@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str, req: WorkflowUpdateRequest, request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Save one atomic revision, retaining unspecified settings and tenant identity."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scope = get_authorized_scope(request, db)
    _check_workflow_scope(wf, scope)
    changes = req.model_dump(exclude_unset=True)
    changes.pop("definition_yaml", None)
    changes.pop("expected_revision", None)
    changes.pop("change_summary", None)
    if "organization_id" in changes and changes["organization_id"] != wf.organization_id:
        raise HTTPException(status_code=403, detail="Workflow organization cannot be changed")
    if "name" in changes and (not changes["name"] or not changes["name"].strip()):
        raise HTTPException(status_code=400, detail="Workflow name cannot be empty")
    if "department_id" in changes:
        dept_id = changes["department_id"]
        if dept_id:
            dept = db.get_department(dept_id)
            if not dept or (scope["org_id"] and dept.organization_id != scope["org_id"]):
                raise HTTPException(status_code=400, detail="Department does not belong to your organization")
            if not scope["is_org_admin"] and dept_id not in scope["department_ids"]:
                raise HTTPException(status_code=403, detail="Not authorized to assign this department")
        elif not scope["is_org_admin"]:
            raise HTTPException(status_code=403, detail="Only organization admins can remove department scope")
    if req.definition_json is not None or req.definition_yaml is not None:
        try:
            data = _validated_definition(json.loads(req.definition_json) if req.definition_json is not None
                                         else yaml.safe_load(req.definition_yaml))
            data["id"] = wf.id
            original = json.loads(wf.definition_json)
            if "runner_agent_id" in original:
                data["runner_agent_id"] = original["runner_agent_id"]
            changes["definition_json"] = json.dumps(data, ensure_ascii=False)
        except (ValueError, TypeError, AttributeError, yaml.YAMLError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid workflow definition: {exc}") from exc
    try:
        updated = db.update_workflow(workflow_id, **changes, **_workflow_actor(request),
            expected_revision=req.expected_revision, change_summary=req.change_summary)
    except WorkflowRevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if "department_id" in changes:
        runner_agent = db.get_agent(f"wf-agent-{workflow_id}")
        if runner_agent:
            runner_agent.department_id = changes["department_id"]
            db.save_agent(runner_agent)
    return _workflow_to_response(updated)

@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Delete a workflow with tenant check."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scope = get_authorized_scope(request, db)
    _check_workflow_scope(wf, scope)
    
    # Clean up associated runner agent
    try:
        db.delete_agent(f"wf-agent-{workflow_id}")
    except Exception:
        pass
    try:
        with db._get_connection() as conn:
            conn.execute("DELETE FROM agents WHERE workflow_id = ? OR id = ?", (workflow_id, f"wf-agent-{workflow_id}"))
            conn.commit()
    except Exception:
        pass

    db.delete_workflow(workflow_id)
    return {"status": "success", "message": f"Workflow {workflow_id} deleted"}

