"""Minimal, real connection test for the RouterAI gateway.

A tiny chat/completions request (max_tokens small) validates the API key, the
account balance and the model availability. GET /models is public on RouterAI
and does NOT validate the key, so it cannot be used as a connection test.
"""

from __future__ import annotations

from typing import Any, Dict

import httpx

from app.config import settings
from app.runtime_config import runtime_config_store

TIMEOUT = httpx.Timeout(30)


async def test_provider_connection(provider_id: str, api_key: str) -> Dict[str, Any]:
    if provider_id != "routerai":
        return {"status": "error", "message": "Неизвестный провайдер", "detail": ""}
    if not api_key:
        return {"status": "not_configured", "message": "Не настроено", "detail": ""}

    base = settings.routerai_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": runtime_config_store.get_default_model(),
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        return {"status": "error", "message": "Не удалось связаться с RouterAI (таймаут)", "detail": "Timeout"}
    except httpx.NetworkError as exc:
        return {"status": "error", "message": "Не удалось связаться с RouterAI", "detail": str(exc)[:300]}

    body = resp.text[:500]
    status = resp.status_code
    if status == 200:
        return {"status": "connected", "message": "Подключение к RouterAI успешно", "detail": ""}
    if status in (401, 403):
        return {"status": "invalid", "message": "API-ключ RouterAI недействителен", "detail": body}
    if status == 402:
        return {"status": "error", "message": "Недостаточно средств на балансе RouterAI", "detail": body}
    if status == 429:
        return {"status": "rate_limited", "message": "Превышен доступный лимит API", "detail": body}
    return {"status": "error", "message": f"Ошибка API (HTTP {status})", "detail": body}
