"""Explicit channel delivery endpoint; no simulated success responses."""

from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from ..dependencies import get_db_manager, DatabaseManager
from ..security import get_current_org_id
from .mcp_models import ChannelTestMessageRequest
from integrations.channels import ChannelDeliveryError, deliver_channel_message, find_channel_connector

router = APIRouter()


@router.post("/test-channel-message")
def test_channel_message(req: ChannelTestMessageRequest, request: Request,
                         db: DatabaseManager = Depends(get_db_manager)):
    organization_id = get_current_org_id(request)
    connector = find_channel_connector(db, req.provider, organization_id)
    if connector is None:
        raise HTTPException(status_code=503, detail="Channel connector is unavailable")
    now = datetime.now().isoformat()
    call_id = f"call_test_{uuid.uuid4().hex[:8]}"
    agents = db.list_agents(organization_id=organization_id)
    record = {
        "id": call_id, "connector_id": connector.id,
        "tool_id": f"tool_{req.provider}_send_message",
        "agent_id": agents[0].id if agents else None,
        "arguments": {"channel": req.channel_id, "text": req.message},
        "status": "STARTED", "started_at": now,
    }
    if agents:
        db.save_mcp_tool_call(record)
    try:
        deliver_channel_message(connector, req.channel_id, req.message)
    except ChannelDeliveryError as error:
        if agents:
            record.update(status="FAILED", error=str(error), completed_at=datetime.now().isoformat())
            db.save_mcp_tool_call(record)
        raise HTTPException(status_code=400, detail=str(error)) from error
    if agents:
        record.update(status="COMPLETED", result="Message delivered", completed_at=datetime.now().isoformat())
        db.save_mcp_tool_call(record)
    return {
        "status": "success", "delivery": "delivered", "provider": req.provider,
        "channel_id": req.channel_id, "message": req.message,
        "call_id": call_id, "timestamp": now,
    }
