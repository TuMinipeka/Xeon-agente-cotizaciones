"""Regression tests for the API access-control findings (A2) of the 2026-10-26 review."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from typer.testing import CliRunner

from xeon.adapters.conversation.funnel import InMemoryFunnelRepository
from xeon.adapters.notifications.inbox import InMemoryAdvisorInbox
from xeon.api.app import create_app
from xeon.api.security import (
    ApiAuth,
    SlidingWindowLimiter,
    client_ip,
    is_secure_request,
    trusted_hosts,
)
from xeon.application.container import build_container
from xeon.application.ports.advisor import AttentionStatus
from xeon.application.ports.funnel import FunnelState
from xeon.cli import app as cli_app
from xeon.config import Settings, SettingsError

KEY = "clave-de-api-de-prueba-0123456789"


def _settings(tmp_path: Path, *, key: str | None = KEY, **extra: Any) -> Settings:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    key_file = secrets_dir / "xeon_api_key.txt"
    if key is not None:
        key_file.write_text(key + "\n", encoding="utf-8")
    values: dict[str, Any] = {
        "llm_provider": "mock",
        "xeon_api_key_file": key_file,
        "xeon_api_auth_disabled": False,
        "_env_file": None,
    }
    values.update(extra)
    return Settings(**values)


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), follow_redirects=False)


def _bearer(key: str = KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


# ---------- authentication ----------


def test_v1_routes_reject_missing_or_wrong_keys_and_accept_the_right_one(tmp_path: Path) -> None:
    client = _client(_settings(tmp_path))
    quote_id = uuid.uuid4()
    calls = (
        ("post", "/v1/chat", {"json": {"message": "hola"}}),
        (
            "post",
            "/v1/quotes",
            {"json": {"tenant_id": "whatsapp", "request_id": "r1", "lines": []}},
        ),
        (
            "get",
            "/v1/stock",
            {
                "params": {
                    "sku": "CEM-50",
                    "requested_branch_id": "sede-norte",
                    "evaluated_at": "2026-10-26T12:00:00+00:00",
                }
            },
        ),
        ("get", f"/v1/quotes/{quote_id}", {"params": {"tenant_id": "whatsapp"}}),
    )
    for method, path, kwargs in calls:
        assert getattr(client, method)(path, **kwargs).status_code == 401, path
        wrong = getattr(client, method)(
            path, headers=_bearer("otra-clave-incorrecta-000000"), **kwargs
        )
        assert wrong.status_code == 401, path
        assert (
            getattr(client, method)(path, headers={"Authorization": KEY}, **kwargs).status_code
            == 401
        )
    assert client.post("/v1/chat", json={"message": "hola"}, headers=_bearer()).status_code == 200
    assert client.get("/health").status_code == 200


def test_signed_webhook_does_not_use_the_api_key(tmp_path: Path) -> None:
    response = _client(_settings(tmp_path)).post(
        "/v1/channels/whatsapp/kapso/webhook", content=b"{}", headers=_bearer()
    )
    assert response.status_code == 401 and "Firma" in response.json()["detail"]


def test_production_refuses_to_start_without_a_key_or_with_auth_disabled(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="requiere la clave"):
        create_app(_settings(tmp_path, key=None, app_env="production"))
    with pytest.raises(SettingsError, match="no se admite"):
        create_app(_settings(tmp_path, app_env="production", xeon_api_auth_disabled=True))
    assert _client(_settings(tmp_path, app_env="production")).get("/health").status_code == 200


def test_development_without_key_fails_closed_unless_explicitly_disabled(tmp_path: Path) -> None:
    closed = _client(_settings(tmp_path, key=None))
    assert closed.post("/v1/chat", json={"message": "hola"}).status_code == 503
    explicit = _client(_settings(tmp_path, key=None, xeon_api_auth_disabled=True))
    assert explicit.post("/v1/chat", json={"message": "hola"}).status_code == 200


def test_short_or_misplaced_key_files_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="24 caracteres"):
        create_app(_settings(tmp_path, key="corta"))
    outside = tmp_path / "fuera.txt"
    outside.write_text(KEY, encoding="utf-8")
    with pytest.raises(SettingsError, match="secrets"):
        _settings(tmp_path, key=None, xeon_api_key_file=outside).read_api_key()


def test_api_auth_compares_digests_not_raw_values() -> None:
    auth = ApiAuth.from_key(KEY)
    assert (
        auth.check(KEY)
        and not auth.check(KEY + "x")
        and not auth.check("")
        and not auth.check(None)
    )
    assert not ApiAuth("disabled").check(KEY)


# ---------- the anonymous flood (sonda P3) ----------


def test_anonymous_chat_flood_cannot_fill_the_advisor_inbox(tmp_path: Path) -> None:
    container = build_container(_settings(tmp_path))
    client = TestClient(create_app(container=container), follow_redirects=False)
    for _ in range(50):
        response = client.post(
            "/v1/chat", json={"message": "asesor", "conversation_id": str(uuid.uuid4())}
        )
        assert response.status_code == 401
    assert container.advisor_inbox is not None
    assert container.advisor_inbox.list_events() == ()


def test_chat_is_rate_limited_per_conversation_and_per_ip(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path, chat_rate_limit_conversation_per_minute=3, chat_rate_limit_ip_per_minute=5
    )
    client = _client(settings)
    same = str(uuid.uuid4())
    statuses = [
        client.post(
            "/v1/chat", json={"message": "hola", "conversation_id": same}, headers=_bearer()
        ).status_code
        for _ in range(4)
    ]
    assert statuses == [200, 200, 200, 429]
    limited = client.post(
        "/v1/chat", json={"message": "hola", "conversation_id": same}, headers=_bearer()
    )
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
    fresh = [
        client.post(
            "/v1/chat",
            json={"message": "hola", "conversation_id": str(uuid.uuid4())},
            headers=_bearer(),
        ).status_code
        for _ in range(3)
    ]
    assert 429 in fresh  # the IP budget (5/min) is spent after 5 accepted calls


def test_chat_text_is_capped(tmp_path: Path) -> None:
    client = _client(_settings(tmp_path))
    assert (
        client.post("/v1/chat", json={"message": "a" * 1001}, headers=_bearer()).status_code == 422
    )
    assert (
        client.post("/v1/chat", json={"message": "a" * 1000}, headers=_bearer()).status_code == 200
    )


# ---------- memory bounds ----------


def test_advisor_inbox_is_bounded_and_keeps_client_confirmations() -> None:
    inbox = InMemoryAdvisorInbox(max_events=5)
    confirmed = uuid.uuid4()
    inbox.notify(tenant_id="t", event="client_confirmed", conversation_key="c0", quote_id=confirmed)
    for index in range(30):
        inbox.notify(tenant_id="t", event="advisor_requested", conversation_key=f"c{index + 1}")
    events = inbox.list_events()
    assert len(events) == 5
    assert any(e.kind == "client_confirmed" and e.quote_id == confirmed for e in events)
    resolved = inbox.list_events(status=AttentionStatus.PENDIENTE)
    assert len(resolved) == 5


def test_funnel_state_is_lru_bounded() -> None:
    states = InMemoryFunnelRepository(max_conversations=3)
    for index in range(5):
        states.save(f"k{index}", FunnelState(step="producto"))
    assert states.get("k0") == FunnelState() and states.get("k1") == FunnelState()
    assert states.get("k4").step == "producto"


def test_sliding_window_limiter_forgets_old_hits_and_bounds_keys() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(limit=2, window_seconds=10, max_keys=3, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    now[0] = 11
    assert limiter.allow("a")
    for key in "bcde":
        limiter.allow(key)
    assert len(limiter._hits) == 3


# ---------- trusted proxies ----------


def _request(peer: str, headers: dict[str, str], scheme: str = "http") -> Request:
    return Request(
        {
            "type": "http",
            "scheme": scheme,
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (peer, 1234),
            "server": ("x", 80),
        }
    )


def test_forwarded_headers_are_honoured_only_from_trusted_proxies() -> None:
    trusted = trusted_hosts("10.0.0.5, 10.0.0.6")
    xff = {"X-Forwarded-For": "6.6.6.6, 203.0.113.9, 10.0.0.6", "X-Forwarded-Proto": "https"}
    assert client_ip(_request("10.0.0.5", xff), trusted) == "203.0.113.9"
    assert client_ip(_request("198.51.100.1", xff), trusted) == "198.51.100.1"
    assert is_secure_request(_request("10.0.0.5", xff), trusted)
    assert not is_secure_request(_request("198.51.100.1", xff), trusted)
    with pytest.raises(ValueError):
        trusted_hosts("no-es-una-ip")


# ---------- CLI sends the key from the secrets file ----------


def test_cli_reads_the_key_from_the_secrets_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "k.txt").write_text(KEY, encoding="utf-8")
    monkeypatch.setenv("XEON_API_KEY_FILE", str(secrets_dir / "k.txt"))
    seen: dict[str, Any] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"reply": "ok"}

    def fake_post(url: str, json: dict[str, Any], timeout: float, headers: dict[str, str]) -> Any:
        seen["headers"] = headers
        return _Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    result = CliRunner().invoke(cli_app, ["chat", "hola"])
    assert result.exit_code == 0
    assert seen["headers"] == {"Authorization": f"Bearer {KEY}"}
    assert KEY not in result.output
