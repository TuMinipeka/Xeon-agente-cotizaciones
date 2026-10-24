from __future__ import annotations

import os

import httpx
import pytest

# Set before pytest imports test modules (including xeon.api.app, which builds app on import).
os.environ["LLM_PROVIDER"] = "mock"
os.environ["WHATSAPP_SEND_ENABLED"] = "false"


def pytest_sessionstart(session: pytest.Session) -> None:
    # Keep Settings() from reading the developer's .env during test collection.
    from xeon.config import Settings

    Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True)
def block_real_http_transports(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_sync(_transport: httpx.HTTPTransport, _request: httpx.Request) -> httpx.Response:
        raise AssertionError("Las pruebas no pueden usar transporte HTTP real.")

    async def deny_async(
        _transport: httpx.AsyncHTTPTransport, _request: httpx.Request
    ) -> httpx.Response:
        raise AssertionError("Las pruebas no pueden usar transporte HTTP real.")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny_sync)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_async)
