"""
Main FastAPI application for the AI Agents Platform Dashboard API.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import API routers - using relative imports within the backend package
from .api.agents import router as agents_router
from .api.projects import router as projects_router
from .api.skills import router as skills_router
from .api.tasks import router as tasks_router
from .events.router import router as events_router
from .api.templates import router as templates_router
from .api.models import router as models_router
from .api.audit import router as audit_router
from .scheduler.router import router as schedules_router
from .approvals.router import router as approvals_router
from .chat.router import router as chat_router
from .memory.router import router as memories_router
from .war_room.router import router as war_room_router
from .messages.router import router as messages_router
from .mcp.router import router as mcp_router
from .teams.router import router as teams_router

# Import security layer
from .security import (
    CorrelationIdMiddleware,
    RateLimiterMiddleware,
    authenticate_request,
    http_exception_handler,
    generic_exception_handler,
)

# Import dependencies for startup/shutdown
from .dependencies import init_services, shutdown_services


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_services()
    yield
    # Shutdown
    await shutdown_services()


# Create FastAPI app
app = FastAPI(
    title="AI Agents Platform API",
    description="REST API for managing AI agents, projects, skills, and tasks",
    version="0.1.0",
    lifespan=lifespan
)

# Exception handlers for uniform error structures
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Configure Middlewares (Order: Correlation -> RateLimiter -> CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# Auth dependencies for protected routes
auth_deps = [Depends(authenticate_request)]

# Include API routers
app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"], dependencies=auth_deps)
app.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"], dependencies=auth_deps)
app.include_router(skills_router, prefix="/api/v1/skills", tags=["skills"], dependencies=auth_deps)
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"], dependencies=auth_deps)
app.include_router(events_router, prefix="/api/v1/events", tags=["events"], dependencies=auth_deps)
app.include_router(templates_router, prefix="/api/v1/templates", tags=["templates"], dependencies=auth_deps)
app.include_router(models_router, prefix="/api/v1/models", tags=["models"], dependencies=auth_deps)
app.include_router(schedules_router, prefix="/api/v1/schedules", tags=["schedules"], dependencies=auth_deps)
app.include_router(approvals_router, prefix="/api/v1/approvals", tags=["approvals"], dependencies=auth_deps)
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"], dependencies=auth_deps)
app.include_router(memories_router, prefix="/api/v1/projects", tags=["memories"], dependencies=auth_deps)
app.include_router(war_room_router, prefix="/api/v1/war-room", tags=["war-room"], dependencies=auth_deps)
app.include_router(messages_router, prefix="/api/v1/messages", tags=["messages"], dependencies=auth_deps)
app.include_router(mcp_router, prefix="/api/v1/mcp", tags=["mcp"], dependencies=auth_deps)
app.include_router(teams_router, prefix="/api/v1/teams", tags=["teams"], dependencies=auth_deps)
app.include_router(audit_router, prefix="/api/v1/audit", tags=["audit"])

app.include_router(audit_router, prefix="/api/v1/auth", tags=["auth"])


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