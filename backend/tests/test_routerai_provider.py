# RouterAI provider unit tests (httpx.MockTransport, no real API calls).
import os

os.environ.setdefault("ROUTERAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ROUTERAI_BASE_URL", "https://routerai.ru/api/v1")
os.environ.setdefault("ANALYZER_MODEL", "deepseek/deepseek-v4-flash")
os.environ.setdefault("ROUTERAI_DEFAULT_MODEL", "deepseek/deepseek-v4-flash")

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.providers.base import ProviderError, ProviderNotConfigured  # noqa: E402
from app.providers.routerai_provider import RouterAIProvider  # noqa: E402

MODEL = "deepseek/deepseek-v4-flash"
ANSWER = "Priority Center — языковой центр во Владивостоке."


def provider_with_transport(handler, api_key="sk-test-dummy-key"):
    return RouterAIProvider(
        {
            "api_key": api_key,
            "model": MODEL,
            "base_url": "https://routerai.ru/api/v1",
            "timeout": 5,
            "max_retries": 2,
            "transport": httpx.MockTransport(handler),
        }
    )


def chat_response(text=ANSWER, model=MODEL):
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl_test",
            "object": "chat.completion",
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 20, "total_tokens": 25},
        },
    )


@pytest.mark.asyncio
async def test_success_parses_text_model_raw():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        body = request.content
        assert b"deepseek/deepseek-v4-flash" in body
        assert request.headers["Authorization"] == "Bearer sk-test-dummy-key"
        assert str(request.url).startswith("https://routerai.ru/api/v1/chat/completions")
        return chat_response()

    provider = provider_with_transport(handler)
    result = await provider.run_prompt("Какой языковой центр выбрать во Владивостоке?")
    assert result.provider == "routerai"
    assert result.model == MODEL
    assert ANSWER in result.text
    assert result.raw_response["id"] == "chatcmpl_test"
    assert result.response_time_ms >= 0
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_parses_citations_if_present():
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "object": "chat.completion",
                "model": MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": ANSWER}, "finish_reason": "stop"}],
                "citations": [{"url": "https://priority-center.ru/", "title": "Priority Center"}],
            },
        )

    provider = provider_with_transport(handler)
    result = await provider.run_prompt("x")
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://priority-center.ru/"


@pytest.mark.asyncio
async def test_not_configured():
    provider = provider_with_transport(lambda req: chat_response(), api_key="")
    with pytest.raises(ProviderNotConfigured):
        await provider.run_prompt("x")


@pytest.mark.asyncio
async def test_401_not_retried():
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": {"message": "invalid api key"}})

    provider = provider_with_transport(handler)
    with pytest.raises(ProviderError):
        await provider.run_prompt("x")
    assert len(calls) == 1, "auth errors must not be retried"


@pytest.mark.asyncio
async def test_400_not_retried():
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"error": {"message": "model not found"}})

    provider = provider_with_transport(handler)
    with pytest.raises(ProviderError):
        await provider.run_prompt("x")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_429_retried_then_fails():
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "rate limit"}})

    provider = provider_with_transport(handler)
    with pytest.raises(ProviderError):
        await provider.run_prompt("x")
    assert 1 < len(calls) <= 3, f"expected retries, got {len(calls)}"


@pytest.mark.asyncio
async def test_500_retried_then_succeeds():
    calls = []

    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, json={"error": {"message": "upstream down"}})
        return chat_response()

    provider = provider_with_transport(handler)
    result = await provider.run_prompt("x")
    assert ANSWER in result.text
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_timeout_raises():
    async def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    provider = provider_with_transport(handler)
    with pytest.raises(ProviderError):
        await provider.run_prompt("x")


@pytest.mark.asyncio
async def test_network_error_raises():
    async def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    provider = provider_with_transport(handler)
    with pytest.raises(ProviderError):
        await provider.run_prompt("x")
