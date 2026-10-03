import os

os.environ.setdefault("ROUTERAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ROUTERAI_BASE_URL", "https://routerai.ru/api/v1")
os.environ.setdefault("ROUTERAI_DEFAULT_MODEL", "deepseek/deepseek-v4-flash")
os.environ.setdefault("ANALYZER_MODEL", "deepseek/deepseek-v4-flash")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _anyio_backend():
    return
