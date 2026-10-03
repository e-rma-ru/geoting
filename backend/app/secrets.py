"""Runtime secret store for the RouterAI API key.

For the local MVP the secret is persisted to `backend/.env`. The store keeps an
in-memory override so a key saved through the UI takes effect immediately
without restarting the backend. On restart the value is read back from `.env`
via the pydantic settings.

The store is a thin seam: the storage backend can later be replaced with an
encrypted DB column or a secret manager without touching the API/UI layer.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import settings

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

ROUTERAI_ENV_KEY = "ROUTERAI_API_KEY"


class SecretStore:
    def __init__(self) -> None:
        self._runtime: dict = {}

    def get(self, provider_id: str) -> str:
        if provider_id != "routerai":
            return ""
        if ROUTERAI_ENV_KEY in self._runtime:
            return self._runtime[ROUTERAI_ENV_KEY]
        return str(settings.routerai_api_key or "")

    def set(self, provider_id: str, value: str) -> None:
        if provider_id != "routerai":
            raise ValueError(f"Unknown provider: {provider_id}")
        self._runtime[ROUTERAI_ENV_KEY] = value
        self._persist_env(ROUTERAI_ENV_KEY, value)

    def clear(self, provider_id: str) -> None:
        if provider_id != "routerai":
            return
        self._runtime.pop(ROUTERAI_ENV_KEY, None)
        self._persist_env(ROUTERAI_ENV_KEY, "")

    def key_hint(self, provider_id: str) -> str:
        if provider_id != "routerai":
            return ""
        key = self.get(provider_id)
        if not key:
            return ""
        return f"•••{key[-4:]}" if len(key) > 4 else "•••"

    @staticmethod
    def _persist_env(env_name: str, value: str) -> None:
        """Update one variable in backend/.env, preserving other lines.

        Failure to write the file is non-fatal: the runtime value is already
        applied for the current process; the change just won't survive a
        restart until the file is writable.
        """
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


secret_store = SecretStore()
