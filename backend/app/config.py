from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


# Fallback model catalog used when the live RouterAI /models endpoint is
# unreachable. IDs use RouterAI's real `provider/model` format. The live
# catalog (fetched and cached by the settings API) takes precedence.
DEFAULT_MODEL_CATALOG: List[dict] = [
    {"id": "deepseek/deepseek-v4-flash", "name": "DeepSeek V4 Flash"},
    {"id": "~deepseek/deepseek-v4-flash-latest", "name": "DeepSeek V4 Flash (latest alias)"},
    {"id": "openai/gpt-5.4", "name": "OpenAI GPT-5.4"},
    {"id": "~openai/gpt-latest", "name": "OpenAI GPT (latest alias)"},
    {"id": "~anthropic/claude-sonnet-latest", "name": "Anthropic Claude Sonnet (latest)"},
    {"id": "~qwen/qwen-latest", "name": "Qwen (latest alias)"},
    {"id": "z-ai/glm-4.6", "name": "Z.ai GLM 4.6"},
]

DEFAULT_ROUTERAI_BASE_URL = "https://routerai.ru/api/v1"
DEFAULT_ROUTERAI_MODEL = "deepseek/deepseek-v4-flash"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Geoting"
    # Database — `geo_lab` kept for compatibility with existing PostgreSQL data.
    # For a fresh VDS deployment, change to `geoting` and update docker-compose.yml.
    database_url: str = "postgresql+psycopg://geo:geo@localhost:5433/geo_lab"

    # RouterAI — the single AI gateway
    routerai_api_key: str = ""
    routerai_base_url: str = DEFAULT_ROUTERAI_BASE_URL
    routerai_default_model: str = DEFAULT_ROUTERAI_MODEL

    # Execution
    max_concurrent_requests: int = 5
    max_retries: int = 3
    request_timeout_seconds: int = 120

    # Analyzer (semantic analysis of answers; goes through RouterAI too)
    analyzer_model: str = DEFAULT_ROUTERAI_MODEL

    # AI Profiles
    profile_extraction_batch_size: int = 5
    profile_frequent_threshold: float = 0.5
    profile_moderate_threshold: float = 0.2
    profile_summary_min_mentions: int = 3

    @property
    def configured(self) -> bool:
        return bool(self.routerai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
