from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_OWNER,
    get_current_membership,
    get_current_organization,
    get_current_user,
    require_role,
)
from app.database import get_db
from app.models.organization import Organization
from app.models.organization_invitation import OrganizationInvitation
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.schemas.organization import (
    AcceptInviteRequest,
    InviteCreate,
    InviteRead,
    MemberRead,
    MemberRoleUpdate,
    OrganizationRead,
    OrganizationUpdate,
    TransferOwnershipRequest,
)

logger = logging.getLogger("geoting.api.organization")

router = APIRouter(prefix="/api/organization", tags=["organization"])

INVITE_EXPIRE_HOURS = 72


# ─── Helpers ──────────────────────────────────────────────────────────────────


async def _members_to_read(db, memberships, org_id):
    user_ids = [m.user_id for m in memberships]
    users = {}
    if user_ids:
        rows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: u for u in rows}
    return [
        MemberRead(
            id=m.id,
            user_id=m.user_id,
            email=users[m.user_id].email if m.user_id in users else "",
            name=users[m.user_id].name if m.user_id in users else None,
            role=m.role,
            created_at=m.created_at,
        )
        for m in memberships
    ]


async def _assert_only_owner(membership: OrganizationMembership):
    db = None  # We'll use caller's session
    return membership.role == ROLE_OWNER


# ─── Organization ─────────────────────────────────────────────────────────────


ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER)


@router.get("", response_model=OrganizationRead)
async def get_organization(
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, current_membership.organization_id)
    return OrganizationRead(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_at=org.created_at,
        role=current_membership.role,
    )


@router.put("", response_model=OrganizationRead)
async def update_organization(
    payload: OrganizationUpdate,
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    if current_membership.role not in (ROLE_OWNER,):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only OWNER can update organization")
    org = await db.get(Organization, current_membership.organization_id)
    org.name = payload.name
    await db.commit()
    await db.refresh(org)
    return OrganizationRead(
        id=org.id, name=org.name, slug=org.slug, created_at=org.created_at, role=current_membership.role,
    )


# ─── Members ──────────────────────────────────────────────────────────────────


@router.get("/members", response_model=list[MemberRead])
async def list_members(
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    memberships = (
        (await db.execute(
            select(OrganizationMembership)
            .where(OrganizationMembership.organization_id == current_membership.organization_id)
            .order_by(OrganizationMembership.id)
        )).scalars().all()
    )
    return await _members_to_read(db, memberships, current_membership.organization_id)


@router.patch("/members/{membership_id}", response_model=MemberRead)
async def update_member_role(
    membership_id: int,
    payload: MemberRoleUpdate,
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    actor = await db.get(OrganizationMembership, current_membership.id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    target = await db.get(OrganizationMembership, membership_id)
    if target is None or target.organization_id != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    new_role = payload.role
    actor_role = actor.role

    if actor_role == ROLE_OWNER:
        if target.role == ROLE_OWNER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change OWNER role via this endpoint")
    elif actor_role == ROLE_ADMIN:
        if target.role in (ROLE_OWNER, ROLE_ADMIN):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify OWNER or ADMIN")
        if new_role == ROLE_ADMIN:
            pass  # ADMIN can promote MEMBER to ADMIN
        elif new_role == ROLE_MEMBER:
            pass
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot set this role")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    target.role = new_role
    await db.commit()
    await db.refresh(target)

    user = await db.get(User, target.user_id)
    return MemberRead(
        id=target.id,
        user_id=target.user_id,
        email=user.email if user else "",
        name=user.name if user else None,
        role=target.role,
        created_at=target.created_at,
    )


@router.delete("/members/{membership_id}", status_code=204)
async def delete_member(
    membership_id: int,
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    actor = await db.get(OrganizationMembership, current_membership.id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    target = await db.get(OrganizationMembership, membership_id)
    if target is None or target.organization_id != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    actor_role = actor.role

    if actor_role == ROLE_OWNER:
        if target.role == ROLE_OWNER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the only OWNER")
    elif actor_role == ROLE_ADMIN:
        if target.role in (ROLE_OWNER, ROLE_ADMIN):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot remove OWNER or ADMIN")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    await db.delete(target)
    await db.commit()


# ─── Transfer ownership ───────────────────────────────────────────────────────


@router.post("/transfer-ownership")
async def transfer_ownership(
    payload: TransferOwnershipRequest,
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    actor = await db.get(OrganizationMembership, current_membership.id)
    if actor is None or actor.role != ROLE_OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only OWNER can transfer ownership")

    target = (
        await db.execute(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == actor.organization_id,
                OrganizationMembership.user_id == payload.user_id,
            )
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this organization")

    actor.role = ROLE_ADMIN
    target.role = ROLE_OWNER
    await db.commit()

    return {"message": "Ownership transferred"}


# ─── Invitations ──────────────────────────────────────────────────────────────


@router.post("/invites", response_model=InviteRead, status_code=201)
async def create_invite(
    payload: InviteCreate,
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    actor_role = current_membership.role
    if actor_role == ROLE_OWNER:
        pass  # can invite ADMIN or MEMBER
    elif actor_role == ROLE_ADMIN:
        if payload.role != ROLE_MEMBER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN can only invite MEMBER")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRE_HOURS)

    invite = OrganizationInvitation(
        organization_id=current_membership.organization_id,
        email=payload.email.strip().lower(),
        role=payload.role,
        token=token,
        invited_by=current_membership.user_id,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


@router.get("/invites", response_model=list[InviteRead])
async def list_invites(
    current_membership: OrganizationMembership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    if current_membership.role not in (ROLE_OWNER, ROLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    invites = (
        (await db.execute(
            select(OrganizationInvitation)
            .where(
                OrganizationInvitation.organization_id == current_membership.organization_id,
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.cancelled_at.is_(None),
            )
            .order_by(OrganizationInvitation.created_at.desc())
        )).scalars().all()
    )
    return invites


# ─── Public: accept invitation (no auth required, user may not exist yet) ────


@router.post("/accept-invite")
async def accept_invite(
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invite = (
        await db.execute(
            select(OrganizationInvitation).where(
                OrganizationInvitation.token == payload.token,
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.cancelled_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found or expired")

    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation expired")

    if invite.email != current_user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation was sent to a different email")

    existing = (
        await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == invite.organization_id,
                OrganizationMembership.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already a member of this organization")

    membership = OrganizationMembership(
        organization_id=invite.organization_id,
        user_id=current_user.id,
        role=invite.role,
    )
    db.add(membership)
    invite.accepted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Invitation accepted"}