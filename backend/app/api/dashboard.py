from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.research import Research
from app.services.metrics import (
    compute_project_timeseries,
    compute_research_detail,
    compute_research_metrics,
)
from app.services.profile_service import ResearchProfilesNotFoundError, build_profiles, get_profiles

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/research/{research_id}/dashboard")
async def research_dashboard(research_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await compute_research_detail(db, research_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Research not found")


@router.get("/projects/{project_id}/dashboard")
async def project_dashboard(project_id: int, db: AsyncSession = Depends(get_db)):
    timeseries = await compute_project_timeseries(db, project_id)
    return {"project_id": project_id, "timeseries": timeseries}


@router.get("/research/{research_id}/metrics")
async def research_metrics(research_id: int, db: AsyncSession = Depends(get_db)):
    research = await db.get(Research, research_id)
    if research is None:
        raise HTTPException(status_code=404, detail="Research not found")
    return await compute_research_metrics(db, research_id)


@router.get("/compare")
async def compare_research(    research_ids: str,
    db: AsyncSession = Depends(get_db),
):
    """research_ids: comma-separated ids, e.g. ?research_ids=1,2"""
    try:
        ids = [int(x.strip()) for x in research_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="research_ids must be integers separated by comma")
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two research ids")

    results = []
    for rid in ids:
        research = await db.get(Research, rid)
        if research is None:
            raise HTTPException(status_code=404, detail=f"Research {rid} not found")
        metrics = await compute_research_metrics(db, rid)
        results.append(
            {
                "research_id": rid,
                "name": research.name,
                "created_at": research.created_at,
                "metrics": metrics,
            }
        )

    base = results[0]["metrics"]
    rows = []
    metric_keys = [
        "mention_rate",
        "top3_rate",
        "average_position",
        "recommendation_rate",
        "average_recommendation_score",
        "citation_rate",
        "entity_accuracy",
        "share_of_voice",
    ]
    for key in metric_keys:
        values = [p["metrics"].get(key) for p in results]
        non_null = [v for v in values if v is not None]
        diff = None
        if len(non_null) == len(values) and len(values) >= 2:
            diff = round(values[-1] - values[0], 1)
        rows.append({"metric": key, "values": values, "diff": diff})

    return {"points": results, "comparison": rows}


@router.get("/research/{research_id}/profiles")
async def research_profiles(research_id: int, db: AsyncSession = Depends(get_db)):
    """Read saved AI profiles. DB read only — never triggers LLM calls."""
    try:
        return await get_profiles(db, research_id)
    except ResearchProfilesNotFoundError:
        raise HTTPException(status_code=404, detail="Research not found")


@router.post("/research/{research_id}/profiles/build")
async def research_profiles_build(research_id: int, db: AsyncSession = Depends(get_db)):
    """Explicitly build AI profiles from existing runs. May use AI API credits."""
    try:
        return await build_profiles(db, research_id)
    except ResearchProfilesNotFoundError:
        raise HTTPException(status_code=404, detail="Research not found")
