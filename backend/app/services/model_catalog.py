"""RouterAI model catalog.

Tries the live RouterAI `GET /models` endpoint (cached) and falls back to a
curated list when the gateway is unreachable. All model IDs use RouterAI's real
`provider/model` format. This is the single source of model IDs for the UI —
they are not scattered through the frontend.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import DEFAULT_MODEL_CATALOG, settings

logger = logging.getLogger("geoting.models")

_cache: Optional[Dict[str, Any]] = None  # {"fetched_at": ts, "models": [...]}


async def get_available_models(force_refresh: bool = False) -> List[Dict[str, str]]:
    global _cache
    now = time.monotonic()
    if not force_refresh and _cache and now - _cache["fetched_at"] < 1800:
        return _cache["models"]

    live = await _fetch_live_catalog()
    models = live if live else DEFAULT_MODEL_CATALOG
    _cache = {"fetched_at": now, "models": models}
    return models


async def model_catalog_info() -> Dict[str, Any]:
    global _cache
    source = "routerai-live"
    if _cache and "source" in _cache:
        source = _cache["source"]
    models = await get_available_models()
    resolved_source = _cache.get("source", source) if _cache else source
    return {"models": models, "source": resolved_source}


async def _fetch_live_catalog() -> Optional[List[Dict[str, str]]]:
    """Fetch and filter RouterAI /models to token-priced, text-capable models."""
    base = settings.routerai_base_url.rstrip("/")
    url = f"{base}/models"
    headers = {}
    try:
        from app.secrets import secret_store

        key = secret_store.get("routerai")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(15)) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.info("RouterAI models catalog unavailable, using curated list: %s", exc)
        if _cache is not None:
            _cache["source"] = "config"
        return None

    entries = data.get("data") or []
    result: List[Dict[str, str]] = []
    for e in entries:
        mid = e.get("id")
        if not mid or str(mid).startswith("~"):
            continue
        pricing = e.get("pricing") or {}
        # Only token-priced models are usable via chat completions.
        if "prompt" not in pricing:
            continue
        name = e.get("name") or mid
        result.append({"id": str(mid), "name": str(name)})

    result.sort(key=lambda m: m["id"])
    if _cache is not None:
        _cache["source"] = "routerai-live"
    return result
