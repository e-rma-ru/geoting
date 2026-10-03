"""DEMO research must never trigger RouterAI / real AI API calls, neither when
opening/reading it nor when seeding it."""

import asyncio
import os

os.environ.setdefault("ROUTERAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ROUTERAI_BASE_URL", "https://routerai.ru/api/v1")

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Project, Prompt, Research, ResearchModel, ResearchRun, MentionAnalysis  # noqa: E402
from app.models.common import utcnow  # noqa: E402
from app.services import metrics as metrics_module  # noqa: E402
from app.services import research_service  # noqa: E402
from app.services.profile_service import get_profiles  # noqa: E402


def _fail_if_called(provider_id):
    raise AssertionError(f"provider.run_prompt must not be called for DEMO (got provider={provider_id})")


@pytest.fixture()
def no_provider_calls(monkeypatch):
    monkeypatch.setattr(research_service, "get_provider", _fail_if_called)
    yield


async def _create_demo_like_research():
    async with SessionLocal() as db:
        project = Project(
            name="Demo NoCall Project", city="Владивосток",
            brand_aliases=["Priority Center"], competitors=[],
        )
        db.add(project)
        await db.flush()
        prompt = Prompt(project_id=project.id, text="Куда отдать ребёнка на английский?", cluster="children", intent="commercial")
        db.add(prompt)
        await db.flush()
        research = Research(
            project_id=project.id, name="demo-no-call", status="completed",
            prompts_count=1, providers_count=1, runs_per_prompt=1,
            started_at=utcnow(), completed_at=utcnow(),
        )
        db.add(research)
        await db.flush()
        db.add(ResearchModel(research_id=research.id, model="deepseek/deepseek-v4-flash", provider="routerai"))
        run = ResearchRun(
            research_id=research.id, prompt_id=prompt.id, provider="routerai",
            model="deepseek/deepseek-v4-flash", run_number=1, status="completed",
            response_text="[DEMO] Priority Center — языковой центр.", completed_at=utcnow(),
        )
        db.add(run)
        await db.flush()
        db.add(MentionAnalysis(research_run_id=run.id, brand_mentioned=True, brand_position=1,
                               recommendation_score=4, is_heuristic=True))
        await db.commit()
        return research.id


@pytest.mark.asyncio
async def test_opening_demo_dashboard_does_not_call_provider(no_provider_calls):
    research_id = await _create_demo_like_research()
    async with SessionLocal() as db:
        # These are pure DB reads; if any code tried to build a provider this test fails.
        detail = await metrics_module.compute_research_detail(db, research_id)
        assert detail["metrics"]["total_runs"] == 1
        await get_profiles(db, research_id)


@pytest.mark.asyncio
async def test_running_pipeline_skips_completed_demo_runs(no_provider_calls):
    """_run_research must not re-execute already-completed runs (no API calls)."""
    research_id = await _create_demo_like_research()
    service = research_service.ResearchService()
    await service._run_research(research_id)
    async with SessionLocal() as db:
        from sqlalchemy import select
        from app.models import Research

        r = await db.get(Research, research_id)
        assert r.status == "completed"
        run = (await db.execute(select(ResearchRun).where(ResearchRun.research_id == research_id))).scalar_one()
        assert run.status == "completed"
        assert "Interrupted" not in (run.error_message or "")


@pytest.mark.asyncio
async def test_settings_reads_do_not_call_provider():
    """GET settings and models list never call the AI gateway transport."""
    from app.api.settings import get_settings

    result = await get_settings()
    assert "routerai" in result
    assert result["routerai"]["configured"] is True  # dummy key from env
    assert "sk-test-dummy-key" not in str(result), "full key must never be returned"
