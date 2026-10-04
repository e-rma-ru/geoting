from __future__ import annotations

import logging
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    set_auth_cookie,
    unset_auth_cookie,
    verify_password,
)
from app.database import get_db
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    UserRead,
)

logger = logging.getLogger("geoting.api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _make_org_name(payload: RegisterRequest) -> str:
    return payload.name or payload.email


def _make_org_slug(org_name: str, email: str) -> str:
    slug = org_name.strip().lower()
    if "@" in slug:
        slug = slug[: slug.index("@")]
    slug = _SLUG_CLEAN.sub("-", slug).strip("-")
    if not slug:
        slug = email[: email.index("@")]
        slug = _SLUG_CLEAN.sub("-", slug).strip("-")
    if not slug:
        slug = "org"
    suffix = secrets.token_hex(4)
    return f"{slug}-{suffix}"


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(payload.email)

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    await db.flush()

    org_name = _make_org_name(payload)
    org = Organization(name=org_name, slug=_make_org_slug(org_name, email))
    db.add(org)
    await db.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="OWNER",
    )
    db.add(membership)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    cookie_kwargs = set_auth_cookie(token)
    response.set_cookie(**cookie_kwargs)

    return user


@router.post("/login", response_model=UserRead)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(payload.email)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    token = create_access_token(user.id)
    cookie_kwargs = set_auth_cookie(token)
    response.set_cookie(**cookie_kwargs)

    return user


@router.post("/logout")
async def logout(response: Response, request: Request):
    cookie_kwargs = unset_auth_cookie()
    response.set_cookie(**cookie_kwargs)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserRead)
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await db.get(User, current_user.id)
    if payload.name is not None:
        user.name = payload.name
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await db.get(User, current_user.id)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = hash_password(payload.new_password)
    await db.commit()

    cookie_kwargs = unset_auth_cookie()
    response.set_cookie(**cookie_kwargs)

    return {"message": "Password changed. Please log in again."}