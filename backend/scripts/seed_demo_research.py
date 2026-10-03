"""Dev/demo only: inserts a COMPLETED research filled with clearly-marked
DEMO data so the dashboard UI can be explored before real API keys are set.

This does NOT call any AI API. All data is labelled as DEMO.
Run:  PYTHONPATH=. .venv/bin/python scripts/seed_demo_research.py
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import (
    Citation, CompetitorMention, MentionAnalysis, Project, Prompt, Research, ResearchRun,
)
from app.models.common import utcnow

wave = int(sys.argv[1]) if len(sys.argv) > 1 else 1
if wave == 1:
    DEMO_RESEARCH_NAME = "DEMO — sample research (не реальные данные)"
    HIT_RATE = 1.0        # brand mentioned in all runs
    POSITION_BIAS = 0     # positions 1/2
    REC_BIAS = 0          # scores 5/4
else:
    DEMO_RESEARCH_NAME = "DEMO — baseline research 2 (не реальные данные)"
    HIT_RATE = 0.5        # brand mentioned in ~half of runs
    POSITION_BIAS = 3     # positions shift down
    REC_BIAS = -1         # scores lower

DEMO_PROMPT_TEXTS = [
    "Какие хорошие языковые школы английского есть во Владивостоке?",
    "Куда во Владивостоке отдать ребёнка на английский?",
    "Где взрослому человеку во Владивостоке выучить английский с нуля?",
]


async def main() -> None:
    async with SessionLocal() as db:
        existing = (
            await db.execute(select(Research).where(Research.name == DEMO_RESEARCH_NAME))
        ).scalars().all()
        for r in existing:
            await db.execute(delete(CompetitorMention).where(CompetitorMention.research_run_id.in_(
                select(ResearchRun.id).where(ResearchRun.research_id == r.id)
            )))
            await db.execute(delete(Citation).where(Citation.research_run_id.in_(
                select(ResearchRun.id).where(ResearchRun.research_id == r.id)
            )))
            await db.execute(delete(MentionAnalysis).where(MentionAnalysis.research_run_id.in_(
                select(ResearchRun.id).where(ResearchRun.research_id == r.id)
            )))
            await db.execute(delete(ResearchRun).where(ResearchRun.research_id == r.id))
            await db.execute(delete(Research).where(Research.id == r.id))
        await db.commit()

        project = (await db.execute(select(Project).where(Project.name == "Priority Center"))).scalars().first()
        if project is None:
            print("Run seed first: python -m app.seed")
            return

        prompts = []
        for text in DEMO_PROMPT_TEXTS:
            p = (await db.execute(select(Prompt).where(Prompt.project_id == project.id, Prompt.text == text))).scalars().first()
            if p:
                prompts.append(p)

        research = Research(
            project_id=project.id,
            name=DEMO_RESEARCH_NAME,
            status="completed",
            prompts_count=len(prompts),
            providers_count=2,
            runs_per_prompt=2,
            started_at=utcnow(),
            completed_at=utcnow(),
        )
        db.add(research)
        await db.flush()

        answers = {
            "openai": (
                "[DEMO] Для изучения английского во Владивостоке рекомендуем рассмотреть Priority Center — "
                "языковой центр для детей, подростков и взрослых. Также хорошие отзывы у Demo School A и Demo School B."
            ),
            "gemini": (
                "[DEMO] Среди языковых центров Владивостока выделяется Priority Center: курсы для детей от 6 лет, "
                "подростков и взрослых. Как альтернативу можно рассмотреть Demo School A."
            ),
        }

        run_no = 0
        for prompt in prompts:
            for provider, text in answers.items():
                for run_number in (1, 2):
                    run_no += 1
                    mentioned = (run_no % 10) < 10 * HIT_RATE
                    run = ResearchRun(
                        research_id=research.id,
                        prompt_id=prompt.id,
                        provider=provider,
                        model="demo-model",
                        run_number=run_number,
                        status="completed",
                        response_text=text,
                        response_time_ms=900 + run_no * 37,
                        completed_at=utcnow(),
                    )
                    db.add(run)
                    await db.flush()

                    if mentioned:
                        position = run_number + POSITION_BIAS
                        db.add(
                            MentionAnalysis(
                                research_run_id=run.id,
                                brand_mentioned=True,
                                brand_position=position,
                                recommendation_score=max(1, (5 if run_number == 1 else 4) + REC_BIAS),
                                sentiment="positive",
                                accuracy_score=max(60, 88 + run_number + REC_BIAS * 3),
                                confidence=0.9,
                                reasoning="DEMO data: бренд упомянут и рекомендован.",
                                is_heuristic=True,
                            )
                        )
                    else:
                        db.add(
                            MentionAnalysis(
                                research_run_id=run.id,
                                brand_mentioned=False,
                                brand_position=None,
                                recommendation_score=0,
                                sentiment="unknown",
                                accuracy_score=None,
                                confidence=None,
                                reasoning="DEMO data: бренд не упомянут.",
                                is_heuristic=True,
                            )
                        )
                    db.add(
                        Citation(
                            research_run_id=run.id,
                            url="https://priority-center.ru/",
                            domain="priority-center.ru",
                            title="Priority Center — официальный сайт (DEMO)",
                            supports_brand=mentioned,
                            source_type="other",
                        )
                    )
                    db.add(
                        Citation(
                            research_run_id=run.id,
                            url="https://2gis.ru/vladivostok",
                            domain="2gis.ru",
                            title="2ГИС Владивосток (DEMO)",
                            supports_brand=False,
                            source_type="map",
                        )
                    )
                    for name, pos, rec in (("Demo School A", 2, 3), ("Demo School B", 3, 3)):
                        db.add(
                            CompetitorMention(
                                research_run_id=run.id,
                                competitor_name=name,
                                position=pos,
                                recommendation_score=rec,
                            )
                        )

        await db.commit()
        print(f"Created DEMO research id={research.id} for project {project.name}")
        print("IMPORTANT: these are DEMO results, not real measurements.")


if __name__ == "__main__":
    asyncio.run(main())
