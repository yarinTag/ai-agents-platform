"""
Runtime provider selection API.

Backs the runtime setup modal: reports which API providers are configured,
allows updating provider API keys/models/enabled states, and persists the
platform default provider.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, SecretStr
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from runtime.direct_config import (
    DIRECT_PROVIDERS,
    DEFAULT_PROVIDER_MODEL,
    PROVIDER_MODELS,
    enabled_setting,
    model_setting,
    validate_model,
)

from ..dependencies import db_manager, runtime_providers as providers

logger = logging.getLogger(__name__)

class CredentialRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                # FastAPI's default 422 includes rejected input, possibly a key.
                raise HTTPException(422, 'Invalid runtime configuration request.') from None
        return safe_handler


router = APIRouter(route_class=CredentialRoute)


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
    api_key: Optional[SecretStr] = None
    enabled_providers: Optional[List[str]] = None
    provider_models: Optional[Dict[str, str]] = None
    provider_keys: Optional[Dict[str, SecretStr]] = None


def organization_settings(request, manage=False):
    from storage.runtime_settings import OrganizationRuntimeSettings
    claims = getattr(request.state, 'user', None) or {}
    org_id = claims.get('org_id')
    user = db_manager.get_user(claims.get('sub')) if claims.get('sub') else None
    service = claims.get('service') in ('api_key', 'open_development')
    if not org_id or (not service and (not user or user.status != 'ACTIVE' or user.organization_id != org_id)):
        raise HTTPException(403, 'An active organization account is required.')
    if manage and not ((user and user.role == 'ORG_ADMIN') or (service and claims.get('role') == 'ORG_ADMIN')):
        raise HTTPException(403, 'An organization administrator must manage provider credentials.')
    try:
        return OrganizationRuntimeSettings(db_manager, org_id)
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from None


def _build_setup_state(settings) -> SetupStateResponse:
    selected = settings.get_setting(providers.SETTING_PROVIDER)
    available = [pid for pid in DIRECT_PROVIDERS if settings.has_credential(pid)]
    effective = selected or (available[0] if available else 'direct_nvidia')
    items = []
    for pid, (name, _, _) in DIRECT_PROVIDERS.items():
        has_key = pid in available
        items.append(ProviderStatusResponse(id=pid, name=name,
            description=f'Direct HTTP API for {name} models.', available=has_key,
            detail='Organization API key configured.' if has_key else 'Configure an API key for this organization.',
            requires_config=True, is_selected=pid == selected,
            config={'model_id': settings.get_setting(model_setting(pid)) or DEFAULT_PROVIDER_MODEL[pid],
                    'models': PROVIDER_MODELS.get(pid, []), 'has_api_key': has_key,
                    'enabled': has_key and (settings.get_setting(enabled_setting(pid)) == 'true' or pid == selected)}))
    return SetupStateResponse(setup_completed=settings.get_setting(providers.SETTING_SETUP_COMPLETED) == 'true' and selected in available,
        selected_provider=selected, effective_provider=effective,
        suggested_provider=available[0] if available else None, providers=items)


@router.get('/', response_model=SetupStateResponse)
@router.get('', response_model=SetupStateResponse)
async def get_runtime_setup_state(request: Request):
    return _build_setup_state(organization_settings(request))


@router.put('/selection', response_model=SetupStateResponse)
async def select_runtime_provider(payload: ProviderSelectionRequest, request: Request):
    settings = organization_settings(request, manage=True)
    pid = payload.provider_id.strip()
    if pid not in DIRECT_PROVIDERS:
        raise HTTPException(400, 'Select a supported Direct API provider.')
    if payload.gateway_base_url is not None:
        raise HTTPException(400, 'Shared gateways are not organization credential providers.')
    credentials = {}
    for provider, value in (payload.provider_keys or {}).items():
        if provider not in DIRECT_PROVIDERS:
            raise HTTPException(400, 'Unknown credential provider.')
        value = value.get_secret_value().strip()
        if value:
            credentials[provider] = value
    if payload.api_key and payload.api_key.get_secret_value().strip():
        credentials[pid] = payload.api_key.get_secret_value().strip()
    if any(len(value.encode()) > 4096 for value in credentials.values()):
        raise HTTPException(400, 'Provider API key exceeds the size limit.')
    updates = {providers.SETTING_PROVIDER: pid, providers.SETTING_SETUP_COMPLETED: 'true'}
    try:
        for provider, model in (payload.provider_models or {}).items():
            if provider not in DIRECT_PROVIDERS:
                raise ValueError('Unknown model provider.')
            updates[model_setting(provider)] = validate_model(model)
        updates[model_setting(pid)] = validate_model(payload.model_id or updates.get(model_setting(pid))
            or settings.get_setting(model_setting(pid)) or DEFAULT_PROVIDER_MODEL[pid])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    enabled = set(payload.enabled_providers or [p for p in DIRECT_PROVIDERS
        if settings.get_setting(enabled_setting(p)) == 'true']) | {pid}
    if enabled - set(DIRECT_PROVIDERS):
        raise HTTPException(400, 'Unknown enabled provider.')
    if any(provider not in credentials and not settings.has_credential(provider) for provider in enabled):
        raise HTTPException(400, 'Configure an organization API key for every enabled provider.')
    updates.update({enabled_setting(provider): 'true' if provider in enabled else 'false' for provider in DIRECT_PROVIDERS})
    try:
        settings.save(updates, credentials, (getattr(request.state, 'user', None) or {}).get('sub'))
    except Exception:
        # Encryption/configuration errors must never echo submitted keys.
        raise HTTPException(503, 'Unable to store organization credentials. Configure PLATFORM_SECRETS_KEY and check storage.') from None
    return _build_setup_state(settings)


@router.delete('/credentials/{provider_id}', response_model=SetupStateResponse)
async def revoke_provider_credential(provider_id: str, request: Request):
    settings = organization_settings(request, manage=True)
    if provider_id not in DIRECT_PROVIDERS:
        raise HTTPException(400, 'Unknown credential provider.')
    settings.revoke(provider_id, (getattr(request.state, 'user', None) or {}).get('sub'))
    return _build_setup_state(settings)


@router.post('/detect', response_model=SetupStateResponse)
async def redetect_providers(request: Request):
    return _build_setup_state(organization_settings(request))
