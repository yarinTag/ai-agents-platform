"""Explicit admin channel test; exact tenant connector and allowlisted destination."""
from datetime import datetime
import hashlib
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from ..dependencies import get_db_manager, DatabaseManager
from .mcp_models import ChannelTestMessageRequest
from integrations.scoped_channels import send_message
from integrations.tool_definitions import ToolAccessError, resource_values, valid_channel

router = APIRouter()


@router.post("/test-channel-message")
def test_channel_message(req: ChannelTestMessageRequest, request: Request,
                         db: DatabaseManager = Depends(get_db_manager)):
    claims = getattr(request.state, "user", None) or {}
    def authorize():
        user = db.get_user(claims.get("sub"))
        if not user or user.status != "ACTIVE" or user.role != "ORG_ADMIN" or user.organization_id != claims.get("org_id"):
            raise HTTPException(403, "An active organization administrator must send integration tests.")
        return user
    user = authorize()
    if req.connector_id:
        connector = db.get_mcp_connector(req.connector_id)
    else:
        candidates = [c for c in db.list_mcp_connectors(organization_id=user.organization_id)
                      if c.organization_id == user.organization_id and c.provider == req.provider]
        if len(candidates) != 1:
            raise HTTPException(400, "Select the exact connector to test.")
        connector = candidates[0]
    if not connector or connector.organization_id != user.organization_id or connector.provider != req.provider:
        raise HTTPException(404, "Channel connector not found in this organization.")

    def check_target():
        authorize()
        current = db.get_mcp_connector(connector.id)
        if not current or current.organization_id != user.organization_id or current.provider != req.provider or current.status != "CONNECTED":
            raise HTTPException(409, "Save and connect this integration before testing.")
        if not valid_channel(req.provider, req.channel_id) or req.channel_id not in resource_values(current.configuration or {}, "channels"):
            raise HTTPException(400, "Save this exact chat ID or public @channel username in the connector's allowed channels before testing.")
        return current

    connector = check_target()
    call_id = "call_test_" + uuid.uuid4().hex
    agents = db.list_agents(organization_id=user.organization_id)
    record = {"id": call_id, "connector_id": connector.id,
              "tool_id": f"tool_{req.provider}_send_message", "agent_id": agents[0].id if agents else None,
              "arguments": {"channel_id": req.channel_id, "text_sha256": hashlib.sha256(req.message.encode()).hexdigest()},
              "status": "STARTED", "started_at": datetime.now().isoformat()}
    if agents:
        db.save_mcp_tool_call(record)
    try:
        receipt = send_message(connector, req.channel_id, req.message, check_target)
    except (ToolAccessError, HTTPException) as error:
        detail = error.detail if isinstance(error, HTTPException) else str(error)
        if agents:
            record.update(status="FAILED", error=detail, completed_at=datetime.now().isoformat())
            db.save_mcp_tool_call(record)
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(400, detail=detail + " For Telegram: start this bot in a private chat, or add it to the intended group/channel with permission to post. Verify the selected destination and bot token. Delivery may be uncertain; tests are never automatically retried.") from error
    if agents:
        record.update(status="COMPLETED", result=json.dumps(receipt), completed_at=datetime.now().isoformat())
        db.save_mcp_tool_call(record)
    return {"status": "success", "provider": req.provider, **receipt,
            "call_id": call_id, "timestamp": datetime.now().isoformat()}
