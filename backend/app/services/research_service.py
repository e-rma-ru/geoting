from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionLocal
from app.models.common import utcnow
from app.models.project import Project
from app.models.prompt import Prompt
from app.models.research import Research
from app.models.research_model import ResearchModel
from app.models.research_run import ResearchRun
from app.providers import get_provider
from app.runtime_config import runtime_config_store
from app.services.analysis_service import AnalysisService
from app.services.model_catalog import get_available_models

logger = logging.getLogger("geoting.research")

_shared_semaphore: Optional[asyncio.Semaphore] = None


def get_shared_semaphore() -> asyncio.Semaphore:
    """Global semaphore shared across all researches so MAX_CONCURRENT_REQUESTS
    bounds total outbound API traffic, not just per-research."""
    global _shared_semaphore
    if _shared_semaphore is None:
        _shared_semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_requests))
    return _shared_semaphore


class ResearchService:
    def __init__(self) -> None:
        self._gateway = "routerai"

    async def create_research(
        self,
        db: AsyncSession,
        project_id: int,
        name: Optional[str],
        models: Optional[List[str]],
        runs_per_prompt: int,
        model: Optional[str] = None,
    ) -> Research:
        project = await db.get(Project, project_id)
        if project is None:
            raise ValueError("Project not found")

        prompts = list(
            (
                await db.execute(
                    select(Prompt).where(Prompt.project_id == project_id, Prompt.active.is_(True)).order_by(Prompt.id)
                )
            ).scalars()
        )
        if not prompts:
            raise ValueError("Project has no active prompts")

        if not get_provider("routerai").is_configured:
            raise ValueError(
                "RouterAI is not configured (no API key). Add ROUTERAI_API_KEY in Settings or backend/.env."
            )

        # Resolve selected models: explicit `models` list > legacy `model` > default.
        requested = list(models or [])
        if not requested and model:
            requested = [model]
        if not requested:
            requested = [runtime_config_store.get_default_model()]
        selected: List[str] = []
        for m in requested:
            m = (m or "").strip()
            if m and m not in selected:
                selected.append(m)
        if not selected:
            raise ValueError("Select at least one AI model")

        available = [m["id"] for m in await get_available_models()]
        if available:
            unknown = [m for m in selected if m not in available]
            if unknown:
                raise ValueError(
                    f"Unknown models (not in the RouterAI catalog): {', '.join(unknown)}. "
                    "Pick models from the list."
                )

        research = Research(
            project_id=project_id,
            name=name or f"Research {utcnow():%Y-%m-%d %H:%M}",
            status="queued",
            prompts_count=len(prompts),
            providers_count=1,
            runs_per_prompt=runs_per_prompt,
        )
        db.add(research)
        await db.flush()

        for m in selected:
            db.add(ResearchModel(research_id=research.id, model=m, provider=self._gateway))

        total_runs = len(prompts) * len(selected) * runs_per_prompt
        for prompt in prompts:
            for m in selected:
                for run_number in range(1, runs_per_prompt + 1):
                    db.add(
                        ResearchRun(
                            research_id=research.id,
                            prompt_id=prompt.id,
                            provider=self._gateway,
                            model=m,
                            run_number=run_number,
                            status="queued",
                        )
                    )
        await db.commit()

        logger.info(
            "Research started: id=%s name=%r models=%s prompts=%d runs/prompt=%d (total runs=%d)",
            research.id,
            research.name,
            selected,
            len(prompts),
            runs_per_prompt,
            total_runs,
        )
        asyncio.get_running_loop().create_task(self._run_research(research.id))
        return research

    async def _run_research(self, research_id: int) -> None:
        async with SessionLocal() as db:
            research = await db.get(Research, research_id)
            if research is None:
                return

            research.status = "running"
            research.started_at = utcnow()
            await db.commit()

            runs = list(
                (
                    await db.execute(
                        select(ResearchRun)
                        .where(ResearchRun.research_id == research_id)
                        .order_by(ResearchRun.id)
                    )
                ).scalars()
            )
            project = await db.get(Project, research.project_id)
            prompts = {
                p.id: p
                for p in list(
                    (
                        await db.execute(
                            select(Prompt).where(Prompt.project_id == research.project_id)
                        )
                    ).scalars()
                )
            }

            total = len(runs)
            logger.info("Research %s running: %d runs to execute", research_id, total)

            completed = 0
            for run in runs:
                if run.status == "completed":
                    completed += 1

            sem = get_shared_semaphore()

            async def process(run: ResearchRun) -> None:
                nonlocal completed
                async with sem:
                    await self._process_run(research, project, prompts, run)
                    completed += 1
                    logger.info(
                        "Research %s progress: %d/%d runs done",
                        research_id,
                        completed,
                        total,
                    )

            await asyncio.gather(*(process(run) for run in runs if run.status != "completed"))

            await db.refresh(research)
            failed_count = 0
            if runs:
                remaining = list(
                    (
                        await db.execute(
                            select(ResearchRun)
                            .where(ResearchRun.research_id == research_id)
                        )
                    ).scalars()
                )
                failed_count = sum(1 for r in remaining if r.status == "failed")
            if failed_count == len(runs) and runs:
                research.status = "failed"
            else:
                research.status = "completed"
            research.completed_at = utcnow()
            await db.commit()
            logger.info("Research %s finished: status=%s", research_id, research.status)

    async def _process_run(
        self,
        research: Research,
        project: Optional[Project],
        prompts: dict,
        run: ResearchRun,
    ) -> None:
        prompt = prompts.get(run.prompt_id)
        logger.info(
            "[research %s] prompt %s (%s) provider=%s run=%s request started",
            research.id,
            run.prompt_id,
            prompt.text[:60] if prompt else "?",
            run.provider,
            run.run_number,
        )

        async with SessionLocal() as db:
            current = await db.get(ResearchRun, run.id)
            if current is None:
                return
            current.status = "running"
            await db.commit()

            try:
                provider = get_provider(current.provider)
                # Each run executes its OWN model (multi-model research). The
                # provider instance is configured per-run from the run's model.
                if current.model:
                    provider.set_config({**provider.config, "model": current.model})
                ai_response = await provider.run_prompt(prompt.text if prompt else "")

                current.response_text = ai_response.text
                current.raw_response = ai_response.raw_response
                # run.model keeps the model that was requested for this run
                # (research_models). The gateway-echoed model stays in raw_response.
                current.response_time_ms = ai_response.response_time_ms
                current.status = "completed"
                current.completed_at = utcnow()
                await db.commit()
                logger.info(
                    "[research %s] provider=%s request completed in %sms (chars=%d)",
                    research.id,
                    current.provider,
                    current.response_time_ms or 0,
                    len(ai_response.text or ""),
                )

                if project is not None and prompt is not None:
                    await AnalysisService(db, project, prompt, current, ai_response).run()
            except Exception as exc:
                current.status = "failed"
                current.error_message = str(exc)[:2000]
                current.completed_at = utcnow()
                await db.commit()
                logger.error(
                    "[research %s] provider=%s run failed: %s",
                    research.id,
                    current.provider,
                    exc,
                    exc_info=True,
                )
