"""HTTP adapter; future MCP tools can call the same service with verified identity."""

from typing import Optional
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request

from ..dependencies import get_db_manager, get_runtime_adapter, get_optional_runtime_adapter
from .models import DraftCreate, DraftUpdate, GenerationRequest, SaveGenerationRequest, ValidationRequest, YamlValidationRequest
from .service import AssistantError, WorkflowAssistantService
from .generation import AuthoringGenerationService
from .tools import WorkflowAuthoringTools

router = APIRouter()
logger = logging.getLogger(__name__)


def get_assistant_service(request: Request, db=Depends(get_db_manager)):
    claims = getattr(request.state, "user", None) or {}
    scopes = claims.get("scope")
    granted_scopes = set(scopes.split()) if isinstance(scopes, str) else set() if scopes is not None else None
    return WorkflowAssistantService(db, claims, source="platform_api", granted_scopes=granted_scopes)


def _call(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except AssistantError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@router.get("/context")
def context(service=Depends(get_assistant_service), runtime=Depends(get_optional_runtime_adapter)):
    workspace = _call(service.context)
    supports_generation, models = False, []
    if runtime is not None:
        try:
            supports_generation = bool(getattr(runtime.get_capabilities(), "supports_authoring", False))
            if supports_generation:
                models = runtime.get_authoring_models()
        except Exception:
            # Provider inventory is optional metadata, not authority for DB reads.
            logger.warning("Authoring model inventory is unavailable")
            supports_generation, models = False, []
    return {**workspace, "supports_generation": supports_generation, "authoring_models": models}


@router.get("/catalog")
def catalog(department_id: str = Query(..., min_length=1, max_length=200),
            service=Depends(get_assistant_service)):
    return _call(service.catalog, department_id)


@router.get("/proposal-schema")
def proposal_schema(service=Depends(get_assistant_service)):
    _call(service.context)
    return {"proposal_schema_version": 1, "schema": ValidationRequest.model_json_schema()}


@router.post("/validate")
def validate(request: ValidationRequest, service=Depends(get_assistant_service)):
    return _call(service.validate, request.department_id, request.proposal)


@router.post("/drafts", status_code=201)
def create_draft(request: DraftCreate, service=Depends(get_assistant_service),
                 idempotency_key: Optional[str] = Header(None, min_length=1, max_length=128,
                    pattern=r"^[A-Za-z0-9._:-]+$", alias="Idempotency-Key")):
    return _call(service.create_draft, request, idempotency_key)


@router.get("/drafts")
def list_drafts(department_id: str = Query(..., min_length=1, max_length=200),
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                service=Depends(get_assistant_service)):
    return _call(service.list_drafts, department_id, limit=limit, offset=offset)


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, service=Depends(get_assistant_service)):
    return _call(service.get_draft, draft_id)


@router.put("/drafts/{draft_id}")
def update_draft(draft_id: str, request: DraftUpdate, service=Depends(get_assistant_service)):
    return _call(service.update_draft, draft_id, request)


@router.get("/drafts/{draft_id}/revisions")
def history(draft_id: str, limit: int = Query(50, ge=1, le=100),
            before_revision: Optional[int] = Query(None, ge=1),
            service=Depends(get_assistant_service)):
    return _call(service.history, draft_id, limit=limit, before_revision=before_revision)


def get_generation_service(service=Depends(get_assistant_service)):
    """Read/cancel/save persisted generations independently from inference."""
    return AuthoringGenerationService(service)


def get_generation_execution_service(service=Depends(get_assistant_service), runtime=Depends(get_runtime_adapter)):
    """Only new inference requests require a live execution adapter."""
    return AuthoringGenerationService(service, runtime)


@router.post("/generations", status_code=202)
def create_generation(request: GenerationRequest, background: BackgroundTasks,
                      service=Depends(get_generation_execution_service),
                      idempotency_key: Optional[str] = Header(None, min_length=1, max_length=128,
                          pattern=r"^[A-Za-z0-9._:-]+$", alias="Idempotency-Key")):
    generation, created = _call(service.create, request, idempotency_key)
    if created:
        background.add_task(service.run, generation["id"])
    return generation


@router.get("/generations/{generation_id}")
def get_generation(generation_id: str, service=Depends(get_generation_service)):
    return _call(service.get, generation_id)


@router.post("/generations/{generation_id}/cancel")
def cancel_generation(generation_id: str, service=Depends(get_generation_service)):
    return _call(service.cancel, generation_id)


@router.post("/generations/{generation_id}/save-draft")
def save_generation(generation_id: str, request: SaveGenerationRequest,
                    service=Depends(get_generation_service)):
    return _call(service.save, generation_id, request.save_blocked)


@router.get("/workflow-schema")
def workflow_schema(service=Depends(get_assistant_service)):
    return _call(WorkflowAuthoringTools(service).schema)


@router.post("/validate-yaml")
def validate_yaml(request: YamlValidationRequest, service=Depends(get_assistant_service)):
    try:
        return _call(WorkflowAuthoringTools(service).validate_yaml, request.department_id, request.yaml_content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "WORKFLOW_YAML_INVALID", "message": str(exc)}) from exc
