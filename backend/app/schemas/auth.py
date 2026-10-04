from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: Optional[str] = None
    is_active: bool
    is_superadmin: bool
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)