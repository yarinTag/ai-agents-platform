"""
Runtime provider selection API.

Backs the first-run setup prompt: reports which providers this machine can
actually use, and persists the operator's choice as the platform default.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import db_manager, runtime_adapter, runtime_providers as providers

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
    # Only needed for custom_gateway. Non-secret; the matching token is read
    # from PLATFORM_GATEWAY_AUTH_TOKEN at runtime and never stored.
    gateway_base_url: Optional[str] = None


def _build_setup_state() -> SetupStateResponse:
    selected = db_manager.get_setting(providers.SETTING_PROVIDER)
    setup_completed = db_manager.get_setting(providers.SETTING_SETUP_COMPLETED) == "true"
    effective = runtime_adapter.resolve_runtime_provider()

    detected = providers.detect_providers()
    return SetupStateResponse(
        setup_completed=setup_completed,
        selected_provider=selected,
        effective_provider=effective,
        suggested_provider=providers.suggest_default_provider(),
        providers=[
            ProviderStatusResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                available=s.available,
                detail=s.detail,
                requires_config=s.requires_config,
                config=s.config,
                is_selected=(s.id == selected),
            )
            for s in detected
        ],
    )


@router.get("/", response_model=SetupStateResponse)
@router.get("", response_model=SetupStateResponse)
async def get_runtime_setup_state():
    """
    Report provider availability on this machine plus the current selection.

    The dashboard calls this on load; when `setup_completed` is false it shows
    the first-run provider prompt.
    """
    return _build_setup_state()


@router.put("/selection", response_model=SetupStateResponse)
async def select_runtime_provider(payload: ProviderSelectionRequest):
    """Persist the platform-default runtime provider chosen by the operator."""
    provider_id = payload.provider_id.strip()
    if provider_id not in providers.ALL_PROVIDER_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown runtime provider '{provider_id}'. "
                f"Expected one of: {', '.join(providers.ALL_PROVIDER_IDS)}."
            ),
        )

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

    # Reject a selection the machine cannot actually serve, so the failure
    # surfaces here rather than as a confusing mid-run subprocess error.
    probe = providers.detect_provider(provider_id)
    if not probe.available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider_id}' is not usable on this machine: {probe.detail}",
        )

    db_manager.set_setting(providers.SETTING_PROVIDER, provider_id)
    db_manager.set_setting(providers.SETTING_SETUP_COMPLETED, "true")
    logger.info(f"Runtime provider default set to '{provider_id}'")

    return _build_setup_state()


@router.post("/detect", response_model=SetupStateResponse)
async def redetect_providers():
    """Re-probe providers — used by the 'Re-scan' action in the setup prompt."""
    return _build_setup_state()
