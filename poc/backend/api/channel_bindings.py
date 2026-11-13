"""Tenant-scoped channel registry configuration. No provider requests."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from integrations.tool_definitions import valid_channel
from storage import channel_bindings as store

from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources


router = APIRouter(prefix="/channel-bindings")
Provider = Literal["telegram", "slack"]
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
    channel_id: Annotated[str, Field(min_length=1, max_length=32)]
    uses: ChannelUses = Field(default_factory=ChannelUses)

    @model_validator(mode="after")
    def validate_channel(self):
        # Telegram usernames can be reassigned. Registry identities use numeric IDs.
        if self.channel_id.startswith("@") or not valid_channel(self.provider, self.channel_id):
            raise ValueError("Use an exact numeric Telegram chat ID or a Slack channel ID.")
        return self


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
        Resources(actor).require("department", department_id, 3)
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
