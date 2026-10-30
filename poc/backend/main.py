"""
Main FastAPI application for the AI Agents Platform Dashboard API.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .router_registry import register_routers
from .capabilities import capabilities

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
    try:
        await init_services()
        yield
    finally:
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

# Optional module imports are isolated by the composition root.
register_routers(app)


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

@app.get("/api/v1/capabilities", dependencies=auth_deps)
async def capability_status():
    """Report sanitized availability separately from execution state."""
    return {"capabilities": capabilities.snapshot()}


@app.get("/health/ready")
async def core_readiness():
    """Required-core readiness; optional inference/provider availability is separate."""
    from .dependencies import get_db_manager
    from fastapi.responses import JSONResponse
    try:
        with get_db_manager()._get_connection() as connection:
            connection.execute("SELECT 1")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}
