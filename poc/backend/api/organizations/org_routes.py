"""
Multi-tenant Organization Administration Routes.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import uuid

from ...dependencies import get_db_manager, DatabaseManager
from .schemas import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationResponse,
    UserResponse,
)

router = APIRouter()


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    req: OrganizationCreateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new tenant organization."""
    existing = db.get_organization_by_slug(req.slug)
    if existing:
        raise HTTPException(status_code=400, detail=f"Organization with slug '{req.slug}' already exists")

    org_id = req.id or f"org_{uuid.uuid4().hex[:10]}"
    org = db.create_organization(
        id=org_id,
        name=req.name,
        slug=req.slug,
        domain=req.domain,
        settings_json=req.settings_json or "{}"
    )
    return OrganizationResponse(**org.to_dict())


@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all tenant organizations."""
    orgs = db.list_organizations()
    return [OrganizationResponse(**o.to_dict()) for o in orgs]


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get an organization by ID."""
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse(**org.to_dict())


@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: str,
    req: OrganizationUpdateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update organization settings."""
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    updated = db.update_organization(
        id=org_id,
        name=req.name,
        slug=req.slug,
        domain=req.domain,
        settings_json=req.settings_json
    )
    return OrganizationResponse(**updated.to_dict())


@router.get("/organizations/{org_id}/users", response_model=List[UserResponse])
def list_organization_users(
    org_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all enterprise users registered under an organization."""
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{org_id}' not found")

    users = db.list_users_by_organization(org_id)
    return [UserResponse(**u.to_dict()) for u in users]
