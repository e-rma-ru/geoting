from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger("geoting.analyzer")

ANALYZER_SYSTEM_PROMPT = """Ты — аналитик GEO-исследований. Ты анализируешь ответ AI-ассистента на пользовательский вопрос и оцениваешь, как в нём представлена конкретная компания (бренд).

Схема рекомендаций (recommendation_score):
0 — бренд отсутствует в ответе
1 — бренд просто упомянут
2 — бренд один из перечисленных вариантов
3 — бренд рекомендован
4 — бренд явно рекомендован
5 — бренд среди лучших / предпочтительный вариант

Правила:
- При определении упоминания бренда опирайся на переданный список brand_aliases. Отдельное слово типа "priority" или "приоритет" без связи с компанией НЕ считается упоминанием.
- brand_position — порядковый номер бренда в списке рекомендуемых вариантов (1-based). null, если бренд не упомянут или нет списка.
- accuracy_score (0-100) — насколько корректно и без фактических ошибок описан бренд: услуги, специализация, город, факты.
- sentiment — общий тон упоминания бренда: positive, neutral, negative, mixed, unknown.
- confidence (0-1) — уверенность анализатора в своих оценках.
- competitors — список других компаний/организаций из той же сферы, упомянутых в ответе, с их позицией в списке вариантов и recommendation_score (по той же шкале 0-5).
- reasoning — краткое обоснование (1-3 предложения).

Ответь ТОЛЬКО валидным JSON без markdown-обёртки по схеме:
{
  "brand_mentioned": boolean,
  "brand_position": number|null,
  "recommendation_score": number,
  "sentiment": "positive|neutral|negative|mixed|unknown",
  "accuracy_score": number,
  "confidence": number,
  "reasoning": "string",
  "competitors": [{"name": "string", "position": number|null, "recommendation_score": number|null}]
}
"""


def analyzer_provider_configured() -> bool:
    """True if the RouterAI analyzer has a usable API key."""
    from app.secrets import secret_store

    return bool(secret_store.get("routerai"))


async def chat_json(system_prompt: str, user_content: str) -> Optional[Dict[str, Any]]:
    """Structured-JSON call through the RouterAI gateway.

    Returns a parsed dict or None when RouterAI is not configured or the call
    failed. Never logs API keys.
    """
    from app.secrets import secret_store

    api_key = secret_store.get("routerai")
    if not api_key:
        logger.info("RouterAI is not configured, LLM call skipped")
        return None

    try:
        data = await _call_routerai_chat(api_key, settings.analyzer_model, system_prompt, user_content)
    except Exception as exc:
        logger.warning("Analyzer call via RouterAI failed: %s", exc)
        return None

    content = _extract_text_content(data)
    if not content:
        return None
    parsed = _parse_json_response(content)
    if parsed is None:
        logger.warning("Analyzer returned non-JSON content: %.200s", content)
    return parsed


async def _call_routerai_chat(
    api_key: str, model: str, system_prompt: str, user_content: str
) -> Any:
    base = settings.routerai_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _extract_text_content(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    choices = data.get("choices") or []
    if choices:
        return (choices[0].get("message") or {}).get("content")
    return None


def _parse_json_response(content: str) -> Optional[Dict[str, Any]]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def _build_user_message(
    company_name: str,
    website: Optional[str],
    city: Optional[str],
    description: Optional[str],
    brand_aliases: List[str],
    prompt_text: str,
    answer_text: str,
    sources: List[Dict[str, Any]],
) -> str:
    lines = [
        "## Компания",
        f"name: {company_name}",
        f"website: {website or '—'}",
        f"city: {city or '—'}",
        f"description: {description or '—'}",
        f"brand_aliases: {', '.join(brand_aliases)}",
        "",
        "## Пользовательский вопрос (prompt)",
        prompt_text,
        "",
        "## Ответ AI, который нужно проанализировать",
        answer_text,
    ]
    if sources:
        lines.append("")
        lines.append("## Источники, которые вернул API (title | url)")
        for s in sources:
            lines.append(f"- {s.get('title') or ''} | {s.get('url') or ''}")
    return "\n".join(lines)


async def analyze_with_llm(
    company_name: str,
    website: Optional[str],
    city: Optional[str],
    description: Optional[str],
    brand_aliases: List[str],
    prompt_text: str,
    answer_text: str,
    sources: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Runs the semantic analysis via the configured analyzer LLM."""
    user_message = _build_user_message(
        company_name, website, city, description, brand_aliases,
        prompt_text, answer_text, sources,
    )
    return await chat_json(ANALYZER_SYSTEM_PROMPT, user_message)
