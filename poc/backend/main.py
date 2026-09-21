"""
Main FastAPI application for the AI Agents Platform Dashboard API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import API routers - using relative imports within the backend package
from .api.agents import router as agents_router
from .api.projects import router as projects_router
from .api.skills import router as skills_router
from .api.tasks import router as tasks_router
from .api.events import router as events_router
from .api.templates import router as templates_router
from .api.models import router as models_router

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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(skills_router, prefix="/api/v1/skills", tags=["skills"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(events_router, prefix="/api/v1/events", tags=["events"])
app.include_router(templates_router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(models_router, prefix="/api/v1/models", tags=["models"])


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