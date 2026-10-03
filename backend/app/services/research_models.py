"""Helpers for reading a research's selected models and building read dicts."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research import Research
from app.models.research_model import ResearchModel


async def get_models_map(db: AsyncSession, research_ids: List[int]) -> Dict[int, List[str]]:
    if not research_ids:
        return {}
    rows = list(
        (
            await db.execute(
                select(ResearchModel).where(ResearchModel.research_id.in_(research_ids)).order_by(ResearchModel.id)
            )
        ).scalars()
    )
    result: Dict[int, List[str]] = {}
    for row in rows:
        result.setdefault(row.research_id, []).append(row.model)
    return result


async def research_read(db: AsyncSession, research: Research) -> dict:
    models_map = await get_models_map(db, [research.id])
    return {
        "id": research.id,
        "project_id": research.project_id,
        "name": research.name,
        "status": research.status,
        "models": models_map.get(research.id, []),
        "prompts_count": research.prompts_count,
        "providers_count": research.providers_count,
        "runs_per_prompt": research.runs_per_prompt,
        "started_at": research.started_at,
        "completed_at": research.completed_at,
        "created_at": research.created_at,
    }


async def researches_read(db: AsyncSession, researches: List[Research]) -> List[dict]:
    ids = [r.id for r in researches]
    models_map = await get_models_map(db, ids)
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "name": r.name,
            "status": r.status,
            "models": models_map.get(r.id, []),
            "prompts_count": r.prompts_count,
            "providers_count": r.providers_count,
            "runs_per_prompt": r.runs_per_prompt,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "created_at": r.created_at,
        }
        for r in researches
    ]
