"""Compatibility exports and router composition for mcp."""

from fastapi import APIRouter
# Bootstrap the single legacy import bridge before domain compatibility exports.
from ..dependencies import get_db_manager
from .mcp_catalog import (CATALOG_MCP_SERVERS, get_catalog)
from .mcp_models import (ConnectorInstallRequest, ConnectorUpdateRequest, PermissionGrantRequest, PermissionRevokeRequest, ResourceDiscoveryRequest, ChannelTestMessageRequest)
from .mcp_connectors import (list_installed_connectors, get_connector, install_connector, update_connector, uninstall_connector, test_connector, list_connector_tools)
from .mcp_permissions import (list_agent_permissions, grant_permission, revoke_permission)
from .mcp_discovery import (discover_resources)
from .mcp_channels import (test_channel_message)

router = APIRouter()
from .mcp_catalog import router as catalog_router
router.include_router(catalog_router)
from .mcp_connectors import router as connectors_router
router.include_router(connectors_router)
from .mcp_permissions import router as permissions_router
router.include_router(permissions_router)
from .mcp_discovery import router as discovery_router
router.include_router(discovery_router)
from .mcp_channels import router as channels_router
router.include_router(channels_router)
