"""Dev-only verification of AI Profiles aggregation with a stubbed LLM.

Validates: mention consistency, normalization of synonyms, programmatic
frequencies, run_ids, raw formulations. No real API calls.
"""

import asyncio
import json
import os

os.environ["ROUTERAI_API_KEY"] = "sk-test-dummy-key"
os.environ["ROUTERAI_DEFAULT_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["ANALYZER_MODEL"] = "deepseek/deepseek-v4-flash"

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Project, Prompt, Research, ResearchRun, MentionAnalysis, CompetitorMention,
    CompanyProfile, CompanyProfileFact,
)
from app.services import profile_service  # noqa: E402

TEXT_A = (
    "Priority Center — языковой центр во Владивостоке. Занятия проходят в небольших группах. "
    "Опытные преподаватели. Английский для детей."
)
TEXT_B = (
    "Priority Center предлагает английский для детей и занятия в маленьких группах, "
    "опытные преподаватели, подготовка к ЕГЭ."
)
TEXT_C = "Рекомендую обратить внимание на Simple Smart, у них сильные программы для детей."
TEXT_D = "Priority Center: английский для детей и корпоративный английский."


async def mock_chat_json(system_prompt, user_content):
    if "извлечения фактов" in system_prompt:
        payload = json.loads(user_content)
        runs = payload.get("runs", [])
        results = []
        for r in runs:
            rid = r["run_id"]
            if rid == RUN_IDS[0]:
                results.append({
                    "run_id": rid,
                    "companies": [{
                        "name": "Priority Center",
                        "description": "Языковой центр во Владивостоке.",
                        "positioning": "языковой центр",
                        "facts": [
                            {"category": "characteristic", "text": "языковой центр"},
                            {"category": "advantage", "text": "занятия проходят в небольших группах"},
                            {"category": "advantage", "text": "опытные преподаватели"},
                            {"category": "program", "text": "английский для детей"},
                        ],
                    }],
                })
            elif rid == RUN_IDS[1]:
                results.append({
                    "run_id": rid,
                    "companies": [{
                        "name": "Priority Center",
                        "description": "Языковой центр во Владивостоке.",
                        "positioning": None,
                        "facts": [
                            {"category": "advantage", "text": "занятия в маленьких группах"},
                            {"category": "advantage", "text": "опытные преподаватели"},
                            {"category": "program", "text": "детский английский"},
                            {"category": "program", "text": "подготовка к ЕГЭ"},
                        ],
                    }],
                })
            elif rid == RUN_IDS[2]:
                results.append({
                    "run_id": rid,
                    "companies": [{
                        "name": "Simple Smart",
                        "description": None,
                        "positioning": None,
                        "facts": [{"category": "program", "text": "английский для детей"}],
                    }],
                })
            elif rid == RUN_IDS[3]:
                results.append({
                    "run_id": rid,
                    "companies": [{
                        "name": "Priority Center",
                        "description": "Языковой центр во Владивостоке.",
                        "positioning": None,
                        "facts": [
                            {"category": "program", "text": "английский для детей"},
                            {"category": "program", "text": "корпоративный английский"},
                        ],
                    }],
                })
        return {"results": results}
    if "нормализации" in system_prompt:
        lines = [l for l in user_content.split("\n- ") if l]
        raw_list = lines[1:] if lines else []
        mapping = {}
        for r in raw_list:
            low = r.lower()
            if "групп" in low:
                mapping[r] = "небольшие группы"
            elif "детск" in low and "англ" in low:
                mapping[r] = "английский для детей"
            elif "егэ" in low:
                mapping[r] = "подготовка к экзаменам"
            elif "преподавател" in low:
                mapping[r] = "опытные преподаватели"
            elif "языковой центр" in low:
                mapping[r] = "языковой центр"
            else:
                mapping[r] = r
        return {"map": mapping}
    if "сводное описание" in system_prompt:
        return {"description": "Языковой центр во Владивостоке, обучение английскому в группах."}
    if "резюме" in system_prompt:
        return {"summary": "AI представляет Priority Center как языковой центр с акцентом на детский английский."}
    return None


RUN_IDS = []


async def main():
    profile_service.chat_json = mock_chat_json
    profile_service.analyzer_provider_configured = lambda: True

    async with SessionLocal() as db:
        project = Project(
            name="Priority Center", city="Владивосток",
            brand_aliases=["Priority Center", "Priority", "Приоритет Центр"],
            competitors=["Simple Smart"],
        )
        db.add(project)
        await db.flush()
        p1 = Prompt(project_id=project.id, text="Где учить английский?", cluster="discovery", intent="commercial")
        p2 = Prompt(project_id=project.id, text="Куда отдать ребёнка?", cluster="children", intent="commercial")
        db.add_all([p1, p2])
        await db.flush()
        research = Research(project_id=project.id, name="profiles-test", status="completed",
                            prompts_count=2, providers_count=1, runs_per_prompt=2)
        db.add(research)
        await db.flush()

        for i, (prompt, text, mentioned) in enumerate([
            (p1, TEXT_A, True), (p1, TEXT_B, True), (p2, TEXT_C, False), (p2, TEXT_D, True),
        ]):
            run = ResearchRun(research_id=research.id, prompt_id=prompt.id, provider="openai",
                              model="m", run_number=i + 1, status="completed", response_text=text)
            db.add(run)
            await db.flush()
            RUN_IDS.append(run.id)
            db.add(MentionAnalysis(research_run_id=run.id, brand_mentioned=mentioned,
                                   brand_position=1 if mentioned else None,
                                   recommendation_score=4 if mentioned else 0))
            if not mentioned:
                db.add(CompetitorMention(research_run_id=run.id, competitor_name="Simple Smart",
                                         position=1, recommendation_score=4))
        await db.commit()
        research_id = research.id
        print("Test research id:", research_id)

    result = await profile_service.build_profiles(SessionLocal, research_id) if False else await _build(SessionLocal, research_id)

    profiles = {p["company_name"]: p for p in result["profiles"]}
    pc = profiles.get("Priority Center")
    ss = profiles.get("Simple Smart")
    assert pc is not None, "Priority Center profile missing"
    assert pc["mention_count"] == 3, f"Priority mentions expected 3, got {pc['mention_count']}"
    assert ss is not None and ss["mention_count"] == 1, "Simple Smart profile missing/wrong"
    assert pc["description_raw"], "raw descriptions missing"
    assert pc["summary_text"], "summary missing"

    by_label = {f["normalized_label"]: f for f in pc["facts"]}
    assert "небольшие группы" in by_label, f"normalization failed: {list(by_label.keys())}"
    g = by_label["небольшие группы"]
    assert g["frequency"] == 2, f"группы freq expected 2, got {g['frequency']}"
    assert g["frequency_percent"] == round(2 / 3 * 100, 1), f"expected 66.7%, got {g['frequency_percent']}"
    assert sorted(g["raw_mentions"]) == sorted(["занятия проходят в небольших группах", "занятия в маленьких группах"]), g["raw_mentions"]
    assert sorted(g["run_ids"]) == sorted(RUN_IDS[:2]), g["run_ids"]

    ege = by_label.get("подготовка к экзаменам")
    assert ege and ege["frequency"] == 1, "ЕГЭ fact missing/wrong"
    kids = by_label.get("английский для детей")
    assert kids and kids["frequency"] == 3, f"детский английский should normalize and count 3, got {kids}"
    assert ss["mention_count"] == 1 and ss["summary_text"] is None, "small-sample summary guard failed"

    async with SessionLocal() as db:
        sel = __import__("sqlalchemy").select
        rows = (await db.execute(sel(CompanyProfile).where(CompanyProfile.research_id == research_id))).scalars().all()
        pids = [p.id for p in rows]
        facts = (await db.execute(sel(CompanyProfileFact).where(CompanyProfileFact.profile_id.in_(pids)))).scalars().all()
        assert len(rows) == 2, f"expected 2 saved profiles, got {len(rows)}"
        assert len(facts) >= 5, f"expected facts, got {len(facts)}"

    print("ALL PROFILE ASSERTIONS PASSED")
    print("Priority facts:", [(f['category'], f['normalized_label'], f['frequency']) for f in pc['facts']])


async def _build(session_factory, research_id):
    async with session_factory() as db:
        return await profile_service.build_profiles(db, research_id)


if __name__ == "__main__":
    asyncio.run(main())
