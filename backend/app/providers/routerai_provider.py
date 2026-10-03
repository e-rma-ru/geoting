"""RouterAIProvider — the single AI gateway for Geoting.

RouterAI exposes an OpenAI-compatible `/chat/completions` endpoint. Geoting does
not know details of the upstream AI provider; the concrete model is passed as a
`provider/model` string (e.g. `deepseek/deepseek-v4-flash`, `openai/gpt-5.4`).
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.config import settings
from app.providers.base import AIProvider, AIResponse, Source


class RouterAIProvider(AIProvider):
    provider_id = "routerai"
    display_name = "RouterAI"

    @property
    def url(self) -> str:
        base = (self.config.get("base_url") or settings.routerai_base_url or "").rstrip("/")
        return f"{base}/chat/completions"

    def build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(self, prompt: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        # Keep answers concise for research prompts; no hidden history is sent.
        if self.config.get("max_tokens"):
            payload["max_tokens"] = int(self.config["max_tokens"])
        return payload

    def parse_response(self, data: Any, response_time_ms: int) -> AIResponse:
        text = ""
        model = self.model
        sources: List[Source] = []
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                text = message.get("content") or ""
            model = data.get("model") or model
            # Some gateway responses may include citations; parse them when present.
            for item in data.get("citations") or []:
                if isinstance(item, dict) and item.get("url"):
                    sources.append(Source(url=item.get("url"), title=item.get("title")))
                elif isinstance(item, str):
                    sources.append(Source(url=item))
        return AIResponse(
            provider=self.provider_id,
            model=model,
            text=text,
            sources=sources,
            raw_response=data,
            response_time_ms=response_time_ms,
        )

    def build_request(self, prompt: str):
        return self.url, self.build_payload(prompt), self.build_headers()
