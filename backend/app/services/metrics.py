from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.citation import Citation
from app.models.competitor_mention import CompetitorMention
from app.models.mention_analysis import MentionAnalysis
from app.models.research_model import ResearchModel
from app.models.research_run import ResearchRun

METHODOLOGY_NOTES = {
    "mention_rate": "mentions / total_runs * 100. brand_mentioned is set programmatically (aliases + fuzzy matching).",
    "top3_rate": "runs with brand_position <= 3 / total_runs * 100. brand_position comes from the LLM analyzer.",
    "average_position": "mean brand_position among runs where the brand is present and position is known.",
    "recommendation_rate": "runs with recommendation_score >= 3 / total_runs * 100.",
    "average_recommendation_score": "mean recommendation_score over all analyzed runs (0 = brand absent).",
    "citation_rate": "runs having at least one citation marked as supporting the brand / total_runs * 100. supports_brand is heuristic (domain/alias match).",
    "entity_accuracy": "mean accuracy_score over analyzed runs.",
    "share_of_voice": "brand mentions / (brand mentions + competitor mentions) * 100. Heuristic visibility share, NOT market share.",
    "denominator": "total_runs = all ResearchRun rows of the research (including failed ones). Failed runs have no analysis and do not count as mentions.",
}


async def compute_research_metrics(db: AsyncSession, research_id: int) -> Dict[str, Any]:
    runs = list(
        (
            await db.execute(
                select(ResearchRun).where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    )
    total_runs = len(runs)
    completed_runs = sum(1 for r in runs if r.status == "completed")
    failed_runs = sum(1 for r in runs if r.status == "failed")

    analyses = list(
        (
            await db.execute(
                select(MentionAnalysis)
                .join(ResearchRun, MentionAnalysis.research_run_id == ResearchRun.id)
                .where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    )
    citations = list(
        (
            await db.execute(
                select(Citation)
                .join(ResearchRun, Citation.research_run_id == ResearchRun.id)
                .where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    )
    competitors = list(
        (
            await db.execute(
                select(CompetitorMention)
                .join(ResearchRun, CompetitorMention.research_run_id == ResearchRun.id)
                .where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    )

    mention_rate = _percent(sum(1 for a in analyses if a.brand_mentioned), total_runs)
    top3 = sum(1 for a in analyses if a.brand_position is not None and a.brand_position <= 3)
    top3_rate = _percent(top3, total_runs)

    positions = [a.brand_position for a in analyses if a.brand_position is not None]
    average_position = round(sum(positions) / len(positions), 2) if positions else None

    rec_rate = _percent(sum(1 for a in analyses if a.recommendation_score is not None and a.recommendation_score >= 3), total_runs)
    rec_scores = [a.recommendation_score for a in analyses if a.recommendation_score is not None]
    average_recommendation_score = round(sum(rec_scores) / len(rec_scores), 2) if rec_scores else None

    brand_cited_run_ids = {c.research_run_id for c in citations if c.supports_brand}
    citation_rate = _percent(len(brand_cited_run_ids), total_runs)

    accuracies = [a.accuracy_score for a in analyses if a.accuracy_score is not None]
    entity_accuracy = round(sum(accuracies) / len(accuracies), 1) if accuracies else None

    brand_mentions = sum(1 for a in analyses if a.brand_mentioned)
    competitor_mentions = len(competitors)
    total_mentions = brand_mentions + competitor_mentions
    share_of_voice = round(brand_mentions / total_mentions * 100, 1) if total_mentions else None

    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "analyzed_runs": len(analyses),
        "mention_rate": mention_rate,
        "top3_rate": top3_rate,
        "average_position": average_position,
        "recommendation_rate": rec_rate,
        "average_recommendation_score": average_recommendation_score,
        "citation_rate": citation_rate,
        "entity_accuracy": entity_accuracy,
        "share_of_voice": share_of_voice,
        "methodology": METHODOLOGY_NOTES,
    }


async def compute_project_timeseries(db: AsyncSession, project_id: int) -> List[Dict[str, Any]]:
    from app.models.research import Research

    researches = list(
        (
            await db.execute(
                select(Research)
                .where(Research.project_id == project_id, Research.status == "completed")
                .order_by(Research.created_at.asc())
            )
        ).scalars()
    )
    result = []
    for r in researches:
        metrics = await compute_research_metrics(db, r.id)
        result.append(
            {
                "research_id": r.id,
                "name": r.name,
                "created_at": r.created_at,
                "completed_at": r.completed_at,
                "metrics": metrics,
            }
        )
    return result


async def compute_research_detail(
    db: AsyncSession, research_id: int
) -> Dict[str, Any]:
    """Everything the dashboard needs: metrics, prompt results, sources, competitors."""
    from app.models.prompt import Prompt
    from app.models.research import Research

    research = await db.get(Research, research_id)
    if research is None:
        raise ValueError("Research not found")

    metrics = await compute_research_metrics(db, research_id)

    model_rows = list(
        (
            await db.execute(
                select(ResearchModel).where(ResearchModel.research_id == research_id).order_by(ResearchModel.id)
            )
        ).scalars()
    )
    models = [m.model for m in model_rows]

    runs = list(
        (
            await db.execute(
                select(ResearchRun).where(ResearchRun.research_id == research_id).order_by(ResearchRun.id)
            )
        ).scalars()
    )
    prompts = {p.id: p for p in list((await db.execute(select(Prompt).where(Prompt.project_id == research.project_id))).scalars())}
    analyses = {a.research_run_id: a for a in list(
        (await db.execute(select(MentionAnalysis).join(ResearchRun).where(ResearchRun.research_id == research_id))).scalars()
    )}

    prompt_results = []
    for run in runs:
        prompt = prompts.get(run.prompt_id)
        analysis = analyses.get(run.id)
        prompt_results.append(
            {
                "run_id": run.id,
                "prompt_id": run.prompt_id,
                "prompt_text": prompt.text if prompt else "",
                "cluster": prompt.cluster if prompt else None,
                "provider": run.provider,
                "model": run.model,
                "run_number": run.run_number,
                "run_status": run.status,
                "brand_mentioned": analysis.brand_mentioned if analysis else None,
                "brand_position": analysis.brand_position if analysis else None,
                "recommendation_score": analysis.recommendation_score if analysis else None,
                "accuracy_score": analysis.accuracy_score if analysis else None,
                "response_time_ms": run.response_time_ms,
                "error_message": run.error_message,
            }
        )

    sources = list(
        (
            await db.execute(
                select(Citation)
                .join(ResearchRun, Citation.research_run_id == ResearchRun.id)
                .where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    )
    source_agg: Dict[str, Dict[str, Any]] = {}
    for c in sources:
        key = c.domain or "(none)"
        entry = source_agg.setdefault(
            key, {"domain": c.domain, "count": 0, "supports_brand": 0, "source_type": c.source_type}
        )
        entry["count"] += 1
        if c.supports_brand:
            entry["supports_brand"] += 1

    competitor_agg: Dict[str, Dict[str, Any]] = {}
    for cm in await _load_competitors(db, research_id):
        entry = competitor_agg.setdefault(
            cm.competitor_name,
            {"name": cm.competitor_name, "mentions": 0, "top3": 0, "positions": [], "recommendation_scores": []},
        )
        entry["mentions"] += 1
        if cm.position is not None:
            entry["positions"].append(cm.position)
            if cm.position <= 3:
                entry["top3"] += 1
        if cm.recommendation_score is not None:
            entry["recommendation_scores"].append(cm.recommendation_score)

    competitors_table = []
    for entry in sorted(competitor_agg.values(), key=lambda e: -e["mentions"]):
        positions = entry["positions"]
        competitors_table.append(
            {
                "name": entry["name"],
                "mentions": entry["mentions"],
                "top3": entry["top3"],
                "avg_position": round(sum(positions) / len(positions), 2) if positions else None,
                "avg_recommendation": (
                    round(sum(entry["recommendation_scores"]) / len(entry["recommendation_scores"]), 2)
                    if entry["recommendation_scores"]
                    else None
                ),
            }
        )

    return {
        "research": {
            "id": research.id,
            "name": research.name,
            "status": research.status,
            "project_id": research.project_id,
            "models": models,
            "prompts_count": research.prompts_count,
            "providers_count": research.providers_count,
            "runs_per_prompt": research.runs_per_prompt,
            "created_at": research.created_at,
            "started_at": research.started_at,
            "completed_at": research.completed_at,
        },
        "metrics": metrics,
        "prompt_results": prompt_results,
        "sources": sorted(source_agg.values(), key=lambda e: -e["count"]),
        "competitors": competitors_table,
    }


async def _load_competitors(db: AsyncSession, research_id: int):
    return list(
        (
            await db.execute(
                select(CompetitorMention)
                .join(ResearchRun, CompetitorMention.research_run_id == ResearchRun.id)
                .where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    )


def _percent(part: int, total: int) -> Optional[float]:
    if total == 0:
        return None
    return round(part / total * 100, 1)
