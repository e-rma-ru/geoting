"""Dev-only E2E verification of the research pipeline over the RouterAI gateway.

Uses an httpx.MockTransport (no real API calls) plus a stubbed analyzer.
This is a test harness, NOT production functionality.
"""

import asyncio
import os

os.environ["ROUTERAI_API_KEY"] = "sk-test-dummy-key"
os.environ["ANALYZER_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["ROUTERAI_DEFAULT_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["MAX_CONCURRENT_REQUESTS"] = "3"

import httpx  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Project, Prompt, Research  # noqa: E402
from app.providers.routerai_provider import RouterAIProvider  # noqa: E402
from app.services import metrics as metrics_module  # noqa: E402
from app.services import research_service  # noqa: E402

MOCK_ANSWER = (
    "При выборе языковой школы для детей во Владивостоке стоит рассмотреть несколько центров. "
    "Priority Center — один из лучших вариантов, школа специализируется на детях и подростках, "
    "проводит занятия для взрослых. Также хорошие отзывы у Competitor A и у Competitor B, "
    "оба предлагают курсы английского для детей."
)

MOCK_ANALYSIS = {
    "brand_mentioned": True,
    "brand_position": 1,
    "recommendation_score": 5,
    "sentiment": "positive",
    "accuracy_score": 90,
    "confidence": 0.85,
    "reasoning": "Priority Center рекомендован первым как один из лучших вариантов для детей.",
    "competitors": [
        {"name": "Competitor A", "position": 2, "recommendation_score": 3},
        {"name": "Competitor B", "position": 3, "recommendation_score": 3},
    ],
}


def make_transport():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "routerai.ru" and request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_test",
                    "object": "chat.completion",
                    "model": "deepseek/deepseek-v4-flash",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": MOCK_ANSWER}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60},
                },
            )
        return httpx.Response(500, json={"error": f"unexpected host {request.url.host}"})

    return httpx.MockTransport(handler)


def patched_get_provider(provider_id):
    if provider_id == "routerai":
        config = {
            "api_key": "sk-test-dummy-key",
            "model": "deepseek/deepseek-v4-flash",
            "base_url": "https://routerai.ru/api/v1",
            "timeout": 30,
            "max_retries": 1,
            "transport": make_transport(),
        }
        return RouterAIProvider(config)
    raise ValueError(f"unexpected provider {provider_id}")


async def main():
    research_service.get_provider = patched_get_provider

    import app.services.analysis_service as analysis_service_mod

    async def fake_analyze(**kwargs):
        return dict(MOCK_ANALYSIS)

    analysis_service_mod.analyzer_module.analyze_with_llm = fake_analyze

    async with SessionLocal() as db:
        project = Project(
            name="Verify Project",
            city="Владивосток",
            website="https://priority-center.ru",
            description="Test",
            brand_aliases=["Priority Center", "Priority", "Приоритет Центр"],
            competitors=[],
        )
        db.add(project)
        await db.flush()
        for text, cluster in [
            ("Куда отдать ребёнка на английский во Владивостоке?", "children"),
            ("Где взрослому выучить английский во Владивостоке?", "adults"),
        ]:
            db.add(Prompt(project_id=project.id, text=text, cluster=cluster, intent="commercial"))
        await db.commit()
        project_id = project.id
        print("Created verify project id:", project_id)

    service = research_service.ResearchService()
    async with SessionLocal() as db:
        research = await service.create_research(
            db, project_id=project_id, name="verify-run", models=["deepseek/deepseek-v4-flash"], runs_per_prompt=2
        )
        research_id = research.id
        print("Created research id:", research_id, "| models:", research.models if hasattr(research, "models") else "n/a")

    async with SessionLocal() as db:
        for _ in range(60):
            r = await db.get(Research, research_id)
            if r.status in ("completed", "failed"):
                break
            await asyncio.sleep(1)

    async with SessionLocal() as db:
        r = await db.get(Research, research_id)
        print("Research status:", r.status)
        from app.models import ResearchModel, ResearchRun

        rmodels = list((await db.execute(__import__("sqlalchemy").select(ResearchModel).where(ResearchModel.research_id == research_id))).scalars())
        assert [m.model for m in rmodels] == ["deepseek/deepseek-v4-flash"], "research_models not persisted"
        runs = list((await db.execute(__import__("sqlalchemy").select(ResearchRun).where(ResearchRun.research_id == research_id))).scalars())
        assert all(run.provider == "routerai" for run in runs), "run.provider != routerai"
        assert all(run.model == "deepseek/deepseek-v4-flash" for run in runs), "run.model not persisted"
        assert all(run.raw_response for run in runs), "raw_response not saved"

        detail = await metrics_module.compute_research_detail(db, research_id)
        print("\n=== METRICS ===")
        print(detail["metrics"]["mention_rate"], "% mention |", detail["metrics"]["citation_rate"], "% citation |", detail["metrics"]["total_runs"], "total")
        assert detail["metrics"]["total_runs"] == 4
        assert detail["metrics"]["failed_runs"] == 0
        assert detail["research"]["models"] == ["deepseek/deepseek-v4-flash"]
        print("\n=== PROMPT RESULTS (first row) ===")
        row = detail["prompt_results"][0]
        print("provider:", row["provider"], "| model:", row["model"], "| mention:", row["brand_mentioned"])
        print("\nALL ROUTERAI PIPELINE ASSERTIONS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
