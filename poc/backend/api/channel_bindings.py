"""Tenant-scoped channel registry configuration. No provider requests."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from integrations.channel_providers import CHANNEL_PROVIDERS
from integrations.channel_ingress import INGRESS_ADAPTERS
from storage import channel_bindings as store

from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources


router = APIRouter(prefix="/channel-bindings")
Provider = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=150)]
Revision = Annotated[int, Field(ge=1)]
Department = Annotated[str | None, Query(min_length=1, max_length=150)]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ChannelUses(StrictModel):
    send_notifications: bool = False
    trigger_workflows: bool = False
    approve_decisions: bool = False


class CreateChannelBinding(StrictModel):
    department_id: Identifier | None = None
    connector_id: Identifier
    provider: Provider
    channel_id: Identifier
    uses: ChannelUses = Field(default_factory=ChannelUses)

class ReplaceChannelUses(StrictModel):
    expected_revision: Revision
    uses: ChannelUses


class ChannelBinding(StrictModel):
    id: str
    organization_id: str
    department_id: str | None
    connector_id: str
    provider: Provider
    channel_id: str
    channel_name: str | None = None
    uses: ChannelUses
    revision: Revision
    created_at: str
    updated_at: str


class ChannelBindingPage(StrictModel):
    bindings: list[ChannelBinding]
    next_after: str | None


def _scope(request, db, department_id, *, write=False):
    actor = load_actor(request, db)
    if write or department_id is None:
        actor.require(level=4)
        if write and not actor.user_id:
            raise HTTPException(403, "A signed-in organization administrator is required.")
    if department_id is not None:
        Resources(actor).require("department", department_id)
    return actor


def _mutate(action, *args):
    try:
        return action(*args)
    except store.BindingConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def _channel_label(configuration: dict, channel_id: str) -> str | None:
    labels = configuration.get("channel_labels")
    label = labels.get(channel_id) if isinstance(labels, dict) else None
    return label.strip()[:160] or None if isinstance(label, str) else None


@router.get("/catalog")
def get_channel_binding_catalog(request: Request, department_id: Department = None, db=Depends(get_db_manager)):
    actor = _scope(request, db, department_id)
    resources = Resources(actor)
    connectors = []
    for connector in db.list_mcp_connectors(organization_id=actor.organization_id):
        provider = connector.provider.lower()
        adapter = CHANNEL_PROVIDERS.get(provider)
        if adapter is None:
            continue
        if not actor.admin:
            grant = db.get_department_mcp_access(department_id, connector.id)
            if not grant or not grant.is_active or grant.organization_id not in (None, actor.organization_id):
                continue
            if not resources.allows("connector", connector.id):
                continue
        configuration = connector.configuration or {}
        channel_ids = adapter.configured_ids(configuration) if actor.admin else []
        channel_labels = {
            channel_id: label for channel_id in channel_ids
            if (label := _channel_label(configuration, channel_id)) is not None
        }
        connectors.append({
            "id": connector.id, "name": connector.name, "provider": provider, "status": connector.status,
            "channel_ids": channel_ids, "channel_labels": channel_labels,
        })
    return {
        "providers": {key: {
            "label": adapter.label,
            "ingress_supported": key in INGRESS_ADAPTERS,
            "configurable_uses": list(store.USES),
            "runtime_supported_uses": adapter.runtime_supported_uses,
        } for key, adapter in CHANNEL_PROVIDERS.items()},
        "connectors": connectors,
    }


@router.get("", response_model=ChannelBindingPage)
def list_channel_bindings(
    request: Request,
    department_id: Department = None,
    after: Annotated[str | None, Query(pattern=r"^chb_[0-9a-f]{32}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db=Depends(get_db_manager),
):
    actor = _scope(request, db, department_id)
    rows = store.list_bindings(db, actor.organization_id, department_id, after or "", limit + 1)
    connectors = {connector.id: connector for connector in db.list_mcp_connectors(organization_id=actor.organization_id)}
    for row in rows[:limit]:
        connector = connectors.get(row["connector_id"])
        if connector and connector.provider.lower() == row["provider"]:
            row["channel_name"] = _channel_label(connector.configuration or {}, row["channel_id"])
    return {"bindings": rows[:limit], "next_after": rows[limit - 1]["id"] if len(rows) > limit else None}


@router.post("", status_code=201, response_model=ChannelBinding)
def create_channel_binding(payload: CreateChannelBinding, request: Request, db=Depends(get_db_manager)):
    actor = _scope(request, db, payload.department_id, write=True)
    return _mutate(store.create, db, actor.organization_id, payload.department_id, actor.user_id,
                   payload.connector_id, payload.provider, payload.channel_id, payload.uses.model_dump())


@router.put("/{binding_id}/uses", response_model=ChannelBinding)
def replace_channel_binding_uses(
    binding_id: str, payload: ReplaceChannelUses, request: Request,
    department_id: Department = None, db=Depends(get_db_manager),
):
    actor = _scope(request, db, department_id, write=True)
    return _mutate(store.change, db, actor.organization_id, department_id, actor.user_id,
                   binding_id, payload.expected_revision, payload.uses.model_dump())


@router.delete("/{binding_id}", status_code=204)
def delete_channel_binding(
    binding_id: str, request: Request, expected_revision: Annotated[int, Query(ge=1)],
    department_id: Department = None, db=Depends(get_db_manager),
):
    actor = _scope(request, db, department_id, write=True)
    _mutate(store.change, db, actor.organization_id, department_id, actor.user_id, binding_id, expected_revision)
    return Response(status_code=204)
