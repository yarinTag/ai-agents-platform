"""
Model discovery and provider configuration API endpoints.
Provides dynamic list of available AI models filtered by the configured API providers.
"""

from fastapi import APIRouter, Query, Request
from typing import List, Optional
from pydantic import BaseModel

from runtime.model_policy import model_policy_resolver
from runtime.direct_config import (
    DIRECT_PROVIDERS,
    DEFAULT_PROVIDER_MODEL,
    PROVIDER_MODELS,
    enabled_setting,
    model_setting,
)

router = APIRouter()


class ModelOption(BaseModel):
    id: str
    name: str
    provider: str
    description: str
    context_window: int
    is_default: bool = False
    tier: Optional[str] = None


class ModelCategory(BaseModel):
    provider: str
    models: List[ModelOption]


class ModelTierOption(BaseModel):
    id: str
    tier: str
    name: str
    description: str
    min_context_window: int
    requires_reasoning: bool
    requires_tools: bool


# Legacy fallback catalog for unit tests using non-direct provider IDs
AVAILABLE_MODELS: List[ModelOption] = [
    ModelOption(
        id="default",
        name="Platform Default",
        provider="Anthropic",
        description="System configured default model",
        context_window=200000,
        is_default=True,
        tier="default",
    ),
    *[ModelOption(**m) for m in PROVIDER_MODELS["direct_anthropic"]],
    *[ModelOption(**m) for m in PROVIDER_MODELS["direct_nvidia"]],
]


@router.get("/tiers", response_model=List[ModelTierOption])
async def list_model_tiers():
    """List all logical model capability tiers (decoupled from vendor model IDs)."""
    return [ModelTierOption(**t) for t in model_policy_resolver.list_tiers()]


def _models_for_provider(provider_id: str, db_manager) -> List[ModelOption]:
    provider_name = DIRECT_PROVIDERS[provider_id][0]
    catalog = PROVIDER_MODELS.get(provider_id, [])
    items: List[ModelOption] = [ModelOption(**m) for m in catalog]
    saved_model = (db_manager.get_setting(model_setting(provider_id)) or "").strip()
    if saved_model and not any(m.id == saved_model for m in items):
        items.insert(
            0,
            ModelOption(
                id=saved_model,
                name=saved_model,
                provider=provider_name,
                description="Configured direct API model; availability depends on provider access",
                context_window=0,
                tier="developer",
            ),
        )
    return items


@router.get("/", response_model=List[ModelOption])
@router.get("", response_model=List[ModelOption])
async def list_models(request: Request, provider: Optional[str] = Query(default=None)):
    """List available models based on the configured runtime provider(s)."""
    from ..dependencies import db_manager, runtime_providers as providers

    from .runtimes import organization_settings
    db_manager = organization_settings(request)
    if provider and provider in DIRECT_PROVIDERS and not db_manager.has_credential(provider):
        return []
    if provider and provider in DIRECT_PROVIDERS:
        default_model = db_manager.get_setting(model_setting(provider)) or DEFAULT_PROVIDER_MODEL.get(provider, "")
        provider_name = DIRECT_PROVIDERS[provider][0]
        return [
            ModelOption(
                id="default",
                name=f"Platform API default ({default_model})" if default_model else "Platform API default",
                provider=provider_name,
                description="Uses the model selected in Runtime settings",
                context_window=0,
                is_default=True,
                tier="default",
            ),
            *_models_for_provider(provider, db_manager),
        ]

    active_provider = db_manager.get_setting(providers.SETTING_PROVIDER)
    if active_provider not in DIRECT_PROVIDERS or not db_manager.has_credential(active_provider):
        return []
    if active_provider in DIRECT_PROVIDERS:
        active_name = DIRECT_PROVIDERS[active_provider][0]
        default_model = db_manager.get_setting(model_setting(active_provider)) or DEFAULT_PROVIDER_MODEL.get(active_provider, "")
        result: List[ModelOption] = [
            ModelOption(
                id="default",
                name="Platform API default",
                provider=active_name,
                description=f"Uses the model selected in Runtime settings ({default_model})" if default_model else "Uses the model selected in Runtime settings",
                context_window=0,
                is_default=True,
                tier="default",
            )
        ]

        enabled_providers = [active_provider]
        for pid in DIRECT_PROVIDERS:
            if pid != active_provider:
                if db_manager.get_setting(enabled_setting(pid)) == "true" and db_manager.has_credential(pid):
                    enabled_providers.append(pid)

        seen_ids = {"default"}
        for pid in enabled_providers:
            for item in _models_for_provider(pid, db_manager):
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    result.append(item)
        return result

    return list(AVAILABLE_MODELS)
