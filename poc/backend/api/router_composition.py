"""Compose route-only modules before the application applies their URL prefix."""
from fastapi import APIRouter


def compose_routers(*routers: APIRouter) -> APIRouter:
    """Preserve both empty and slash aliases until the nonempty mount prefix exists.

    FastAPI include_router rejects an empty child path with an empty prefix.
    Flatten route-only modules here; the application includes this router with
    the actual domain prefix, cloning route metadata and applying auth guards.
    Child modules must not define router-wide lifecycle hooks or dependencies.
    """
    return APIRouter(routes=[route for router in routers for route in router.routes])
