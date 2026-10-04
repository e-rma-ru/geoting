from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_org_project, get_org_research, get_org_run
from app.auth import get_current_organization
from app.database import get_db
from app.models.citation import Citation
from app.models.competitor_mention import CompetitorMention
from app.models.mention_analysis import MentionAnalysis
from app.models.organization import Organization
from app.models.prompt import Prompt
from app.models.project import Project
from app.models.research import Research
from app.models.research_run import ResearchRun
from app.schemas.research import (
    ResearchCreate,
    ResearchRead,
    ResearchRunDetail,
    ResearchRunRead,
    RunDetailResponse,
    RunPromptInfo,
)
from app.services.research_models import research_read, researches_read
from app.services.research_service import ResearchService

router = APIRouter(prefix="/api", tags=["research"])


@router.get("/research", response_model=list[ResearchRead])
async def list_all_research(
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    researches = list(
        (
            await db.execute(
                select(Research)
                .join(Project, Research.project_id == Project.id)
                .where(Project.organization_id == current_org.id)
                .order_by(Research.created_at.desc())
            )
        ).scalars()
    )
    return await researches_read(db, researches)


@router.get("/projects/{project_id}/research", response_model=list[ResearchRead])
async def list_research(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    await get_org_project(db, project_id, current_org.id)
    researches = list(
        (
            await db.execute(
                select(Research).where(Research.project_id == project_id).order_by(Research.created_at.desc())
            )
        ).scalars()
    )
    return await researches_read(db, researches)


@router.post("/research", response_model=ResearchRead, status_code=202)
async def create_research(
    payload: ResearchCreate,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    await get_org_project(db, payload.project_id, current_org.id)
    service = ResearchService()
    try:
        research = await service.create_research(
            db,
            project_id=payload.project_id,
            name=payload.name,
            models=payload.models,
            runs_per_prompt=payload.runs_per_prompt,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await research_read(db, research)


@router.get("/research/{research_id}", response_model=ResearchRead)
async def get_research(
    research_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    return await get_org_research(db, research_id, current_org.id)


@router.delete("/research/{research_id}", status_code=204)
async def delete_research(
    research_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    """Delete a research and all its children (runs, raw responses, analyses,
    citations, competitor mentions, AI profiles) via DB-level ON DELETE CASCADE."""
    research = await get_org_research(db, research_id, current_org.id)
    await db.delete(research)
    await db.commit()


@router.get("/research/{research_id}/runs", response_model=list[ResearchRunRead])
async def list_runs(
    research_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    await get_org_research(db, research_id, current_org.id)
    runs = list(
        (
            await db.execute(
                select(ResearchRun).where(ResearchRun.research_id == research_id).order_by(ResearchRun.id)
            )
        ).scalars()
    )
    return runs


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run_detail(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    run = await get_org_run(db, run_id, current_org.id)

    prompt = await db.get(Prompt, run.prompt_id)
    analysis = (
        await db.execute(select(MentionAnalysis).where(MentionAnalysis.research_run_id == run_id))
    ).scalar_one_or_none()
    citations = list(
        (await db.execute(select(Citation).where(Citation.research_run_id == run_id))).scalars()
    )
    competitors = list(
        (
            await db.execute(select(CompetitorMention).where(CompetitorMention.research_run_id == run_id))
        ).scalars()
    )

    return RunDetailResponse(
        run=ResearchRunDetail.model_validate(run),
        prompt=RunPromptInfo(
            id=prompt.id if prompt else None,
            text=prompt.text if prompt else None,
            cluster=prompt.cluster if prompt else None,
            intent=prompt.intent if prompt else None,
        ),
        analysis=_analysis_dict(analysis),
        citations=[
            {
                "id": c.id,
                "url": c.url,
                "domain": c.domain,
                "title": c.title,
                "cited_text": c.cited_text,
                "supports_brand": c.supports_brand,
                "source_type": c.source_type,
            }
            for c in citations
        ],
        competitors=[
            {
                "id": cm.id,
                "name": cm.competitor_name,
                "position": cm.position,
                "recommendation_score": cm.recommendation_score,
            }
            for cm in competitors
        ],
    )


def _analysis_dict(analysis):
    if analysis is None:
        return None
    return {
        "id": analysis.id,
        "brand_mentioned": analysis.brand_mentioned,
        "brand_position": analysis.brand_position,
        "recommendation_score": analysis.recommendation_score,
        "sentiment": analysis.sentiment,
        "accuracy_score": analysis.accuracy_score,
        "confidence": analysis.confidence,
        "reasoning": analysis.reasoning,
        "is_heuristic": analysis.is_heuristic,
        "raw_analysis": analysis.raw_analysis,
        "created_at": analysis.created_at,
    }
