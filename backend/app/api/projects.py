from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import ROLE_ADMIN, ROLE_OWNER, get_current_organization, get_current_membership
from app.database import get_db
from app.models.organization_membership import OrganizationMembership
from app.models.organization import Organization
from app.models.project import Project
from app.models.prompt import Prompt
from app.models.research import Research
from app.schemas.project import ProjectCreate, ProjectRead, ProjectSummary, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


async def get_project_or_404(db: AsyncSession, project_id: int) -> Project:
    """Backward-compatible lookup (no org scope). Used by prompts/research APIs."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_project_in_org(
    db: AsyncSession, project_id: int, org_id: int
) -> Project:
    project = (
        await db.execute(
            select(Project).where(
                Project.id == project_id, Project.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    projects = list(
        (
            await db.execute(
                select(Project)
                .where(Project.organization_id == current_org.id)
                .order_by(Project.name)
            )
        ).scalars()
    )
    result = []
    for p in projects:
        active_prompts = (
            await db.execute(
                select(func.count()).select_from(Prompt).where(Prompt.project_id == p.id, Prompt.active.is_(True))
            )
        ).scalar_one()
        researches_count = (
            await db.execute(select(func.count()).select_from(Research).where(Research.project_id == p.id))
        ).scalar_one()
        last_research_at = (
            await db.execute(
                select(func.max(Research.created_at)).select_from(Research).where(Research.project_id == p.id)
            )
        ).scalar_one()
        result.append(
            ProjectSummary(
                id=p.id,
                name=p.name,
                city=p.city,
                category=p.category,
                active_prompts=active_prompts or 0,
                researches_count=researches_count or 0,
                last_research_at=last_research_at or None,
            )
        )
    return result


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    project = Project(**payload.model_dump(), organization_id=current_org.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    return await _get_project_in_org(db, project_id, current_org.id)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    project = await _get_project_in_org(db, project_id, current_org.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
    current_membership: OrganizationMembership = Depends(get_current_membership),
):
    if current_membership.role not in (ROLE_OWNER, ROLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only OWNER or ADMIN can delete projects")
    project = await _get_project_in_org(db, project_id, current_org.id)
    await db.delete(project)
    await db.commit()
