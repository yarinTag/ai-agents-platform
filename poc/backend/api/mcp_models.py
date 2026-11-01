"""Mcp: models ownership."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ConnectorInstallRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    capabilities: Optional[List[str]] = None
    custom_command: Optional[str] = None
    organization_id: Optional[str] = None



class ConnectorUpdateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    capabilities: Optional[List[str]] = None
    organization_id: Optional[str] = None



class PermissionGrantRequest(BaseModel):
    agent_id: str
    connector_id: str
    tool_id: Optional[str] = None



class PermissionRevokeRequest(BaseModel):
    agent_id: str
    connector_id: str
    tool_id: Optional[str] = None



class ResourceDiscoveryRequest(BaseModel):
    provider: str
    connector_id: Optional[str] = None
    token: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None



class ChannelTestMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(pattern="^(telegram|slack)$")
    connector_id: Optional[str] = None
    channel_id: str = Field(min_length=1, max_length=200)
    message: str = Field(default="Test notification from AI Agents Platform", min_length=1, max_length=3500)

