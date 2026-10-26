"""Regression tests for the panel findings M1, M2 and B7 of the 2026-10-26 review."""

from __future__ import annotations

import re
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from xeon.api.app import create_app
from xeon.api.panel_auth import (
    _DUMMY_HASH,
    MAX_PASSWORD_LENGTH,
    PBKDF2_ITERATIONS,
    LoginThrottle,
    SessionStore,
    authenticate,
    hash_password,
)
from xeon.application.container import build_container
from xeon.config import Settings

PASSWORD = "clave-de-prueba-123"
FORM = {"content-type": "application/x-www-form-urlencoded"}


def _key_file(tmp_path: Path) -> Path:
    path = tmp_path / "secrets" / "xeon_api_key.txt"
    path.write_text("clave-de-api-de-prueba-0123456789", encoding="utf-8")
    return path


def _settings(tmp_path: Path, **extra: object) -> Settings:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    creds = secrets_dir / "advisor.txt"
    creds.write_text(f"asesor1:{hash_password(PASSWORD, iterations=1000)}\n", encoding="utf-8")
    values: dict[str, object] = {
        "llm_provider": "mock",
        "advisor_panel_credentials_file": creds,
        "advisor_panel_max_attempts": 3,
        "xeon_api_auth_disabled": True,
        "_env_file": None,
    }
    values.update(extra)
    return Settings(**values)  # type: ignore[arg-type]


def _client(settings: Settings, peer: str = "127.0.0.1", *, https: bool = False) -> TestClient:
    app = create_app(container=build_container(settings))
    return TestClient(
        app,
        client=(peer, 5000),
        base_url="https://xeon.test" if https else "http://testserver",
        follow_redirects=False,
    )


def _login(client: TestClient, password: str = PASSWORD, user: str = "asesor1", **extra: str):  # type: ignore[no-untyped-def]
    page = client.get("/panel/login", headers=extra)
    token = re.search(r"name='csrf' value='([^']+)'", page.text)
    assert token, page.status_code
    return client.post(
        "/panel/login",
        content=f"csrf={token.group(1)}&username={user}&password={password}",
        headers={**FORM, **extra},
    )


# ---------- M1: constant-time login ----------


def test_unknown_users_cost_as_much_as_known_users() -> None:
    assert _DUMMY_HASH.split("$")[1] == str(PBKDF2_ITERATIONS)
    creds = {"asesor1": hash_password(PASSWORD)}

    def average(user: str) -> float:
        start = time.perf_counter()
        for _ in range(3):
            authenticate(creds, user, "clave-incorrecta-xx")
        return (time.perf_counter() - start) / 3

    known, unknown = average("asesor1"), average("nadie")
    assert unknown > known * 0.4, (known, unknown)  # sonda P2 midio una diferencia de 700x


# ---------- M2: lockout per (IP, user), progressive, trusted proxies ----------


def test_a_stranger_cannot_lock_the_real_advisor_out(tmp_path: Path) -> None:
    settings = _settings(tmp_path, trusted_proxies="10.0.0.5")
    proxy = _client(settings, peer="10.0.0.5", https=True)
    attacker = {"X-Forwarded-For": "7.7.7.7"}
    for _ in range(3):
        assert _login(proxy, password="mala-mala-mala-1", **attacker).status_code == 401
    blocked = _login(proxy, password=PASSWORD, **attacker)
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) >= 1
    # Same username from another client IP behind the same proxy is not locked.
    assert _login(proxy, **{"X-Forwarded-For": "8.8.8.8"}).status_code == 303


def test_lockout_grows_progressively_and_forgets_after_success() -> None:
    now = [0.0]
    throttle = LoginThrottle(max_attempts=2, window_seconds=1000, clock=lambda: now[0])
    throttle.failure("k")
    assert not throttle.blocked("k")
    throttle.failure("k")
    assert throttle.blocked("k") and throttle.retry_after("k") <= 31
    now[0] = 31
    assert not throttle.blocked("k")
    throttle.failure("k")
    assert throttle.blocked("k") and 31 < throttle.retry_after("k") <= 61  # 60 s, then 120 s...
    throttle.success("k")
    assert not throttle.blocked("k")


def test_forwarded_for_is_ignored_from_untrusted_peers(tmp_path: Path) -> None:
    settings = _settings(tmp_path, trusted_proxies="10.0.0.5")
    spoofer = _client(settings, peer="203.0.113.50", https=True)
    for index in range(3):
        _login(spoofer, password="mala-mala-mala-1", **{"X-Forwarded-For": f"1.2.3.{index}"})
    # Rotating X-Forwarded-For does not evade the lock: the real peer address is what counts.
    assert _login(spoofer, **{"X-Forwarded-For": "5.6.7.8"}).status_code == 429


# ---------- B7 ----------


def test_overlong_passwords_are_refused_not_truncated() -> None:
    long_password = "a" * (MAX_PASSWORD_LENGTH + 1)
    stored = {"asesor1": hash_password(long_password, iterations=1000)}
    assert authenticate(stored, "asesor1", long_password) is None
    ok = {"asesor1": hash_password("b" * MAX_PASSWORD_LENGTH, iterations=1000)}
    assert authenticate(ok, "asesor1", "b" * MAX_PASSWORD_LENGTH) == "asesor1"


def test_sessions_and_failure_counters_are_purged() -> None:
    now = [0.0]
    store = SessionStore(ttl_seconds=10, max_sessions=3, clock=lambda: now[0])
    tokens = [store.create("ana").token for _ in range(5)]
    assert store.get(tokens[0]) is None and store.get(tokens[4]) is not None
    now[0] = 11
    store.create("ana")
    assert store.get(tokens[4]) is None
    throttle = LoginThrottle(max_attempts=5, window_seconds=10, max_keys=3, clock=lambda: now[0])
    for index in range(10):
        throttle.failure(f"user-{index}")
    now[0] = 100
    throttle.purge()
    assert throttle._failures == {}


def test_panel_refuses_plain_http_from_remote_peers(tmp_path: Path) -> None:
    settings = _settings(tmp_path, trusted_proxies="10.0.0.5")
    remote = _client(settings, peer="203.0.113.9")
    denied = remote.get("/panel/login")
    assert denied.status_code == 403 and "HTTPS" in denied.json()["detail"]
    assert remote.get("/panel/", headers={"X-Forwarded-Proto": "https"}).status_code == 403
    proxied = _client(settings, peer="10.0.0.5")
    secure = proxied.get("/panel/login", headers={"X-Forwarded-Proto": "https"})
    assert secure.status_code == 200 and "secure" in secure.headers["set-cookie"].lower()
    local = _client(settings, peer="127.0.0.1").get("/panel/login")
    assert local.status_code == 200 and "secure" not in local.headers["set-cookie"].lower()
    hardened = _settings(
        tmp_path,
        app_env="production",
        state_store="postgres",
        xeon_api_auth_disabled=False,
        xeon_api_key_file=_key_file(tmp_path),
    )
    base = build_container(_settings(tmp_path))  # production needs PostgreSQL: swap settings only
    app = create_app(container=replace(base, settings=hardened))
    production = TestClient(app, client=("127.0.0.1", 5000)).get("/panel/login")
    assert "secure" in production.headers["set-cookie"].lower()


# ---------- bounded, paginated inbox ----------


def test_inbox_lists_are_paginated(tmp_path: Path) -> None:
    container = build_container(_settings(tmp_path))
    assert container.advisor_inbox is not None
    for _ in range(120):
        container.advisor_inbox.notify(
            tenant_id="whatsapp", event="advisor_requested", conversation_key=str(uuid4())
        )
    client = TestClient(create_app(container=container), follow_redirects=False)
    assert _login(client).status_code == 303
    first = client.get("/panel/").text
    assert first.count("/panel/events/") == 50 and "Siguiente" in first and "Anterior" not in first
    third = client.get("/panel/?page=3").text
    assert third.count("/panel/events/") == 20 and "Siguiente" not in third and "Anterior" in third
    assert client.get("/panel/?page=abc").text.count("/panel/events/") == 50
