"""Reusable organization-scoped lookup helpers for tenant isolation.

Each helper verifies that the requested resource belongs to the current
user's organization through the Project → Organization chain.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_organization
from app.database import get_db
from app.models.project import Project
from app.models.prompt import Prompt
from app.models.research import Research
from app.models.research_run import ResearchRun


async def get_org_project(
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


async def get_org_prompt(
    db: AsyncSession, prompt_id: int, org_id: int
) -> Prompt:
    prompt = (
        await db.execute(
            select(Prompt)
            .join(Project, Prompt.project_id == Project.id)
            .where(Prompt.id == prompt_id, Project.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    return prompt


async def get_org_research(
    db: AsyncSession, research_id: int, org_id: int
) -> Research:
    research = (
        await db.execute(
            select(Research)
            .join(Project, Research.project_id == Project.id)
            .where(Research.id == research_id, Project.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if research is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research not found")
    return research


async def get_org_run(
    db: AsyncSession, run_id: int, org_id: int
) -> ResearchRun:
    run = (
        await db.execute(
            select(ResearchRun)
            .join(Research, ResearchRun.research_id == Research.id)
            .join(Project, Research.project_id == Project.id)
            .where(ResearchRun.id == run_id, Project.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ResearchRun not found")
    return run