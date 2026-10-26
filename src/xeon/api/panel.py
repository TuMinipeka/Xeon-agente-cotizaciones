"""Advisor web panel: server-rendered HTML, authenticated, CSRF-protected, no external JS."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from html import escape
from urllib.parse import parse_qs
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from xeon.adapters.pdf import load_pdf_renderer
from xeon.api.panel_auth import (
    LoginThrottle,
    PanelSession,
    SessionStore,
    authenticate,
    load_credentials,
)
from xeon.api.security import client_ip, is_local_peer, is_secure_request, trusted_hosts
from xeon.application.advisor_review import AdvisorReview, ReviewError
from xeon.application.container import AppContainer
from xeon.application.ports.advisor import AdvisorEvent, AttentionStatus
from xeon.application.ports.channels import ChannelDeliveryError
from xeon.application.quote_document import build_quote_pdf_document, quote_number
from xeon.application.reply import Reply
from xeon.domain.quote import QuoteStatus

SESSION_COOKIE = "xeon_panel_session"
LOGIN_CSRF_COOKIE = "xeon_panel_login_csrf"
MAX_FORM_BYTES = 8192
PAGE_SIZE = 50
KIND_LABEL = {"client_confirmed": "Borrador confirmado", "advisor_requested": "Pide asesor"}
STYLE = (
    "body{font-family:system-ui,sans-serif;margin:0;background:#f4f5f7;color:#1c1f24}"
    "main{max-width:880px;margin:0 auto;padding:16px}"
    "header{background:#14213d;color:#fff;padding:12px 16px;display:flex;"
    "justify-content:space-between;align-items:center}"
    "table{width:100%;border-collapse:collapse;background:#fff}"
    "th,td{padding:8px;border-bottom:1px solid #dde1e6;text-align:left}"
    "a{color:#0b5cad}.card{background:#fff;padding:12px 16px;margin:12px 0;border-radius:6px}"
    "button{padding:8px 14px;margin:4px 4px 4px 0;border:0;border-radius:4px;"
    "background:#0b5cad;color:#fff;cursor:pointer}"
    ".ok{background:#1b7f3b}.bad{background:#b3261e}.muted{color:#5b6470}"
    "input,textarea{padding:6px;width:100%;box-sizing:border-box}"
)


def phone_from_key(conversation_key: str | None) -> str | None:
    """WhatsApp conversations are keyed kapso-<phone_number_id>-<customer phone>."""
    if not conversation_key or not conversation_key.startswith("kapso-"):
        return None
    number = conversation_key.rsplit("-", 1)[-1]
    return number if number.isdigit() and len(conversation_key.split("-")) >= 3 else None


def _page_number(raw: str | None) -> int:
    return int(raw) if raw and raw.isdigit() and 1 <= int(raw) <= 100_000 else 1


def _pager(page: int, *, more: bool) -> str:
    links = []
    if page > 1:
        links.append(f"<a href='/panel/?page={page - 1}'>← Anterior</a>")
    if more:
        links.append(f"<a href='/panel/?page={page + 1}'>Siguiente →</a>")
    return f"<p>Página {page} · {' · '.join(links)}</p>" if links else ""


def _mask(number: str | None) -> str:
    return f"…{number[-4:]}" if number else "sin WhatsApp"


def _money(value: Decimal) -> str:
    """Colombian peso style: $289.000 (the panel only shows the backend-computed amounts)."""
    return "$" + f"{value:,.0f}".replace(",", ".")


def _time(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "—"


def build_panel_router(container: AppContainer) -> APIRouter:
    settings = container.settings
    trusted = trusted_hosts(settings.trusted_proxies)

    def require_secure_transport(request: Request) -> None:
        """Credentials and sessions only travel over HTTPS, except for loopback development."""
        if not is_secure_request(request, trusted) and not is_local_peer(request):
            raise HTTPException(status_code=403, detail="El panel requiere HTTPS.")

    router = APIRouter(prefix="/panel", dependencies=[Depends(require_secure_transport)])
    sessions = SessionStore(ttl_seconds=settings.advisor_panel_session_minutes * 60)
    throttle = LoginThrottle(
        max_attempts=settings.advisor_panel_max_attempts,
        window_seconds=settings.advisor_panel_lockout_minutes * 60,
    )
    ip_throttle = LoginThrottle(
        max_attempts=settings.advisor_panel_max_attempts * 4,
        window_seconds=settings.advisor_panel_lockout_minutes * 60,
    )
    inbox = container.advisor_inbox

    def enqueue_decision(event: AdvisorEvent, message: str) -> None:
        if container.outbound_queue is None:
            return
        phone = phone_from_key(event.conversation_key)
        if phone is None:
            if inbox is not None:
                inbox.save(replace(event, client_notified=False))
            return
        container.outbound_queue.put(
            key=f"advisor:{event.id}:decision",
            recipient_number=phone,
            reply=Reply(message),
            advisor_event_id=event.id,
        )

    review = (
        AdvisorReview(
            inbox,
            container.quotes,
            on_decision=enqueue_decision if container.outbound_queue is not None else None,
        )
        if inbox is not None
        else None
    )

    def secure_cookie(request: Request) -> bool:
        return settings.app_env == "production" or is_secure_request(request, trusted)

    def respond(content: str, *, status: int = 200, title: str = "Panel del asesor") -> Response:
        nonce = secrets.token_urlsafe(12)
        document = (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title><style nonce='{nonce}'>{STYLE}</style></head>"
            f"<body>{content}</body></html>"
        )
        response = HTMLResponse(document, status_code=status)
        response.headers["Content-Security-Policy"] = (
            f"default-src 'none'; style-src 'nonce-{nonce}'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    def layout(session: PanelSession, body: str) -> str:
        return (
            "<header><strong>XEON · Panel del asesor</strong><form method='post' "
            "action='/panel/logout'>"
            f"<input type='hidden' name='csrf' value='{escape(session.csrf)}'>"
            f"<span>{escape(session.username)} </span><button>Salir</button></form></header>"
            f"<main>{body}</main>"
        )

    def session_of(request: Request) -> PanelSession | None:
        return sessions.get(request.cookies.get(SESSION_COOKIE))

    def unauthorized() -> Response:
        return respond(
            "<main><h1>Acceso no autorizado</h1><p><a href='/panel/login'>Iniciar sesión</a></p>"
            "</main>",
            status=401,
        )

    async def form(request: Request) -> dict[str, str] | None:
        body = await request.body()
        if len(body) > MAX_FORM_BYTES:
            return None
        parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        return {key: values[0] for key, values in parsed.items()}

    def csrf_ok(session: PanelSession, data: dict[str, str]) -> bool:
        return hmac.compare_digest(data.get("csrf", ""), session.csrf)

    def forbidden() -> Response:
        return respond("<main><h1>Solicitud rechazada</h1></main>", status=403)

    def login_page(
        request: Request, token: str, *, message: str = "", status: int = 200
    ) -> Response:
        notice = f"<p class='bad'>{escape(message)}</p>" if message else ""
        response = respond(
            "<main><h1>Panel del asesor</h1>"
            f"{notice}<form method='post' action='/panel/login'>"
            f"<input type='hidden' name='csrf' value='{escape(token)}'>"
            "<p><label>Usuario<input name='username' autocomplete='username' required>"
            "</label></p><p><label>Contraseña<input type='password' name='password' "
            "autocomplete='current-password' required></label></p><button>Entrar</button>"
            "</form></main>",
            status=status,
            title="Acceso",
        )
        response.set_cookie(
            LOGIN_CSRF_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            secure=secure_cookie(request),
            path="/panel",
            max_age=900,
        )
        return response

    def configured() -> dict[str, str]:
        return load_credentials(settings.advisor_panel_credentials_file)

    @router.get("/login")
    async def login_form(request: Request) -> Response:
        if not configured():
            return respond("<main><h1>Panel no configurado</h1></main>", status=503)
        return login_page(request, secrets.token_urlsafe(24))

    @router.post("/login")
    async def login(request: Request) -> Response:
        credentials = configured()
        if not credentials:
            return respond("<main><h1>Panel no configurado</h1></main>", status=503)
        data = await form(request)
        cookie = request.cookies.get(LOGIN_CSRF_COOKIE, "")
        if data is None or not cookie or not hmac.compare_digest(data.get("csrf", ""), cookie):
            return forbidden()
        username = data.get("username", "")[:64]
        ip = client_ip(request, trusted)
        # Locks are per (IP, user): a stranger cannot lock the real advisor out from another IP.
        pair = f"{ip}|{username.strip().lower()}"
        if throttle.blocked(pair) or ip_throttle.blocked(ip):
            wait = max(throttle.retry_after(pair), ip_throttle.retry_after(ip))
            blocked = respond(
                "<main><h1>Demasiados intentos</h1><p>Espera unos minutos.</p></main>",
                status=429,
            )
            blocked.headers["Retry-After"] = str(wait)
            return blocked
        # No truncation: a password over the limit simply fails (the script has the same limit).
        password = data.get("password", "")
        user = authenticate(credentials, username, password)
        if user is None:
            throttle.failure(pair)
            ip_throttle.failure(ip)
            return login_page(
                request,
                secrets.token_urlsafe(24),
                message="Credenciales inválidas.",
                status=401,
            )
        throttle.success(pair)
        session = sessions.create(user)
        redirect = RedirectResponse("/panel/", status_code=303)
        redirect.set_cookie(
            SESSION_COOKIE,
            session.token,
            httponly=True,
            samesite="strict",
            secure=secure_cookie(request),
            path="/panel",
            max_age=int(sessions.ttl_seconds),
        )
        redirect.delete_cookie(LOGIN_CSRF_COOKIE, path="/panel")
        return redirect

    @router.post("/logout")
    async def logout(request: Request) -> Response:
        session = session_of(request)
        if session is None:
            return unauthorized()
        data = await form(request)
        if data is None or not csrf_ok(session, data):
            return forbidden()
        sessions.delete(session.token)
        redirect = RedirectResponse("/panel/login", status_code=303)
        redirect.delete_cookie(SESSION_COOKIE, path="/panel")
        return redirect

    def row(event: AdvisorEvent) -> str:
        return (
            f"<tr><td>{_time(event.created_at)}</td><td>{escape(KIND_LABEL[event.kind])}</td>"
            f"<td>{escape(_mask(phone_from_key(event.conversation_key)))}</td>"
            f"<td>{escape(event.status.value)}</td>"
            f"<td><a href='/panel/events/{event.id}'>Ver</a></td></tr>"
        )

    @router.get("/")
    async def index(request: Request) -> Response:
        session = session_of(request)
        if session is None or inbox is None:
            return unauthorized()
        pending = inbox.list_events(status=AttentionStatus.PENDIENTE)
        done = [e for e in inbox.list_events() if e.status is not AttentionStatus.PENDIENTE]
        done.reverse()
        page = _page_number(request.query_params.get("page"))
        start = (page - 1) * PAGE_SIZE
        head = "<tr><th>Fecha</th><th>Tipo</th><th>Cliente</th><th>Estado</th><th></th></tr>"
        empty = "<tr><td colspan=5>Sin pendientes en esta página.</td></tr>"
        shown = "".join(row(e) for e in pending[start : start + PAGE_SIZE]) or empty
        body = (
            f"<h1>Pendientes ({len(pending)})</h1><table>{head}{shown}"
            f"</table><h2>Atendidos recientes ({len(done)})</h2><table>{head}"
            f"{''.join(row(e) for e in done[start : start + PAGE_SIZE])}</table>"
            + _pager(page, more=max(len(pending), len(done)) > start + PAGE_SIZE)
        )
        return respond(layout(session, body))

    def detail_body(session: PanelSession, event: AdvisorEvent) -> str:
        phone = phone_from_key(event.conversation_key)
        parts = [
            f"<p><a href='/panel/'>← Bandeja</a></p><h1>{escape(KIND_LABEL[event.kind])}</h1>",
            f"<div class='card'><p>Estado: <strong>{escape(event.status.value)}</strong> · "
            f"Cliente WhatsApp: <strong>{escape(phone or 'sin WhatsApp')}</strong> · "
            f"Recibido: {_time(event.created_at)}</p>",
        ]
        if event.resolved_by:
            parts.append(
                f"<p class='muted'>Resuelto por {escape(event.resolved_by)} el "
                f"{_time(event.resolved_at)}"
                f"{' · motivo: ' + escape(event.reason) if event.reason else ''}"
                + (
                    ""
                    if event.client_notified is None
                    else " · cliente avisado"
                    if event.client_notified
                    else " · aviso al cliente falló"
                )
                + "</p>"
            )
        parts.append("</div>")
        quote = container.quotes.get(event.quote_id) if event.quote_id else None
        if quote is not None:
            state = container.agent.conversation_state(event.conversation_key or "")
            branch = next(
                (b.name for b in container.branches.list_branches() if b.id == state.branch_id),
                None,
            )
            validity = container.policies.load(event.tenant_id).vigencia_cotizacion_dias
            lines = "".join(
                f"<tr><td>{escape(line.description)}</td><td>{escape(str(line.quantity))} "
                f"{escape(line.unit)}</td><td>{_money(line.unit_price.amount)}</td>"
                f"<td>{_money(line.line_total.amount)}</td></tr>"
                for line in quote.lines
            )
            parts.append(
                "<div class='card'><h2>Cotización vigente</h2><table><tr><th>Producto</th>"
                f"<th>Cantidad</th><th>Precio</th><th>Subtotal</th></tr>{lines}</table>"
                f"<p><strong>Total: {_money(quote.total.amount)} {escape(quote.currency)}</strong> "
                f"· versión {quote.version} · estado {escape(quote.status.value)} · "
                f"<a href='/panel/quotes/{quote.id}/pdf'>Descargar PDF</a></p>"
                f"<p>Entrega: {escape(state.delivery or 'pendiente')} · Sede: "
                f"{escape(branch or 'pendiente')} · Pago: {escape(state.payment or 'pendiente')} "
                f"· Vigencia: {escape(f'{validity} días' if validity else 'pendiente')}</p>"
                + (f"<p>Dirección: {escape(state.address)}</p>" if state.address else "")
                + f"<p class='muted'>{escape(quote.notes)}</p></div>"
            )
        if event.status is AttentionStatus.PENDIENTE:
            token = f"<input type='hidden' name='csrf' value='{escape(session.csrf)}'>"
            actions = ""
            if event.kind == "client_confirmed":
                actions += (
                    f"<form method='post' action='/panel/events/{event.id}/approve'>{token}"
                    "<button class='ok'>Aprobar para facturación</button></form>"
                    f"<form method='post' action='/panel/events/{event.id}/reject'>{token}"
                    "<label>Motivo del rechazo<textarea name='reason' maxlength='300' required>"
                    "</textarea></label><button class='bad'>Rechazar</button></form>"
                )
            actions += (
                f"<form method='post' action='/panel/events/{event.id}/attend'>{token}"
                "<button>Marcar atendido</button></form>"
            )
            parts.append(f"<div class='card'>{actions}</div>")
        return "".join(parts)

    def parse_event_id(raw: str) -> UUID | None:
        try:
            return UUID(raw)
        except ValueError:
            return None

    @router.get("/events/{event_id}")
    async def detail(request: Request, event_id: str) -> Response:
        session = session_of(request)
        if session is None or inbox is None:
            return unauthorized()
        parsed = parse_event_id(event_id)
        event = inbox.get(parsed) if parsed else None
        if event is None:
            return respond(layout(session, "<h1>No encontrado</h1>"), status=404)
        return respond(layout(session, detail_body(session, event)))

    async def act(request: Request, event_id: str, action: str) -> Response:
        session = session_of(request)
        if session is None or inbox is None or review is None:
            return unauthorized()
        data = await form(request)
        if data is None or not csrf_ok(session, data):
            return forbidden()
        parsed = parse_event_id(event_id)
        if parsed is None:
            return respond(layout(session, "<h1>No encontrado</h1>"), status=404)
        try:
            if action == "approve":
                outcome = review.approve(parsed, advisor=session.username)
            elif action == "reject":
                outcome = review.reject(
                    parsed, advisor=session.username, reason=data.get("reason", "")
                )
            else:
                outcome = review.attend(parsed, advisor=session.username)
        except ReviewError as exc:
            return respond(
                layout(
                    session,
                    f"<h1>No se pudo completar</h1><p>{escape(str(exc))}</p>"
                    f"<p><a href='/panel/events/{escape(event_id)}'>Volver</a></p>",
                ),
                status=409,
            )
        if outcome.client_message is not None and container.outbound_queue is None:
            phone = phone_from_key(outcome.event.conversation_key)
            delivered = False
            if phone is not None and container.whatsapp_channel is not None:
                try:
                    await container.whatsapp_channel.send_text(
                        recipient_number=phone, text=outcome.client_message
                    )
                    delivered = True
                except ChannelDeliveryError:
                    delivered = False
            review.mark_client_notified(parsed, delivered=delivered)
        return RedirectResponse(f"/panel/events/{parsed}", status_code=303)

    @router.get("/quotes/{quote_id}/pdf")
    async def quote_pdf(request: Request, quote_id: str) -> Response:
        session = session_of(request)
        if session is None or inbox is None:
            return unauthorized()
        parsed = parse_event_id(quote_id)
        quote = container.quotes.get(parsed) if parsed else None
        event = next((e for e in inbox.list_events() if parsed and e.quote_id == parsed), None)
        if quote is None or event is None:
            return respond(layout(session, "<h1>No encontrado</h1>"), status=404)
        if quote.status is QuoteStatus.DRAFT:
            return respond(
                layout(session, "<h1>El borrador aún no fue confirmado por el cliente</h1>"),
                status=409,
            )
        renderer = load_pdf_renderer()
        if renderer is None:
            return respond(
                layout(session, "<h1>PDF no disponible</h1><p>Instala el grupo pdf.</p>"),
                status=503,
            )
        state = container.agent.conversation_state(event.conversation_key or "")
        branch = next(
            (b.name for b in container.branches.list_branches() if b.id == state.branch_id), None
        )
        document = build_quote_pdf_document(
            quote,
            state=state,
            policy=container.policies.load(quote.tenant_id),
            tenant_id=quote.tenant_id,
            branch_name=branch,
            issued_on=datetime.now(ZoneInfo(settings.default_timezone)).date(),
        )
        content = renderer.render(document)
        filename = f"cotizacion-{quote_number(quote)}-v{quote.version}.pdf"
        return Response(
            content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/events/{event_id}/approve")
    async def approve(request: Request, event_id: str) -> Response:
        return await act(request, event_id, "approve")

    @router.post("/events/{event_id}/reject")
    async def reject(request: Request, event_id: str) -> Response:
        return await act(request, event_id, "reject")

    @router.post("/events/{event_id}/attend")
    async def attend(request: Request, event_id: str) -> Response:
        return await act(request, event_id, "attend")

    return router
