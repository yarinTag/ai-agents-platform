"""Skills: models ownership."""

from typing import Optional
from pydantic import BaseModel, Field


class PluginsConfigRequest(BaseModel):
    source_mode: Optional[str] = "local"
    git_repo: Optional[str] = None
    local_path: Optional[str] = None



class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    project_id: Optional[str] = None  # None for global skills
    source: Optional[str] = "custom"  # "builtin", "local", "git", "custom"
    location: Optional[str] = None    # Repository URL or filesystem path



class SkillCreate(SkillBase):
    pass



class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    project_id: Optional[str] = None
    source: Optional[str] = None
    location: Optional[str] = None



class SkillResponse(SkillBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

