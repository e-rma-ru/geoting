"""Runtime, non-secret configuration (default model, etc.) persisted to .env.

Follows the same pattern as SecretStore: an in-memory override applied
immediately, plus persistence to `backend/.env` so the value survives restarts.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import DEFAULT_ROUTERAI_MODEL, settings

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

DEFAULT_MODEL_ENV = "ROUTERAI_DEFAULT_MODEL"


class RuntimeConfigStore:
    def __init__(self) -> None:
        self._runtime: dict = {}

    def get_default_model(self) -> str:
        if DEFAULT_MODEL_ENV in self._runtime:
            return self._runtime[DEFAULT_MODEL_ENV]
        return str(settings.routerai_default_model or DEFAULT_ROUTERAI_MODEL)

    def set_default_model(self, model: str) -> None:
        self._runtime[DEFAULT_MODEL_ENV] = model
        self._persist_env(DEFAULT_MODEL_ENV, model)

    @staticmethod
    def _persist_env(env_name: str, value: str) -> None:
        try:
            lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
        except OSError:
            return
        new_lines = []
        replaced = False
        for line in lines:
            if re.match(rf"^\s*{env_name}\s*=", line):
                new_lines.append(f"{env_name}={value}")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append(f"{env_name}={value}")
        try:
            ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except OSError:
            pass


runtime_config_store = RuntimeConfigStore()
