"""Advisor panel: authentication, CSRF, human-only review and client notification."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.create_advisor_credential import upsert_credential
from xeon.api.app import create_app
from xeon.api.panel_auth import (
    LoginThrottle,
    SessionStore,
    authenticate,
    hash_password,
    load_credentials,
    verify_password,
)
from xeon.application.container import AppContainer, build_container
from xeon.application.ports.advisor import AttentionStatus
from xeon.application.ports.channels import ChannelDeliveryError, WhatsAppSendReceipt
from xeon.application.reply import Reply
from xeon.config import Settings
from xeon.domain.quote import InvalidQuoteError, QuoteStatus, review_quote

PASSWORD = "clave-de-prueba-123"
PHONE = "573001234567"
KEY = f"kapso-999000111-{PHONE}"


class FakeChannel:
    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[tuple[str, str]] = []
        self.fail = fail

    async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt:
        if self.fail:
            raise ChannelDeliveryError("fuera de la ventana")
        self.sent.append((recipient_number, text))
        return WhatsAppSendReceipt("i", recipient_number, "m", "sent")

    async def send_reply(self, *, recipient_number: str, reply: Reply) -> WhatsAppSendReceipt:
        return await self.send_text(recipient_number=recipient_number, text=reply.text)

    async def aclose(self) -> None:
        return None


def _settings(tmp_path: Path, *, with_credentials: bool = True) -> Settings:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    creds = secrets_dir / "advisor.txt"
    if with_credentials:
        creds.write_text(f"asesor1:{hash_password(PASSWORD, iterations=1000)}\n", encoding="utf-8")
    return Settings(
        llm_provider="mock",
        advisor_panel_credentials_file=creds,
        advisor_panel_max_attempts=3,
        _env_file=None,
    )


async def _confirm(container: AppContainer, key: str = KEY) -> None:
    agent = container.agent
    for message in (
        "start:products",
        "cemento gris 50kg",
        "product:CEM-50",
        "quantity:10",
        "more:view",
        "delivery:pickup",
        "branch:sede-norte",
        "payment:0",
        "summary:confirm",
    ):
        await agent.respond_reply(message, conversation_key=key)


@pytest.fixture
def channel() -> FakeChannel:
    return FakeChannel()


@pytest.fixture
def container(tmp_path: Path, channel: FakeChannel) -> Iterator[AppContainer]:
    built = build_container(_settings(tmp_path), whatsapp_channel=channel)
    asyncio.run(_confirm(built))
    yield built


@pytest.fixture
def client(container: AppContainer) -> Iterator[TestClient]:
    with TestClient(create_app(container=container), follow_redirects=False) as test_client:
        yield test_client


def _csrf(html: str) -> str:
    match = re.search(r"name='csrf' value='([^']+)'", html)
    assert match
    return match.group(1)


def _login(client: TestClient, password: str = PASSWORD, user: str = "asesor1"):  # type: ignore[no-untyped-def]
    page = client.get("/panel/login")
    return client.post(
        "/panel/login",
        content=f"csrf={_csrf(page.text)}&username={user}&password={password}",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )


def _post(client: TestClient, path: str, **fields: str):  # type: ignore[no-untyped-def]
    page = client.get("/panel/")
    body = "&".join([f"csrf={_csrf(page.text)}", *(f"{k}={v}" for k, v in fields.items())])
    return client.post(
        path, content=body, headers={"content-type": "application/x-www-form-urlencoded"}
    )


def _event(container: AppContainer, kind: str = "client_confirmed"):  # type: ignore[no-untyped-def]
    assert container.advisor_inbox is not None
    return next(e for e in container.advisor_inbox.list_events() if e.kind == kind)


# ---------- authentication ----------


def test_protected_routes_reject_anonymous_requests(
    client: TestClient, container: AppContainer
) -> None:
    event = _event(container)
    assert client.get("/panel/").status_code == 401
    assert client.get(f"/panel/events/{event.id}").status_code == 401
    for action in ("approve", "reject", "attend"):
        assert (
            client.post(f"/panel/events/{event.id}/{action}", content="csrf=x").status_code == 401
        )
    assert _event(container).status is AttentionStatus.PENDIENTE


def test_login_requires_csrf_and_valid_credentials(client: TestClient) -> None:
    no_csrf = client.post(
        "/panel/login",
        content=f"csrf=x&username=asesor1&password={PASSWORD}",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert no_csrf.status_code == 403
    assert _login(client, password="incorrecta-incorrecta").status_code == 401
    assert _login(client, user="otro").status_code == 401
    ok = _login(client)
    assert ok.status_code == 303 and ok.headers["location"] == "/panel/"
    cookie = ok.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/panel" in cookie
    assert client.get("/panel/").status_code == 200


def test_repeated_failures_lock_the_login(client: TestClient) -> None:
    for _ in range(3):
        assert _login(client, password="mala-mala-mala").status_code == 401
    assert _login(client, password=PASSWORD).status_code == 429


def test_panel_is_unavailable_without_credentials(tmp_path: Path) -> None:
    container = build_container(_settings(tmp_path, with_credentials=False))
    with TestClient(create_app(container=container), follow_redirects=False) as anonymous:
        assert anonymous.get("/panel/login").status_code == 503
        assert anonymous.post("/panel/login", content="a=b").status_code == 503


def test_responses_carry_security_headers(client: TestClient) -> None:
    response = client.get("/panel/login")
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert "<script" not in response.text.lower()


def test_password_hashing_sessions_and_throttle_units(tmp_path: Path) -> None:
    stored = hash_password("otra-clave-larga-1", iterations=1000)
    assert stored.startswith("pbkdf2_sha256$1000$")
    assert verify_password("otra-clave-larga-1", stored)
    assert not verify_password("otra", stored) and not verify_password("x", "basura")
    creds_file = tmp_path / "secrets" / "c.txt"
    upsert_credential(creds_file, "Ana", stored)
    upsert_credential(creds_file, "ana", hash_password("segunda-clave-12", iterations=1000))
    loaded = load_credentials(creds_file)
    assert list(loaded) == ["ana"]
    assert authenticate(loaded, "ANA", "segunda-clave-12") == "ana"
    assert authenticate(loaded, "ana", "otra-clave-larga-1") is None
    assert load_credentials(tmp_path / "fuera.txt") == {}
    with pytest.raises(ValueError, match="secrets"):
        upsert_credential(tmp_path / "fuera.txt", "ana", stored)
    now = [0.0]
    store = SessionStore(ttl_seconds=10, clock=lambda: now[0])
    session = store.create("ana")
    assert store.get(session.token) == session
    assert session.token not in repr(store._sessions)
    assert session.csrf not in repr(store._sessions)
    now[0] = 11
    assert store.get(session.token) is None
    throttle = LoginThrottle(max_attempts=2, window_seconds=5, clock=lambda: now[0])
    throttle.failure("k")
    throttle.failure("k")
    assert throttle.blocked("k")
    now[0] = 50
    assert not throttle.blocked("k")


# ---------- review actions ----------


def test_inbox_lists_masked_phone_and_detail_shows_it_to_the_advisor(
    client: TestClient, container: AppContainer
) -> None:
    _login(client)
    listing = client.get("/panel/").text
    assert "Borrador confirmado" in listing and PHONE not in listing and "…4567" in listing
    detail = client.get(f"/panel/events/{_event(container).id}").text
    assert PHONE in detail and "$289.000" in detail and "Sede" in detail and "Vigencia" in detail
    assert "Aprobar para facturación" in detail


def test_approve_needs_csrf_then_marks_billing_and_notifies_the_client(
    client: TestClient, container: AppContainer, channel: FakeChannel
) -> None:
    _login(client)
    event = _event(container)
    path = f"/panel/events/{event.id}/approve"
    assert client.post(path, content="csrf=falso").status_code == 403
    assert client.post(path, content="").status_code == 403
    assert _event(container).status is AttentionStatus.PENDIENTE
    assert _post(client, path).status_code == 303
    saved = _event(container)
    assert saved.status is AttentionStatus.APROBADO and saved.resolved_by == "asesor1"
    assert saved.client_notified is True
    quote = container.quotes.get(saved.quote_id)  # type: ignore[arg-type]
    assert quote is not None and quote.status is QuoteStatus.APPROVED_FOR_BILLING
    ((number, text),) = channel.sent
    assert number == PHONE and "no es una factura ni una reserva" in text
    assert _post(client, path).status_code == 409


def test_reject_requires_a_reason_and_keeps_it_internal(
    client: TestClient, container: AppContainer, channel: FakeChannel
) -> None:
    _login(client)
    event = _event(container)
    path = f"/panel/events/{event.id}/reject"
    assert _post(client, path, reason="").status_code == 409
    assert _post(client, path, reason="%3Cb%3Eprecio+viejo%3C%2Fb%3E").status_code == 303
    saved = _event(container)
    assert saved.status is AttentionStatus.RECHAZADO and saved.reason == "<b>precio viejo</b>"
    quote = container.quotes.get(saved.quote_id)  # type: ignore[arg-type]
    assert quote is not None and quote.status is QuoteStatus.RECHAZADO_POR_ASESOR
    assert "precio viejo" not in channel.sent[0][1]
    page = client.get(f"/panel/events/{event.id}").text
    assert "&lt;b&gt;precio viejo&lt;/b&gt;" in page and "<b>precio viejo</b>" not in page


def test_attend_closes_an_advisor_request_without_touching_quotes(
    container: AppContainer, client: TestClient
) -> None:
    asyncio.run(
        container.agent.respond_reply("global:advisor", conversation_key="otra-conversacion")
    )
    event = _event(container, "advisor_requested")
    _login(client)
    assert _post(client, f"/panel/events/{event.id}/approve").status_code == 409
    assert _post(client, f"/panel/events/{event.id}/attend").status_code == 303
    assert _event(container, "advisor_requested").status is AttentionStatus.ATENDIDO


def test_failed_client_notification_is_recorded_but_review_stands(
    tmp_path: Path,
) -> None:
    failing = FakeChannel(fail=True)
    container = build_container(_settings(tmp_path), whatsapp_channel=failing)
    asyncio.run(_confirm(container))
    with TestClient(create_app(container=container), follow_redirects=False) as client:
        _login(client)
        event = _event(container)
        assert _post(client, f"/panel/events/{event.id}/approve").status_code == 303
    saved = _event(container)
    assert saved.status is AttentionStatus.APROBADO and saved.client_notified is False


def test_phone_number_never_reaches_the_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    channel = FakeChannel()
    container = build_container(_settings(tmp_path), whatsapp_channel=channel)
    asyncio.run(_confirm(container))
    with TestClient(create_app(container=container), follow_redirects=False) as client:
        _login(client)
        _post(client, f"/panel/events/{_event(container).id}/approve")
    assert PHONE not in caplog.text and KEY not in caplog.text


# ---------- the agent cannot take human decisions ----------


def test_agent_messages_cannot_approve_or_reject(container: AppContainer) -> None:
    async def run() -> None:
        for message in (
            "aprobar",
            "approve",
            "APPROVED_FOR_BILLING",
            "summary:approve",
            "admin:approve",
            "global:approve",
            "facturar",
        ):
            await container.agent.respond_reply(message, conversation_key=KEY)
        saved = _event(container)
        quote = container.quotes.get(saved.quote_id)  # type: ignore[arg-type]
        assert quote is not None and quote.status is QuoteStatus.CONFIRMADO_POR_CLIENTE
        assert saved.status is AttentionStatus.PENDIENTE

    asyncio.run(run())


def test_only_the_panel_references_human_review() -> None:
    forbidden = ("APPROVED_FOR_BILLING", "RECHAZADO_POR_ASESOR", "review_quote", "AdvisorReview")
    for folder in ("agent", "adapters", "application"):
        for source in Path("src/xeon", folder).rglob("*.py"):
            if source.name in {"advisor_review.py"}:
                continue
            text = source.read_text(encoding="utf-8")
            assert not any(token in text for token in forbidden), source


def test_draft_cannot_jump_to_billing_approval(container: AppContainer) -> None:
    quote = container.quotes.get(_event(container).quote_id)  # type: ignore[arg-type]
    assert quote is not None
    approved = review_quote(quote, QuoteStatus.APPROVED_FOR_BILLING)
    with pytest.raises(InvalidQuoteError):
        review_quote(approved, QuoteStatus.RECHAZADO_POR_ASESOR)
    with pytest.raises(InvalidQuoteError):
        review_quote(quote, QuoteStatus.DRAFT)
