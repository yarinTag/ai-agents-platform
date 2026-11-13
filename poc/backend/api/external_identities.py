"""Personal identity linking API and narrowly scoped provider proof receiver."""
import logging
import re
import sqlite3
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.concurrency import run_in_threadpool

from integrations.identity_proofs import InvalidProof, verify
from storage import external_identities as store
from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources

router = APIRouter(prefix="/external-identities")
proof_router = APIRouter()
logger = logging.getLogger(__name__)


class ConfirmLink(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    subject: Annotated[str, Field(pattern=r"^(?:[1-9][0-9]{0,19}|[UW][A-Z0-9]{2,31})$")]


class RotateSecret(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    secret: SecretStr
    team_id: str | None = None
    app_id: str | None = None


def _outcome(request, operation, code, *, organization_id=None, connector_id=None):
    correlation = getattr(request.state, "correlation_id", "") or ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", correlation):
        correlation = f"req_{uuid4().hex}"
    level = logging.ERROR if code == "STORAGE_UNAVAILABLE" else logging.DEBUG if operation == "proof" and code != "OK" else logging.INFO
    logger.log(level, "external_identity operation=%s code=%s correlation_id=%s organization_id=%s connector_id=%s",
               operation, code, correlation, organization_id, connector_id)
    return correlation


def _personal(request, db):
    actor = load_actor(request, db)
    if not actor.user_id:
        raise HTTPException(403, "A signed-in personal account is required.")
    return actor


def _call(request, operation, action, *args, connector_id=None):
    try:
        result = action(*args)
    except InvalidProof as exc:
        code = str(exc)
        status = {
            "RATE_LIMITED": 429, "IDENTITY_CONFLICT": 409, "PROOF_MISMATCH": 409,
            "CHALLENGE_REPLAY": 409, "CHALLENGE_EXPIRED": 410, "PROVIDER_ROTATED": 409,
            "PROVIDER_UNCONFIGURED": 503,
        }.get(code, 404)
    except (sqlite3.Error, ValueError, RecursionError):
        code, status = "STORAGE_UNAVAILABLE", 503
    except PermissionError:
        code, status = "ADMIN_REQUIRED", 403
    else:
        _outcome(request, operation, "OK", organization_id=args[1], connector_id=connector_id)
        return result
    correlation = _outcome(request, operation, code, organization_id=args[1], connector_id=connector_id)
    raise HTTPException(status, {"code": code, "correlation_id": correlation})


@router.get("")
def list_external_identities(request: Request, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    return _call(request, "list", store.list_for_user, db, actor.organization_id, actor.user_id)


@router.put("/connectors/{connector_id}/secret", status_code=204)
def rotate_identity_secret(connector_id: str, request: Request, payload: dict, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    actor.require(level=4)
    Resources(actor).require("connector", connector_id)
    try:
        data = RotateSecret.model_validate(payload)
    except ValueError:
        raise HTTPException(422, "Invalid identity provider configuration.") from None
    _call(request, "rotate", store.rotate_secret, db, actor.organization_id, actor.user_id, connector_id,
          data.secret.get_secret_value(), data.team_id, data.app_id, connector_id=connector_id)
    return Response(status_code=204)


@router.post("/connectors/{connector_id}/challenges", status_code=201)
def issue_identity_challenge(connector_id: str, request: Request, response: Response, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    Resources(actor).require("connector", connector_id)
    response.headers["Cache-Control"] = "no-store"
    return _call(request, "issue", store.issue, db, actor.organization_id, actor.user_id, connector_id, actor.selected_department,
                 connector_id=connector_id)


@router.get("/challenges/{challenge_id}")
def read_identity_challenge(challenge_id: str, request: Request, response: Response, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    response.headers["Cache-Control"] = "no-store"
    return _call(request, "status", store.status, db, actor.organization_id, actor.user_id, challenge_id)


@router.post("/challenges/{challenge_id}/confirm", status_code=201)
def confirm_identity_challenge(challenge_id: str, payload: ConfirmLink, request: Request, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    return _call(request, "confirm", store.confirm, db, actor.organization_id, actor.user_id, challenge_id, payload.subject)


@router.delete("/{link_id}", status_code=204)
def unlink_external_identity(link_id: str, request: Request, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    _call(request, "unlink", store.unlink, db, actor.organization_id, actor.user_id, link_id)
    return Response(status_code=204)


@router.get("/connectors")
def list_identity_connectors(request: Request, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    resources = Resources(actor)
    with db._get_connection() as conn:
        connectors = []
        for connector in db.list_mcp_connectors(organization_id=actor.organization_id):
            if not resources.allows("connector", connector.id):
                continue
            if not actor.admin:
                departments = [actor.selected_department] if actor.selected_department else actor.departments
                grants = (db.get_department_mcp_access(dept, connector.id) for dept in departments)
                if not any(g and g.is_active and g.organization_id in (None, actor.organization_id) for g in grants):
                    continue
            try:
                _, provider, _, _ = store.connector_settings(conn, connector.id, actor.organization_id)
            except InvalidProof:
                continue
            connectors.append({"id": connector.id, "name": connector.name, "provider": provider})
    return connectors


@router.get("/departments/{department_id}/links")
def list_managed_identities(
    department_id: str, request: Request,
    after: Annotated[str | None, Query(pattern=r"^idl_[a-f0-9]{32}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db=Depends(get_db_manager),
):
    actor = _personal(request, db)
    Resources(actor).require("department", department_id, 3)
    rows = _call(request, "managed_list", store.list_managed, db, actor.organization_id, actor.user_id,
                 department_id, after or "", limit + 1)
    return {"links": [{**row, "can_revoke": bool(row["can_revoke"])} for row in rows[:limit]],
            "next_after": rows[limit - 1]["id"] if len(rows) > limit else None}


@router.delete("/departments/{department_id}/links/{link_id}", status_code=204)
def revoke_managed_identity(department_id: str, link_id: str, request: Request, db=Depends(get_db_manager)):
    actor = _personal(request, db)
    Resources(actor).require("department", department_id, 3)
    _call(request, "managed_revoke", store.revoke_managed, db, actor.organization_id, actor.user_id,
          department_id, link_id)
    return Response(status_code=204)


def _record_verified_request(db, connector_id, raw, headers):
    with db._get_connection() as conn:
        _, provider, settings, version = store.connector_settings(conn, connector_id)
    subject, code = verify(provider, raw, headers, settings, int(time.time()))
    store.record_proof(db, connector_id, version, subject, code)


@proof_router.post("/api/v1/external-identity-proofs/{connector_id}", include_in_schema=False)
async def receive_identity_proof(connector_id: str, request: Request, db=Depends(get_db_manager)):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 16384:
            raise HTTPException(413, "Provider proof exceeds the request limit.")
        raw.extend(chunk)
    try:
        await run_in_threadpool(_record_verified_request, db, connector_id, bytes(raw), request.headers)
    except InvalidProof as exc:
        _outcome(request, "proof", str(exc))
        # Verified retries and expired codes must not expose challenge state to the provider.
        if str(exc) not in {"CHALLENGE_UNAVAILABLE", "CHALLENGE_REPLAY", "CHALLENGE_EXPIRED",
                           "PROVIDER_ROTATED", "USER_UNAVAILABLE"}:
            raise HTTPException(403, "Provider proof rejected.") from None
    except (sqlite3.Error, ValueError, RecursionError):
        _outcome(request, "proof", "STORAGE_UNAVAILABLE")
        raise HTTPException(503, "Provider proof unavailable.") from None
    else:
        _outcome(request, "proof", "OK", connector_id=connector_id)
    return Response(status_code=200)
