"""Verified provider ingress and organization-scoped operational diagnostics."""
import os
import sqlite3
import time
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from integrations.channel_ingress import INGRESS_ADAPTERS, Handshake, IdentityProof, verify_event
from integrations.identity_proofs import InvalidProof, configuration, verify
from integrations.ingress_tls import check_tls
from storage import channel_ingress as inbox
from storage import external_identities as identities

from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources

router = APIRouter(prefix="/channel-ingress")
receiver = APIRouter()
MAX_BODY = 65536
FAILURE_CODES = {"INVALID_PROOF", "INVALID_EVENT", "RATE_LIMITED", "BODY_TOO_LARGE", "QUEUE_FULL", "STORAGE_UNAVAILABLE"}


class IngressTest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    verify_tls: bool = False


def _receive(db, connector_id, raw, headers):
    with db._get_connection() as conn:
        _, provider, settings, version = identities.connector_settings(conn, connector_id)
    now = int(time.time())
    event = verify_event(provider, raw, headers, settings, now)
    if isinstance(event, IdentityProof):
        subject, code = verify(provider, raw, headers, settings, now)
        try:
            identities.record_proof(db, connector_id, version, subject, code)
        except InvalidProof as exc:
            if str(exc) not in {"CHALLENGE_UNAVAILABLE", "CHALLENGE_REPLAY", "CHALLENGE_EXPIRED",
                               "PROVIDER_ROTATED", "USER_UNAVAILABLE", "CONNECTOR_UNAVAILABLE"}:
                raise
        return Response(status_code=200)
    if isinstance(event, Handshake):
        return JSONResponse({"challenge": event.challenge})
    if event is not None:
        accepted = inbox.stage(db, connector_id, version, event)
        return Response(status_code=202 if accepted else 200)
    return Response(status_code=200)


def _failure(db, connector_id, code):
    if code not in FAILURE_CODES:
        return
    try:
        inbox.record_failure(db, connector_id, code)
    except sqlite3.Error:
        pass  # The original provider-facing error remains authoritative.


@receiver.post("/api/v1/channel-ingress/{connector_id}", include_in_schema=False)
async def receive_channel_event(connector_id: str, request: Request, db=Depends(get_db_manager)):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_BODY:
            await run_in_threadpool(_failure, db, connector_id, "BODY_TOO_LARGE")
            raise HTTPException(413, "Provider event exceeds the request limit.")
        raw.extend(chunk)
    try:
        return await run_in_threadpool(_receive, db, connector_id, bytes(raw), request.headers)
    except InvalidProof as exc:
        code = str(exc)
        await run_in_threadpool(_failure, db, connector_id, code)
        if code in {"RATE_LIMITED", "QUEUE_FULL"}:
            raise HTTPException(429, "Provider event capacity reached.", headers={"Retry-After": "60"}) from None
        if code == "INVALID_EVENT":
            raise HTTPException(400, "Provider event rejected.") from None
        raise HTTPException(403, "Provider proof rejected.") from None
    except (sqlite3.Error, ValueError, RecursionError):
        await run_in_threadpool(_failure, db, connector_id, "STORAGE_UNAVAILABLE")
        raise HTTPException(503, "Provider event unavailable.") from None


def _webhook_url(connector_id):
    raw = os.getenv("PLATFORM_INGRESS_PUBLIC_URL", "").strip().rstrip("/")
    if any(ord(char) < 33 or ord(char) > 126 for char in raw) or "\\" in raw:
        return None
    try:
        parsed = urlsplit(raw)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path or parsed.port == 0):
            return None
    except ValueError:
        return None
    return f"{raw}/api/v1/channel-ingress/{quote(connector_id, safe='')}"


def _scope(request, db, connector_id):
    actor = load_actor(request, db)
    actor.require(level=4)
    connector = Resources(actor).require("connector", connector_id)
    provider = connector.provider.lower()
    if provider not in INGRESS_ADAPTERS:
        raise HTTPException(404, "Channel connector unavailable.")
    try:
        configuration(provider, connector.configuration or {})
        secret_configured = True
    except InvalidProof:
        secret_configured = False
    webhook_url = _webhook_url(connector_id)
    return actor, {
        "provider": provider,
        "webhook_url": webhook_url,
        "secret_configured": secret_configured,
        "https_configured": webhook_url is not None,
        "ssl_status": "UNVERIFIED",
        "connector_connected": connector.status == "CONNECTED",
    }


@router.get("/{connector_id}/diagnostics")
def get_channel_ingress_diagnostics(connector_id: str, request: Request, db=Depends(get_db_manager)):
    actor, status = _scope(request, db, connector_id)
    try:
        return {**status, **inbox.diagnostics(db, actor.organization_id, connector_id)}
    except sqlite3.Error:
        raise HTTPException(503, "Channel diagnostics unavailable.") from None


@router.post("/{connector_id}/test")
def test_channel_ingress_configuration(connector_id: str, request: Request,
                                       payload: IngressTest | None = None, db=Depends(get_db_manager)):
    """Check local prerequisites and optionally validate the public endpoint certificate."""
    _, status = _scope(request, db, connector_id)
    try:
        with db._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE channel_ingress_outbox SET attempts=attempts WHERE 0")
            conn.rollback()
        storage_ready = True
    except sqlite3.Error:
        storage_ready = False
    checks = {key: status[key] for key in ("https_configured", "secret_configured", "connector_connected")}
    checks["storage_ready"] = storage_ready
    tls_status, live_request = "UNVERIFIED", False
    if payload and payload.verify_tls and status["webhook_url"]:
        tls_status, live_request = check_tls(status["webhook_url"])
    return {"status": "READY" if all(checks.values()) else "BLOCKED", "checks": checks,
            "live_request": live_request, "tls_status": tls_status}
