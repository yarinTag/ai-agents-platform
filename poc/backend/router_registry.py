"""Composition-root router descriptors and optional import boundaries."""

from importlib import import_module
import logging

from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRoute, request_response
from .security.request_policy import authorize_request
from .security.response_policy import protect_response

from .capabilities import capabilities
from .security import authenticate_request

logger = logging.getLogger(__name__)

# Domain, relative module, URL prefix, required core.
ROUTERS = (
    ("agents", ".api.agents", "/api/v1/agents", False),
    ("projects", ".api.projects", "/api/v1/projects", False),
    ("skills", ".api.skills", "/api/v1/skills", False),
    ("tasks", ".api.tasks", "/api/v1/tasks", False),
    ("events", ".events.router", "/api/v1/events", False),
    ("templates", ".api.templates", "/api/v1/templates", False),
    ("models", ".api.models", "/api/v1/models", False),
    ("runtimes", ".api.runtimes", "/api/v1/runtimes", False),
    ("audit", ".api.audit", "/api/v1/audit", False),
    ("auth-audit", ".api.audit", "/api/v1/auth", False),
    ("scheduler", ".scheduler.router", "/api/v1/schedules", False),
    ("approvals", ".approvals.router", "/api/v1/approvals", False),
    ("chat", ".chat.router", "/api/v1/chat", False),
    ("memory", ".memory.router", "/api/v1/projects", False),
    ("war-room", ".war_room.router", "/api/v1/war-room", False),
    ("messages", ".messages.router", "/api/v1/messages", False),
    ("teams", ".teams.router", "/api/v1/teams", False),
    ("filesystem", ".api.filesystem", "/api/v1/fs", False),
    ("workflows", ".api.workflows", "/api/v1/workflows", False),
    ("queue-api", ".queue.router", "/api/v1/queue", False),
    ("mcp", ".api.mcp", "/api/v1/mcp", False),
    ("organizations", ".api.organizations", "/api/v1", True),
)


def _availability_guard(name):
    def require_available():
        capabilities.require(name)
    return require_available


def _register_unavailable(app, name, prefix):
    async def unavailable(request: Request):
        raise HTTPException(
            status_code=503,
            detail={"code": "CAPABILITY_UNAVAILABLE", "capability": name},
        )
    # Shared prefixes must never mask another capability's routes.
    if name == "memory":
        paths = (prefix + "/{project_id}/memories", prefix + "/{project_id}/memories/{memory_id}", prefix + "/{project_id}/context-prompt")
    elif name == "auth-audit":
        paths = (prefix + "/status", prefix + "/logs")
    elif name == "projects":
        paths = (prefix, prefix + "/", prefix + "/{project_id}", prefix + "/{project_id}/")
    else:
        paths = (prefix, prefix + "/{remaining_path:path}")
    for path in paths:
        app.add_api_route(
            path, unavailable,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
            dependencies=[Depends(authenticate_request)],
            include_in_schema=False,
        )


def register_routers(app):
    for name, module_name, prefix, required in ROUTERS:
        if required and not capabilities.enabled(name):
            raise ValueError(f"Required core capability cannot be disabled: {name}")
        if not capabilities.enabled(name) and not required:
            capabilities.mark(name, "DISABLED")
            _register_unavailable(app, name, prefix)
            continue
        before = len(app.routes)
        try:
            router = import_module(module_name, __package__).router
            before = len(app.routes)
            app.include_router(
                router, prefix=prefix, tags=[name],
                dependencies=[Depends(authenticate_request), Depends(authorize_request), Depends(_availability_guard(name))],
            )
            for route in app.routes[before:]:
                if isinstance(route, APIRoute):
                    original = route.get_route_handler()
                    def guarded(handler):
                        async def handle(request):
                            response = await handler(request)
                            return protect_response(request, response)
                        return handle
                    route.app = request_response(guarded(original))
            capabilities.mark(name, "READY")
        except Exception:
            # Never leave partially registered routes behind without their policy wrapper.
            if required or len(app.routes) > before:
                raise
            logger.exception("Optional router %s could not be registered", name)
            capabilities.mark(name, "UNAVAILABLE", "Module could not be loaded")
            _register_unavailable(app, name, prefix)
