"""
Main FastAPI application for the AI Agents Platform Dashboard API.
Mounts all domain services via the fault-tolerant ServiceRegistry so that
if any individual service is disconnected or disabled, the platform continues
to operate normally.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .security import (
    CorrelationIdMiddleware,
    RateLimiterMiddleware,
    authenticate_request,
    http_exception_handler,
    generic_exception_handler,
)
from .dependencies import init_services, shutdown_services
from shared.service_registry import ServiceSpec, service_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    await init_services()
    yield
    await shutdown_services()


app = FastAPI(
    title="AI Agents Platform API",
    description="REST API for managing AI agents, projects, skills, workflows, and enterprise governance",
    version="0.1.0",
    lifespan=lifespan
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(CorrelationIdMiddleware)

auth_deps = [Depends(authenticate_request)]

PLATFORM_SERVICES = [
    ServiceSpec("agents", "backend.api.agents", "/api/v1/agents", ["agents"]),
    ServiceSpec("projects", "backend.api.projects", "/api/v1/projects", ["projects"]),
    ServiceSpec("skills", "backend.api.skills", "/api/v1/skills", ["skills"]),
    ServiceSpec("tasks", "backend.api.tasks", "/api/v1/tasks", ["tasks"]),
    ServiceSpec("events", "backend.events.router", "/api/v1/events", ["events"]),
    ServiceSpec("templates", "backend.api.templates", "/api/v1/templates", ["templates"]),
    ServiceSpec("models", "backend.api.models", "/api/v1/models", ["models"]),
    ServiceSpec("runtimes", "backend.api.runtimes", "/api/v1/runtimes", ["runtimes"]),
    ServiceSpec("schedules", "backend.scheduler.router", "/api/v1/schedules", ["schedules"]),
    ServiceSpec("approvals", "backend.approvals.router", "/api/v1/approvals", ["approvals"]),
    ServiceSpec("chat", "backend.chat.router", "/api/v1/chat", ["chat"]),
    ServiceSpec("memories", "backend.memory.router", "/api/v1/projects", ["memories"]),
    ServiceSpec("war_room", "backend.war_room.router", "/api/v1/war-room", ["war-room"]),
    ServiceSpec("messages", "backend.messages.router", "/api/v1/messages", ["messages"]),
    ServiceSpec("teams", "backend.teams.router", "/api/v1/teams", ["teams"]),
    ServiceSpec("filesystem", "backend.api.filesystem", "/api/v1/fs", ["filesystem"]),
    ServiceSpec("workflows", "backend.api.workflows", "/api/v1/workflows", ["workflows"]),
    ServiceSpec("mcp", "backend.api.mcp", "/api/v1/mcp", ["mcp"]),
    ServiceSpec("organizations", "backend.api.organizations", "/api/v1", ["organizations", "departments", "mcp-governance"]),
    ServiceSpec("audit", "backend.api.audit", "/api/v1/audit", ["audit"], requires_auth=False),
    ServiceSpec("auth_audit", "backend.api.audit", "/api/v1/auth", ["auth"], requires_auth=False),
]

service_registry.mount_all(app, PLATFORM_SERVICES, auth_dependencies=auth_deps)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Agents Platform API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/services/status", tags=["services"])
async def list_services_status():
    """Inspect pluggable service modules and their isolation/mount status."""
    statuses = service_registry.get_status_list()
    return {
        "total": len(statuses),
        "mounted": sum(1 for s in statuses if s["status"] == "MOUNTED"),
        "disabled": sum(1 for s in statuses if s["status"] == "DISABLED"),
        "degraded": sum(1 for s in statuses if s["status"] == "DEGRADED"),
        "services": statuses,
    }