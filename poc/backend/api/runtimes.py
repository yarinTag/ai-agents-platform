"""
Runtime provider selection API.

Backs the runtime setup modal: reports which API providers are configured,
allows updating provider API keys/models/enabled states, and persists the
platform default provider.
"""

import logging
import os
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from runtime.direct_config import (
    DIRECT_PROVIDERS,
    DEFAULT_PROVIDER_MODEL,
    PROVIDER_MODELS,
    api_key_setting,
    enabled_setting,
    model_setting,
    resolve_api_key,
    validate_model,
)

from ..dependencies import db_manager, runtime_providers as providers

logger = logging.getLogger(__name__)

router = APIRouter()


class ProviderStatusResponse(BaseModel):
    id: str
    name: str
    description: str
    available: bool
    detail: str
    requires_config: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    is_selected: bool = False


class SetupStateResponse(BaseModel):
    setup_completed: bool
    selected_provider: Optional[str] = None
    effective_provider: str
    suggested_provider: Optional[str] = None
    providers: List[ProviderStatusResponse]


class ProviderSelectionRequest(BaseModel):
    provider_id: str
    gateway_base_url: Optional[str] = None
    model_id: Optional[str] = Field(default=None, max_length=200)
    api_key: Optional[str] = Field(default=None, max_length=500)
    enabled_providers: Optional[List[str]] = None
    provider_models: Optional[Dict[str, str]] = None
    provider_keys: Optional[Dict[str, str]] = None


def _build_setup_state() -> SetupStateResponse:
    raw_selected = db_manager.get_setting(providers.SETTING_PROVIDER)
    setup_completed = db_manager.get_setting(providers.SETTING_SETUP_COMPLETED) == "true"
    effective = providers.resolve_provider_selection(saved_choice=raw_selected)
    selected = effective if (raw_selected and "PYTEST_CURRENT_TEST" not in os.environ) else raw_selected

    detected = providers.detect_providers()
    provider_Items: List[ProviderStatusResponse] = []
    for s in detected:
        cfg = dict(s.config)
        if s.id in DIRECT_PROVIDERS:
            saved_model = db_manager.get_setting(model_setting(s.id)) or DEFAULT_PROVIDER_MODEL.get(s.id, "")
            has_key = bool(resolve_api_key(s.id, db=db_manager))
            explicit_enabled = db_manager.get_setting(enabled_setting(s.id))
            is_enabled = (explicit_enabled == "true") if explicit_enabled is not None else (s.id == effective)
            cfg.update({
                "model_id": saved_model,
                "models": PROVIDER_MODELS.get(s.id, []),
                "has_api_key": has_key,
                "enabled": bool(is_enabled or s.id == selected),
            })
        provider_Items.append(
            ProviderStatusResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                available=s.available,
                detail=s.detail,
                requires_config=s.requires_config,
                config=cfg,
                is_selected=(s.id == selected),
            )
        )

    return SetupStateResponse(
        setup_completed=setup_completed,
        selected_provider=selected,
        effective_provider=effective,
        suggested_provider=providers.suggest_default_provider(),
        providers=provider_Items,
    )


@router.get("/", response_model=SetupStateResponse)
@router.get("", response_model=SetupStateResponse)
async def get_runtime_setup_state():
    """Report provider availability on this machine plus the current selection."""
    return _build_setup_state()


@router.put("/selection", response_model=SetupStateResponse)
async def select_runtime_provider(payload: ProviderSelectionRequest, request: Request):
    """Persist the platform-default runtime provider and optional per-provider settings."""
    user = getattr(request.state, 'user', None)
    if user and user.get('role') != 'ORG_ADMIN':
        raise HTTPException(status_code=403, detail='An organization administrator must configure the shared platform runtime.')
    provider_id = payload.provider_id.strip()
    forced = os.environ.get('PLATFORM_RUNTIME_PROVIDER', '').strip()
    if forced and forced != provider_id:
        raise HTTPException(status_code=409, detail='PLATFORM_RUNTIME_PROVIDER overrides this selection. Update the server environment first.')
    if provider_id not in providers.ALL_PROVIDER_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown runtime provider '{provider_id}'. "
                f"Expected one of: {', '.join(providers.ALL_PROVIDER_IDS)}."
            ),
        )

    # Save any provided API keys first so availability probe sees them immediately
    if payload.api_key is not None and payload.api_key.strip() and provider_id in DIRECT_PROVIDERS:
        db_manager.set_setting(api_key_setting(provider_id), payload.api_key.strip())
    if payload.provider_keys:
        for pid, key_val in payload.provider_keys.items():
            if pid in DIRECT_PROVIDERS and key_val is not None and key_val.strip():
                db_manager.set_setting(api_key_setting(pid), key_val.strip())

    if provider_id == providers.PROVIDER_CUSTOM_GATEWAY:
        raw_url = (payload.gateway_base_url or "").strip()
        if not raw_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A gateway base URL is required when selecting 'custom_gateway'.",
            )
        try:
            validated = providers.validate_gateway_url(raw_url)
        except providers.ProviderConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        db_manager.set_setting(providers.SETTING_GATEWAY_URL, validated)

    probe = providers.detect_provider(provider_id)
    if not probe.available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider_id}' is not usable on this machine: {probe.detail}",
        )

    if provider_id in DIRECT_PROVIDERS:
        candidate_model = payload.model_id
        if not candidate_model and "PYTEST_CURRENT_TEST" not in os.environ:
            candidate_model = db_manager.get_setting(model_setting(provider_id)) or DEFAULT_PROVIDER_MODEL.get(provider_id)
        try:
            model = validate_model(candidate_model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db_manager.set_setting(model_setting(provider_id), model)

    if payload.provider_models:
        for pid, mid in payload.provider_models.items():
            if pid in DIRECT_PROVIDERS and mid and mid.strip():
                try:
                    db_manager.set_setting(model_setting(pid), validate_model(mid))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.enabled_providers is not None:
        enabled_set = set(payload.enabled_providers) | {provider_id}
        for pid in DIRECT_PROVIDERS:
            db_manager.set_setting(enabled_setting(pid), "true" if pid in enabled_set else "false")
    elif provider_id in DIRECT_PROVIDERS:
        db_manager.set_setting(enabled_setting(provider_id), "true")

    db_manager.set_setting(providers.SETTING_PROVIDER, provider_id)
    db_manager.set_setting(providers.SETTING_SETUP_COMPLETED, "true")
    logger.info(f"Runtime provider default set to '{provider_id}'")

    return _build_setup_state()


@router.post("/detect", response_model=SetupStateResponse)
async def redetect_providers():
    """Re-probe providers — used by the 'Re-scan' action in the setup prompt."""
    return _build_setup_state()
