from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
    role: str = ""


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class MemberRead(BaseModel):
    id: int
    user_id: int
    email: str
    name: Optional[str] = None
    role: str
    created_at: datetime


class MemberRoleUpdate(BaseModel):
    role: str = Field(pattern=r"^(OWNER|ADMIN|MEMBER)$")


class TransferOwnershipRequest(BaseModel):
    user_id: int


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: str = Field(default="MEMBER", pattern=r"^(ADMIN|MEMBER)$")


class InviteRead(BaseModel):
    id: int
    organization_id: int
    email: str
    role: str
    token: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime


class AcceptInviteRequest(BaseModel):
    token: str