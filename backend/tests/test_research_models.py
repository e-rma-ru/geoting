"""Multi-model Research tests: run counts, per-model coverage, isolation,
and the global concurrency semaphore. Uses httpx.MockTransport + stubbed
analyzer — no real API calls."""

import asyncio
import os

os.environ.setdefault("ROUTERAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ROUTERAI_BASE_URL", "https://routerai.ru/api/v1")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Project, Prompt, Research, ResearchModel, ResearchRun  # noqa: E402
from app.providers.base import ProviderError, ProviderUnavailable  # noqa: E402
from app.providers.routerai_provider import RouterAIProvider  # noqa: E402
from app.services import research_service  # noqa: E402
from tests.conftest import ensure_test_org  # noqa: E402

M1, M2, M3 = "deepseek/deepseek-v4-flash", "openai/gpt-5.4", "qwen/qwen3.7-flash"
CATALOG = [{"id": M1, "name": M1}, {"id": M2, "name": M2}, {"id": M3, "name": M3}]

ANSWER = "Priority Center — языковой центр во Владивостоке. Рекомендую его."
MOCK_ANALYSIS = {
    "brand_mentioned": True,
    "brand_position": 1,
    "recommendation_score": 4,
    "sentiment": "positive",
    "accuracy_score": 88,
    "confidence": 0.8,
    "reasoning": "ok",
    "competitors": [],
}


def _chat_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "x",
            "model": "m",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": ANSWER}, "finish_reason": "stop"}],
        },
    )


@pytest.fixture()
def env(monkeypatch):
    async def fake_catalog():
        return list(CATALOG)

    monkeypatch.setattr(research_service, "get_available_models", fake_catalog)
    # Each test runs on its own event loop; reset the module-level semaphore so
    # it is created inside the current loop (production has a single loop).
    monkeypatch.setattr(research_service, "_shared_semaphore", None)

    async def fake_analyze(**kwargs):
        return dict(MOCK_ANALYSIS)

    import app.services.analysis_service as analysis_service_mod

    monkeypatch.setattr(analysis_service_mod.analyzer_module, "analyze_with_llm", fake_analyze)
    yield


class _TestProvider(RouterAIProvider):
    def __init__(self, *a, bad_model=None, **kw):
        super().__init__(*a, **kw)
        self._bad = bad_model

    async def run_prompt(self, prompt, config=None):
        if self._bad and self.model == self._bad:
            raise ProviderUnavailable("simulated upstream failure for " + self.model)
        return await super().run_prompt(prompt, config)


def _patch_provider(monkeypatch, bad_model=None):
    def make(provider_id):
        if provider_id != "routerai":
            raise ValueError(provider_id)
        return _TestProvider(
            {
                "api_key": "sk-test",
                "model": M1,
                "base_url": "https://routerai.ru/api/v1",
                "timeout": 5,
                "max_retries": 1,
                "transport": httpx.MockTransport(_chat_handler),
            },
            bad_model=bad_model,
        )

    monkeypatch.setattr(research_service, "get_provider", make)


async def _build_project(n_prompts: int):
    org_id = await ensure_test_org()
    async with SessionLocal() as db:
        p = Project(name="MultiModel Test", city="VL", brand_aliases=["Priority Center"], competitors=[], organization_id=org_id)
        db.add(p)
        await db.flush()
        for i in range(n_prompts):
            db.add(Prompt(project_id=p.id, text=f"prompt {i}", cluster="discovery", intent="commercial"))
        await db.commit()
        return p.id


async def _create_and_wait(project_id, models, runs_per_prompt, bad_model=None, monkeypatch=None):
    _patch_provider(monkeypatch, bad_model=bad_model)
    svc = research_service.ResearchService()
    async with SessionLocal() as db:
        research = await svc.create_research(db, project_id=project_id, name="multi", models=models, runs_per_prompt=runs_per_prompt)
        rid = research.id
    async with SessionLocal() as db:
        for _ in range(120):
            r = await db.get(Research, rid)
            if r.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.1)
    return rid


async def _assert_counts(rid, n_prompts, models, runs_per_prompt):
    async with SessionLocal() as db:
        runs = list((await db.execute(select(ResearchRun).where(ResearchRun.research_id == rid))).scalars())
        rows = list((await db.execute(select(ResearchModel).where(ResearchModel.research_id == rid))).scalars())
        assert len(runs) == n_prompts * len(models) * runs_per_prompt, f"expected {n_prompts * len(models) * runs_per_prompt} runs, got {len(runs)}"
        assert sorted(m.model for m in rows) == sorted(models), "research_models mismatch"
        # every model covered every prompt runs_per_prompt times, all independent
        combos = {}
        for run in runs:
            combos.setdefault((run.prompt_id, run.model), 0)
            combos[(run.prompt_id, run.model)] += 1
            assert run.provider == "routerai"
        assert all(v == runs_per_prompt for v in combos.values()), combos
        assert len(combos) == n_prompts * len(models)
        return runs


@pytest.mark.asyncio
async def test_single_model_runs(env, monkeypatch):
    pid = await _build_project(5)
    rid = await _create_and_wait(pid, [M1], 1, monkeypatch=monkeypatch)
    runs = await _assert_counts(rid, 5, [M1], 1)
    assert all(r.status == "completed" for r in runs)


@pytest.mark.asyncio
async def test_two_models_runs(env, monkeypatch):
    pid = await _build_project(5)
    rid = await _create_and_wait(pid, [M1, M2], 1, monkeypatch=monkeypatch)
    runs = await _assert_counts(rid, 5, [M1, M2], 1)
    assert sum(1 for r in runs if r.model == M1) == 5
    assert sum(1 for r in runs if r.model == M2) == 5


@pytest.mark.asyncio
async def test_three_models_two_reps(env, monkeypatch):
    pid = await _build_project(5)
    rid = await _create_and_wait(pid, [M1, M2, M3], 2, monkeypatch=monkeypatch)
    runs = await _assert_counts(rid, 5, [M1, M2, M3], 2)
    assert len(runs) == 30


@pytest.mark.asyncio
async def test_global_semaphore_is_singleton(env):
    import app.services.research_service as rs

    s1 = rs.get_shared_semaphore()
    s2 = rs.get_shared_semaphore()
    assert s1 is s2
    # even via a fresh service instance path it is the same module-level semaphore
    assert rs._shared_semaphore is s1


@pytest.mark.asyncio
async def test_failed_model_does_not_break_others(env, monkeypatch):
    pid = await _build_project(3)
    rid = await _create_and_wait(pid, [M1, M2, M3], 1, bad_model=M3, monkeypatch=monkeypatch)
    async with SessionLocal() as db:
        runs = list((await db.execute(select(ResearchRun).where(ResearchRun.research_id == rid))).scalars())
        by_model = {}
        for r in runs:
            by_model.setdefault(r.model, []).append(r.status)
        assert set(by_model[M1]) == {"completed"}
        assert set(by_model[M2]) == {"completed"}
        assert set(by_model[M3]) == {"failed"}
        for r in runs:
            if r.model == M3:
                assert r.error_message and "simulated" in r.error_message
        # other models were still analyzed
        from app.models import MentionAnalysis

        analyzed = (await db.execute(select(MentionAnalysis).join(ResearchRun).where(ResearchRun.research_id == rid))).scalars().all()
        assert len(analyzed) == 6  # 3 prompts x 2 healthy models
        research = await db.get(Research, rid)
        assert research.status == "completed"


@pytest.mark.asyncio
async def test_duplicate_and_empty_models_rejected(env, monkeypatch):
    _patch_provider(monkeypatch)
    pid = await _build_project(2)
    svc = research_service.ResearchService()
    async with SessionLocal() as db:
        # empty list -> falls back to default, not an error; empty string filtered
        research = await svc.create_research(db, project_id=pid, name="dedupe", models=[M1, M1, "", "  "], runs_per_prompt=1)
        rid = research.id
    await _assert_counts(rid, 2, [M1], 1)
