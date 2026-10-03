"""AI Company Profiles: aggregate how AI presents each company across all runs
of a research.

Pipeline:
  existing runs -> candidate runs -> LLM fact extraction (batched) ->
  programmatic mention sets -> normalize labels (LLM or fuzzy) ->
  aggregate frequencies (programmatic) -> save CompanyProfile/Facts.

Profiles are only ever built when the user explicitly asks (POST build); reading
profiles (GET) never triggers LLM calls.
"""

from __future__ import annotations

import difflib
import json
import logging
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.common import utcnow
from app.models.company_profile import CompanyProfile, CompanyProfileFact
from app.models.competitor_mention import CompetitorMention
from app.models.mention_analysis import MentionAnalysis
from app.models.project import Project
from app.models.research import Research
from app.models.research_model import ResearchModel
from app.models.research_run import ResearchRun
from app.services.analyzer import analyzer_provider_configured, chat_json
from app.services.branding import normalize_text

logger = logging.getLogger("geoting.profiles")

CATEGORIES = ("characteristic", "advantage", "program", "audience", "positioning")

CATEGORY_LABELS_RU = {
    "characteristic": "характеристика",
    "advantage": "преимущество",
    "program": "программа/направление",
    "audience": "аудитория",
    "positioning": "позиционирование",
}

EXTRACTION_SYSTEM = """Ты — инструмент извлечения фактов для GEO-аналитики. Твоя задача — извлечь из ответов AI-ассистента структурированные факты о компаниях, которые упоминаются в этих ответах.

СТРОГОЕ ПРАВИЛО (защита от галлюцинаций):
- Извлекай ТОЛЬКО информацию, которая ЯВНО присутствует в тексте ответа.
- НЕ используй общие знания о компаниях, не домысливай, не добавляй факты, которых нет в тексте.
- Если какой-то информации нет — не указывай её (поле null или пустой список).

Категории фактов:
- "characteristic" — характеристика компании (например, "языковой центр", "международное образование"). Формулировка близко к тексту ответа.
- "advantage" — ЯВНО указанное преимущество (например, "небольшие группы", "опытные преподаватели"). Обычное нейтральное описание преимуществом НЕ считается.
- "program" — программа/направление/услуга (например, "английский для детей", "подготовка к ЕГЭ", "разговорный английский").
- "audience" — аудитория (например, "дети", "подростки", "взрослые").

Для каждой компании в ответе укажи:
- name: название компании, как в тексте;
- description: краткое описание компании, как оно сформулировано в ответе (если есть), иначе null;
- positioning: формулировка позиционирования, если она явно есть (например, "центр международного образования"), иначе null;
- facts: список фактов с полями {"category": "...", "text": "формулировка близко к тексту ответа"}.

Компании — только те, что реально упомянуты в ответе. Если компания не упомянута — не включай её.

Ответь ТОЛЬКО валидным JSON без markdown по схеме:
{"results": [{"run_id": number, "companies": [{"name": "string", "description": "string|null", "positioning": "string|null", "facts": [{"category": "string", "text": "string"}]}]}]}
"""

NORMALIZE_SYSTEM = """Ты — инструмент нормализации формулировок для GEO-аналитики. Сгруппируй синонимичные формулировки в один нормализованный ярлык (кластер).

Категория: {category}

Правила:
- Синонимы и перефразировки объединяй в один нормализованный ярлык (например, "занятия в небольших группах", "небольшие группы", "маленькие группы" → "небольшие группы").
- Ярлык должен быть коротким, понятным, без лишних слов.
- Разные по смыслу формулировки НЕ объединяй.
- Нормализованный ярлык пиши на том же языке, что и формулировки.

Верни ТОЛЬКО валидный JSON без markdown:
{"map": {"исходная формулировка": "нормализованный ярлык"}}
Включи ВСЕ переданные формулировки как ключи map."""

DESCRIPTION_SYSTEM = """Ты — инструмент синтеза описания для GEO-аналитики. Ниже — несколько фрагментов, где AI-ассистент описывает одну и ту же компанию в разных ответах.

Задача: сформируй ОДНО сводное описание, которое отражает наиболее типичное представление о компании в этих ответах.

СТРОГОЕ ПРАВИЛО: используй ТОЛЬКО информацию из приведённых фрагментов. Не добавляй знания о компании из других источников, не придумывай характеристики.

Верни ТОЛЬКО валидный JSON без markdown:
{"description": "сводное описание (2-4 предложения)"}"""

SUMMARY_SYSTEM = """Ты — инструмент формирования резюме для GEO-аналитики. Ниже — агрегированные данные о том, как AI-ассистенты представляют компанию в ответах.

Задача: составь краткое резюме (2-4 предложения), отражающее общее представление AI о компании.

СТРОГОЕ ПРАВИЛО: используй ТОЛЬКО приведённые агрегированные данные. Не добавляй факты, которых нет в данных. Не делай причинных утверждений о ранжировании.

Верни ТОЛЬКО валидный JSON без markdown:
{"summary": "резюме"}"""


class ResearchProfilesNotFoundError(Exception):
    pass


_NULL_TOKENS = {"null", "none", "n/a", "na", "-", "—"}


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in _NULL_TOKENS:
        return ""
    return text


def _company_key(raw_name: str, project: Project) -> str:
    """Map an extracted name to the brand (via name/aliases) or a known
    competitor, or keep the extracted name as-is (auto-discovered company)."""
    n = normalize_text(raw_name)
    if not n:
        return (raw_name or "").strip()
    brand = normalize_text(project.name)
    aliases = [normalize_text(a) for a in (project.brand_aliases or [])]
    if n == brand or any(a and n == a for a in aliases) or difflib.SequenceMatcher(None, n, brand).ratio() >= 0.8:
        return project.name
    for c in project.competitors or []:
        cn = normalize_text(c)
        if cn and (n == cn or difflib.SequenceMatcher(None, n, cn).ratio() >= 0.8):
            return c
    return raw_name.strip()


async def get_profiles(db: AsyncSession, research_id: int) -> Dict[str, Any]:
    research = await db.get(Research, research_id)
    if research is None:
        raise ResearchProfilesNotFoundError("Research not found")

    model_rows = list(
        (await db.execute(select(ResearchModel).where(ResearchModel.research_id == research_id))).scalars()
    )
    models = [m.model for m in model_rows]

    profiles_rows = list(
        (
            await db.execute(
                select(CompanyProfile).where(CompanyProfile.research_id == research_id).order_by(CompanyProfile.id)
            )
        ).scalars()
    )
    if not profiles_rows:
        return {
            "research_id": research_id,
            "built": False,
            "built_at": None,
            "total_runs": research.prompts_count * len(models) * research.runs_per_prompt,
            "profiles": [],
        }

    profiles = []
    for p in profiles_rows:
        facts = list(
            (
                await db.execute(
                    select(CompanyProfileFact).where(CompanyProfileFact.profile_id == p.id).order_by(
                        CompanyProfileFact.frequency.desc(), CompanyProfileFact.id
                    )
                )
            ).scalars()
        )
        profiles.append(
            {
                "company_name": p.company_name,
                "mention_count": p.mention_count,
                "top3_count": p.top3_count,
                "average_position": p.average_position,
                "description": p.description,
                "description_raw": p.description_raw or [],
                "summary_text": p.summary_text,
                "is_heuristic": p.is_heuristic,
                "facts": [
                    {
                        "category": f.category,
                        "normalized_label": f.normalized_label,
                        "frequency": f.frequency,
                        "frequency_percent": f.frequency_percent,
                        "raw_mentions": f.raw_mentions or [],
                        "run_ids": f.run_ids or [],
                    }
                    for f in facts
                ],
            }
        )

    return {
        "research_id": research_id,
        "built": True,
        "built_at": max(p.updated_at for p in profiles_rows),
        "total_runs": research.prompts_count * len(models) * research.runs_per_prompt,
        "profiles": profiles,
    }


async def build_profiles(db: AsyncSession, research_id: int) -> Dict[str, Any]:
    """Build AI profiles from existing runs. Explicit user action — may cost API credits."""
    research = await db.get(Research, research_id)
    if research is None:
        raise ResearchProfilesNotFoundError("Research not found")
    project = await db.get(Project, research.project_id)
    if project is None:
        raise ResearchProfilesNotFoundError("Project not found")

    model_rows = list(
        (await db.execute(select(ResearchModel).where(ResearchModel.research_id == research_id))).scalars()
    )
    models = [m.model for m in model_rows]

    runs = list(
        (
            await db.execute(
                select(ResearchRun)
                .where(ResearchRun.research_id == research_id, ResearchRun.status == "completed")
                .order_by(ResearchRun.id)
            )
        ).scalars()
    )
    runs = [r for r in runs if r.response_text and r.response_text.strip()]
    analyses = {
        a.research_run_id: a
        for a in (
            await db.execute(
                select(MentionAnalysis)
                .join(ResearchRun, MentionAnalysis.research_run_id == ResearchRun.id)
                .where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    }
    competitor_rows = list(
        (
            await db.execute(
                select(CompetitorMention)
                .join(ResearchRun, CompetitorMention.research_run_id == ResearchRun.id)
                .where(ResearchRun.research_id == research_id)
            )
        ).scalars()
    )

    # ---- 1. Mention sets (authoritative, matches dashboard counts) ----
    brand_run_ids: Set[int] = {rid for rid, a in analyses.items() if a.brand_mentioned}
    mention_sets: Dict[str, Dict[str, Any]] = {
        project.name: {
            "mention_ids": brand_run_ids,
            "positions": [
                a.brand_position for rid, a in analyses.items() if a.brand_mentioned and a.brand_position is not None
            ],
        }
    }
    competitors_by_run: DefaultDict[str, List[int]] = defaultdict(list)
    competitor_positions: DefaultDict[str, List[int]] = defaultdict(list)
    for cm in competitor_rows:
        competitors_by_run[cm.competitor_name].append(cm.research_run_id)
        if cm.position is not None:
            competitor_positions[cm.competitor_name].append(cm.position)
    for name, ids in competitors_by_run.items():
        mention_sets[name] = {"mention_ids": set(ids), "positions": competitor_positions[name]}

    # ---- 2. Candidate runs for LLM extraction ----
    candidate_ids: Set[int] = set(brand_run_ids)
    for ids in competitors_by_run.values():
        candidate_ids.update(ids)
    for r in runs:
        low_norm = normalize_text(r.response_text)
        if any(normalize_text(a) and normalize_text(a) in low_norm for a in (project.brand_aliases or [])):
            candidate_ids.add(r.id)
        elif any(normalize_text(c) and normalize_text(c) in low_norm for c in (project.competitors or [])):
            candidate_ids.add(r.id)
    candidate_runs = [r for r in runs if r.id in candidate_ids]

    llm_available = analyzer_provider_configured()
    extraction: Dict[int, List[Dict[str, Any]]] = {}
    if candidate_runs and llm_available:
        extraction = await _extract_runs(project, candidate_runs)
    elif not llm_available:
        logger.info("Profiles build: analyzer not configured, extraction skipped (minimal profiles)")

    # ---- 3. Merge extraction facts with mention sets ----
    run_facts: DefaultDict[str, DefaultDict[int, Set[Tuple[str, str]]]] = defaultdict(lambda: defaultdict(set))
    descriptions: DefaultDict[str, List[str]] = defaultdict(list)

    for run_id, companies in extraction.items():
        for comp in companies:
            key = _company_key(str(comp.get("name") or ""), project)
            if run_id not in mention_sets.get(key, {}).get("mention_ids", set()):
                continue
            desc = _clean_text(comp.get("description"))
            if desc:
                descriptions[key].append(desc)
            for f in comp.get("facts") or []:
                cat = str(f.get("category") or "")
                text = _clean_text(f.get("text"))
                if cat in CATEGORIES and text:
                    run_facts[key][run_id].add((cat, text))
            pos_text = _clean_text(comp.get("positioning"))
            if pos_text:
                run_facts[key][run_id].add(("positioning", pos_text))

    # ---- 4. Normalize labels (global per category) ----
    raw_by_category: DefaultDict[str, Set[str]] = defaultdict(set)
    for cats in run_facts.values():
        for facts in cats.values():
            for cat, text in facts:
                raw_by_category[cat].add(text)
    norm_maps: Dict[str, Dict[str, str]] = {}
    for cat in CATEGORIES:
        norm_maps[cat] = await _normalize_labels(cat, list(raw_by_category[cat]))

    # ---- 5. Aggregate facts per company ----
    profile_data: List[Dict[str, Any]] = []
    for key, mset in mention_sets.items():
        mention_ids = mset["mention_ids"]
        mention_count = len(mention_ids)
        if mention_count == 0:
            continue
        positions = mset["positions"]
        top3 = sum(1 for p in positions if p is not None and p <= 3)
        avg_pos = round(sum(positions) / len(positions), 2) if positions else None

        agg: DefaultDict[Tuple[str, str], Set[int]] = defaultdict(set)
        raw_by_norm: DefaultDict[Tuple[str, str], Set[str]] = defaultdict(set)
        for run_id, facts in run_facts.get(key, {}).items():
            for cat, text in facts:
                norm = norm_maps.get(cat, {}).get(text, text)
                agg[(cat, norm)].add(run_id)
                raw_by_norm[(cat, norm)].add(text)

        facts_out = []
        for (cat, norm), rids in agg.items():
            freq = len(rids)
            facts_out.append(
                {
                    "category": cat,
                    "normalized_label": norm,
                    "frequency": freq,
                    "frequency_percent": round(freq / mention_count * 100, 1),
                    "run_ids": sorted(rids),
                    "raw_mentions": sorted(raw_by_norm[(cat, norm)]),
                }
            )
        facts_out.sort(key=lambda f: (-f["frequency"], f["normalized_label"]))

        description = await _synthesize_description(descriptions.get(key, [])) if llm_available else None
        if not llm_available and descriptions.get(key):
            description = max(descriptions[key], key=len)
        summary = None
        if mention_count >= settings.profile_summary_min_mentions:
            if llm_available:
                summary = await _summarize(key, mention_count, top3, facts_out, description)
            else:
                summary = _fallback_summary(key, mention_count, top3, facts_out)

        profile_data.append(
            {
                "company_name": key,
                "mention_count": mention_count,
                "top3_count": top3,
                "average_position": avg_pos,
                "description": description,
                "description_raw": sorted(set(descriptions.get(key, []))),
                "summary_text": summary,
                "is_heuristic": not llm_available,
                "facts": facts_out,
            }
        )

    profile_data.sort(key=lambda p: -p["mention_count"])

    # ---- 6. Persist (replace existing profiles in one transaction) ----
    await db.execute(delete(CompanyProfileFact).where(CompanyProfileFact.profile_id.in_(
        select(CompanyProfile.id).where(CompanyProfile.research_id == research_id)
    )))
    await db.execute(delete(CompanyProfile).where(CompanyProfile.research_id == research_id))
    await db.flush()

    now = utcnow()
    for data in profile_data:
        profile = CompanyProfile(
            research_id=research_id,
            company_name=data["company_name"],
            mention_count=data["mention_count"],
            top3_count=data["top3_count"],
            average_position=data["average_position"],
            description=data["description"],
            description_raw=data["description_raw"],
            summary_text=data["summary_text"],
            is_heuristic=data["is_heuristic"],
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
        await db.flush()
        for f in data["facts"]:
            db.add(
                CompanyProfileFact(
                    profile_id=profile.id,
                    category=f["category"],
                    normalized_label=f["normalized_label"],
                    frequency=f["frequency"],
                    frequency_percent=f["frequency_percent"],
                    raw_mentions=f["raw_mentions"],
                    run_ids=f["run_ids"],
                )
            )
    await db.commit()
    logger.info("AI profiles built for research %s: %d companies", research_id, len(profile_data))
    return await get_profiles(db, research_id)


async def _extract_runs(project: Project, runs: List[ResearchRun]) -> Dict[int, List[Dict[str, Any]]]:
    batch_size = max(1, settings.profile_extraction_batch_size)
    result: Dict[int, List[Dict[str, Any]]] = {}
    for i in range(0, len(runs), batch_size):
        batch = runs[i : i + batch_size]
        user = _build_extraction_user(project, batch)
        parsed = await chat_json(EXTRACTION_SYSTEM, user)
        if not parsed:
            continue
        for entry in parsed.get("results") or []:
            rid = entry.get("run_id")
            companies = entry.get("companies") or []
            if isinstance(rid, int) and isinstance(companies, list):
                result[rid] = companies
    return result


def _build_extraction_user(project: Project, runs: List[ResearchRun]) -> str:
    payload = {
        "brand_aliases": project.brand_aliases or [],
        "known_competitors": project.competitors or [],
        "runs": [{"run_id": r.id, "text": r.response_text} for r in runs],
    }
    return json.dumps(payload, ensure_ascii=False)


async def _normalize_labels(category: str, raw_texts: List[str]) -> Dict[str, str]:
    unique = sorted({t.strip() for t in raw_texts if t and t.strip()})
    if not unique:
        return {}
    mapping: Dict[str, str] = {}
    if analyzer_provider_configured():
        try:
            user = "Формулировки:\n- " + "\n- ".join(unique)
            system = NORMALIZE_SYSTEM.replace("{category}", CATEGORY_LABELS_RU.get(category, category))
            parsed = await chat_json(system, user)
            if parsed and isinstance(parsed.get("map"), dict):
                for raw, norm in parsed["map"].items():
                    mapping[str(raw).strip()] = str(norm).strip()
        except Exception as exc:
            logger.warning("Normalization call failed (%s): %s", category, exc)

    # Fuzzy fallback for anything not mapped
    unmapped = [u for u in unique if u not in mapping]
    groups: List[List[str]] = []
    for u in unmapped:
        placed = False
        for g in groups:
            if difflib.SequenceMatcher(None, g[0], u).ratio() >= 0.82:
                g.append(u)
                placed = True
                break
        if not placed:
            groups.append([u])
    for g in groups:
        canonical = max(g, key=len)
        for u in g:
            mapping.setdefault(u, canonical)
    return mapping


async def _synthesize_description(raw_descriptions: List[str]) -> Optional[str]:
    cleaned = [d.strip() for d in raw_descriptions if d and d.strip()]
    if not cleaned:
        return None
    if len(set(d.lower() for d in cleaned)) == 1:
        return cleaned[0]
    parsed = await chat_json(DESCRIPTION_SYSTEM, "\n---\n".join(cleaned))
    if parsed and parsed.get("description"):
        return str(parsed["description"]).strip()
    return max(cleaned, key=len)


async def _summarize(
    company_name: str,
    mention_count: int,
    top3: int,
    facts: List[Dict[str, Any]],
    description: Optional[str],
) -> Optional[str]:
    top_facts = [
        {
            "category": f["category"],
            "label": f["normalized_label"],
            "frequency": f["frequency"],
            "percent": f["frequency_percent"],
        }
        for f in facts[:8]
    ]
    data = {
        "company": company_name,
        "mention_count": mention_count,
        "top3_count": top3,
        "description": description,
        "top_facts": top_facts,
    }
    parsed = await chat_json(SUMMARY_SYSTEM, json.dumps(data, ensure_ascii=False))
    if parsed and parsed.get("summary"):
        return str(parsed["summary"]).strip()
    return None


def _fallback_summary(company_name: str, mention_count: int, top3: int, facts: List[Dict[str, Any]]) -> str:
    """Deterministic summary when the LLM analyzer is unavailable."""
    parts = [f"{company_name} упомянут(а) AI в {mention_count} ответах"]
    if top3:
        parts.append(f", из них {top3} раз(а) в ТОП-3")
    parts.append(".")
    if facts:
        top = [f"{f['normalized_label']} — {f['frequency']} из {mention_count} ({f['frequency_percent']}%)" for f in facts[:4]]
        parts.append(" Чаще всего AI связывает с компанией: " + "; ".join(top) + ".")
    parts.append(" (Сводка сформирована автоматически на основе данных исследования.)")
    return "".join(parts)
