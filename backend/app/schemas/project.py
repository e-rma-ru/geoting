from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    services: Optional[str] = None
    brand_aliases: List[str] = Field(default_factory=list)
    competitors: List[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    website: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    services: Optional[str] = None
    brand_aliases: Optional[List[str]] = None
    competitors: Optional[List[str]] = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    website: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    services: Optional[str] = None
    brand_aliases: List[str] = Field(default_factory=list)
    competitors: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    category: Optional[str] = None
    active_prompts: int = 0
    researches_count: int = 0
    last_research_at: Optional[datetime] = None
