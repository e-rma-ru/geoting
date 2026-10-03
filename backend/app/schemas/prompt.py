from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PromptCreate(BaseModel):
    text: str = Field(min_length=1)
    cluster: Optional[str] = None
    intent: Optional[str] = None
    active: bool = True


class PromptUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1)
    cluster: Optional[str] = None
    intent: Optional[str] = None
    active: Optional[bool] = None


class PromptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    text: str
    cluster: Optional[str] = None
    intent: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime


class PromptBulkImportResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: int = 0
