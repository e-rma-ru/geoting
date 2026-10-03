from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field


class Source(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    cited_text: Optional[str] = None


class AIResponse(BaseModel):
    provider: str
    model: str
    text: str
    sources: List[Source] = Field(default_factory=list)
    raw_response: Any = None
    response_time_ms: int = 0


class ProviderError(Exception):
    """Base error for provider failures."""


class ProviderNotConfigured(ProviderError):
    def __init__(self, provider_id: str):
        super().__init__(f"Provider '{provider_id}' is not configured (API key missing).")
        self.provider_id = provider_id


class ProviderAuthError(ProviderError):
    """Invalid/unauthorized API key (HTTP 401/403). Never retried."""


class ProviderUnavailable(ProviderError):
    pass


class AIProvider(ABC):
    provider_id: str = ""
    display_name: str = ""
    url: str = ""

    def __init__(self, config: Dict[str, Any]):
        self.set_config(config)

    def set_config(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.api_key: str = str(config.get("api_key") or "")
        self.model: str = str(config.get("model") or "")
        self.timeout: int = int(config.get("timeout") or 120)
        self.max_retries: int = int(config.get("max_retries") or 3)
        self.transport: Optional[Any] = config.get("transport")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    def build_headers(self) -> Dict[str, str]:
        ...

    @abstractmethod
    def build_payload(self, prompt: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def parse_response(self, data: Any, response_time_ms: int) -> AIResponse:
        ...

    async def run_prompt(self, prompt: str, config: Optional[Dict[str, Any]] = None) -> AIResponse:
        if config is not None:
            self.set_config(config)
        if not self.is_configured:
            raise ProviderNotConfigured(self.provider_id)

        start = time.monotonic()
        data = await self._request_with_retry(prompt)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return self.parse_response(data, elapsed_ms)

    async def _request_with_retry(self, prompt: str) -> Any:
        url, payload, headers = self.build_request(prompt)
        attempt = 0
        last_error: Optional[Exception] = None

        while True:
            try:
                if self.transport is not None:
                    client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout), transport=self.transport)
                else:
                    client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
                async with client:
                    resp = await client.post(url, json=payload, headers=headers)

                if resp.status_code in (429, 500, 502, 503, 504):
                    retry_after = resp.headers.get("retry-after")
                    delay = self._retry_delay(attempt, retry_after)
                    last_error = ProviderUnavailable(
                        f"{self.provider_id}: HTTP {resp.status_code} "
                        f"({resp.text[:200]})"
                    )
                    if attempt >= self.max_retries:
                        raise last_error
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue

                if resp.status_code in (401, 403):
                    # Bad/unauthorized key — retrying will not help.
                    raise ProviderAuthError(
                        f"{self.provider_id}: HTTP {resp.status_code} "
                        f"({resp.text[:200]})"
                    )
                if resp.status_code >= 400:
                    # 400 (bad request / unknown model), 404, 422, ...
                    raise ProviderError(
                        f"{self.provider_id}: HTTP {resp.status_code} "
                        f"({resp.text[:200]})"
                    )

                return resp.json()

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = ProviderUnavailable(f"{self.provider_id}: network error: {exc}")
                if attempt >= self.max_retries:
                    raise last_error
                await asyncio.sleep(self._retry_delay(attempt, None))
                attempt += 1

        raise last_error

    @staticmethod
    def _retry_delay(attempt: int, retry_after: Optional[str]) -> float:
        base = min(2 ** attempt, 30) + random.uniform(0, 0.5)
        if retry_after:
            try:
                base = max(base, float(retry_after))
            except ValueError:
                pass
        return base

    def build_request(self, prompt: str):
        return self.url, self.build_payload(prompt), self.build_headers()
