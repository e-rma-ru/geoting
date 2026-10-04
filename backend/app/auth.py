"""Password hashing, JWT handling, and get_current_user dependency.

Uses Argon2id (via passlib) for password hashing and PyJWT for stateless
authentication tokens delivered via HttpOnly cookie.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from passlib.hash import argon2
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User

logger = logging.getLogger("geoting.auth")

COOKIE_NAME = "geoting_access_token"
TOKEN_EXPIRE_HOURS = 24


# ─── Password hashing ─────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return argon2.using(time_cost=2, memory_cost=19_200, parallelism=1).hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return argon2.verify(password, password_hash)
    except Exception:
        return False


# ─── JWT ──────────────────────────────────────────────────────────────────────


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": now,
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
        return user_id
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


# ─── Cookie helpers ───────────────────────────────────────────────────────────


def set_auth_cookie(token: str) -> dict:
    """Return keyword-arguments for setting the auth cookie on a Response."""
    return {
        "key": COOKIE_NAME,
        "value": token,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.auth_cookie_secure,
        "path": "/",
    }


def unset_auth_cookie() -> dict:
    """Return keyword-arguments for removing the auth cookie."""
    return {
        "key": COOKIE_NAME,
        "value": "",
        "httponly": True,
        "samesite": "lax",
        "secure": settings.auth_cookie_secure,
        "path": "/",
        "max_age": 0,
    }


# ─── Dependencies ─────────────────────────────────────────────────────────────


async def get_current_user(request: Request) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = decode_access_token(token)
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return user


async def get_current_organization(current_user: User = Depends(get_current_user)) -> Organization:
    async with SessionLocal() as db:
        membership = (
            await db.execute(
                select(OrganizationMembership)
                .where(OrganizationMembership.user_id == current_user.id)
                .order_by(OrganizationMembership.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership")
        org = await db.get(Organization, membership.organization_id)
        if org is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization not found")
        return org


async def get_current_membership(current_user: User = Depends(get_current_user)) -> OrganizationMembership:
    async with SessionLocal() as db:
        membership = (
            await db.execute(
                select(OrganizationMembership)
                .where(OrganizationMembership.user_id == current_user.id)
                .order_by(OrganizationMembership.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership")
        return membership


ROLE_OWNER = "OWNER"
ROLE_ADMIN = "ADMIN"
ROLE_MEMBER = "MEMBER"


def require_role(*allowed: str):
    """Return a dependency that checks the current membership role."""
    async def _require(current_membership: OrganizationMembership = Depends(get_current_membership)) -> OrganizationMembership:
        if current_membership.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_membership
    return _require