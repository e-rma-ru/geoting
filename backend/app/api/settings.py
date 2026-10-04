from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.providers import provider_status
from app.runtime_config import runtime_config_store
from app.secrets import secret_store
from app.services.model_catalog import model_catalog_info
from app.services.provider_connection import test_provider_connection

router = APIRouter(prefix="/api", tags=["settings"])

ROUTERAI_DOCS = "https://routerai.ru"


class ProviderKeyIn(BaseModel):
    api_key: str = Field(min_length=1, max_length=500)


class DefaultModelIn(BaseModel):
    model: str = Field(min_length=3, max_length=255)


@router.get("/settings")
async def get_settings():
    status = provider_status()
    configured = status.get("routerai", False)
    return {
        "routerai": {
            "provider_id": "routerai",
            "display_name": "RouterAI",
            "configured": configured,
            "key_hint": secret_store.key_hint("routerai"),
            "base_url": settings.routerai_base_url,
            "default_model": runtime_config_store.get_default_model(),
            "docs": ROUTERAI_DOCS,
        },
        "analyzer": {
            "model": settings.analyzer_model,
        },
        "concurrency": {
            "max_concurrent_requests": settings.max_concurrent_requests,
            "max_retries": settings.max_retries,
            "timeout_seconds": settings.request_timeout_seconds,
        },
    }


@router.post("/settings/routerai/key")
async def save_routerai_key(payload: ProviderKeyIn):
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API-ключ не может быть пустым")
    secret_store.set("routerai", key)
    return {
        "configured": True,
        "key_hint": secret_store.key_hint("routerai"),
    }


@router.delete("/settings/routerai/key")
async def delete_routerai_key():
    secret_store.clear("routerai")
    return {"configured": False, "key_hint": ""}


@router.post("/settings/routerai/test")
async def test_routerai():
    key = secret_store.get("routerai")
    if not key:
        return {
            "status": "not_configured",
            "message": "Сначала введите API-ключ RouterAI",
            "detail": "",
        }
    return await test_provider_connection("routerai", key)


@router.post("/settings/model")
async def set_default_model(payload: DefaultModelIn):
    model = payload.model.strip()
    available = [m["id"] for m in (await model_catalog_info())["models"]]
    if available and model not in available:
        raise HTTPException(status_code=400, detail=f"Модель '{model}' отсутствует в каталоге RouterAI")
    runtime_config_store.set_default_model(model)
    return {"default_model": runtime_config_store.get_default_model()}


@router.get("/settings/models")
async def list_models():
    info = await model_catalog_info()
    return {"models": info["models"], "source": info["source"], "count": len(info["models"])}
