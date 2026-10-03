from typing import Any, Dict

from app.config import settings
from app.providers.base import AIProvider
from app.providers.routerai_provider import RouterAIProvider
from app.runtime_config import runtime_config_store
from app.secrets import secret_store

PROVIDER_REGISTRY: Dict[str, Any] = {
    "routerai": RouterAIProvider,
}

SUPPORTED_PROVIDER_IDS = list(PROVIDER_REGISTRY.keys())

# Labels for historical runs executed through direct providers before Geoting
# migrated to the RouterAI gateway. Kept only for display of existing data.
LEGACY_PROVIDER_LABELS = {
    "openai": "OpenAI (legacy)",
    "gemini": "Google Gemini (legacy)",
    "perplexity": "Perplexity (legacy)",
}


def get_provider_config(provider_id: str) -> Dict[str, Any]:
    if provider_id != "routerai":
        raise ValueError(f"Unknown provider: {provider_id}")
    return {
        "api_key": secret_store.get("routerai"),
        "model": runtime_config_store.get_default_model(),
        "base_url": settings.routerai_base_url,
        "timeout": settings.request_timeout_seconds,
        "max_retries": settings.max_retries,
        "transport": None,
    }


def get_provider(provider_id: str) -> AIProvider:
    if provider_id not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_id}")
    return PROVIDER_REGISTRY[provider_id](get_provider_config(provider_id))


def is_provider_configured(provider_id: str) -> bool:
    try:
        return get_provider(provider_id).is_configured
    except ValueError:
        return False


def provider_status() -> Dict[str, bool]:
    return {pid: is_provider_configured(pid) for pid in SUPPORTED_PROVIDER_IDS}


def provider_display_name(provider_id: str) -> str:
    cls = PROVIDER_REGISTRY.get(provider_id)
    if cls:
        return cls.display_name
    return LEGACY_PROVIDER_LABELS.get(provider_id, provider_id)
