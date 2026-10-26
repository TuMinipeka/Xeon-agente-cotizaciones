"""Human review of client-confirmed drafts. Only the advisor panel calls this use case."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from xeon.application.ports.advisor import AdvisorEvent, AdvisorInbox, AttentionStatus
from xeon.application.ports.quotes import QuoteDraftRepository
from xeon.domain.quote import QuoteStatus, review_quote

APPROVED_TEXT = (
    "Un asesor revisó tu cotización y te contactará para los siguientes pasos. "
    "Este mensaje no es una factura ni una reserva de productos."
)
REJECTED_TEXT = (
    "Un asesor revisó tu cotización y por ahora no pudo aprobarla. "
    "Te contactará para revisar alternativas. Este mensaje no es una factura ni una reserva."
)
MAX_REASON = 300


class ReviewError(ValueError):
    """The requested human action is not valid for the event."""


@dataclass(frozen=True, slots=True)
class ReviewOutcome:
    event: AdvisorEvent
    client_message: str | None


class AdvisorReview:
    def __init__(
        self,
        inbox: AdvisorInbox,
        quotes: QuoteDraftRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        on_decision: Callable[[AdvisorEvent, str], None] | None = None,
    ) -> None:
        self._inbox = inbox
        self._quotes = quotes
        self._clock = clock or (lambda: datetime.now(UTC))
        self._on_decision = on_decision

    def _pending(self, event_id: UUID) -> AdvisorEvent:
        event = self._inbox.get(event_id)
        if event is None:
            raise ReviewError("Evento inexistente.")
        if event.status is not AttentionStatus.PENDIENTE:
            raise ReviewError("El evento ya fue atendido.")
        return event

    def approve(self, event_id: UUID, *, advisor: str) -> ReviewOutcome:
        return self._decide(event_id, advisor, QuoteStatus.APPROVED_FOR_BILLING, None)

    def reject(self, event_id: UUID, *, advisor: str, reason: str) -> ReviewOutcome:
        text = reason.strip()
        if not text or len(text) > MAX_REASON:
            raise ReviewError(f"El motivo es obligatorio (maximo {MAX_REASON} caracteres).")
        return self._decide(event_id, advisor, QuoteStatus.RECHAZADO_POR_ASESOR, text)

    def attend(self, event_id: UUID, *, advisor: str) -> ReviewOutcome:
        with self._inbox.review_transaction(event_id):
            event = self._pending(event_id)
            saved = self._inbox.save(
                replace(
                    event,
                    status=AttentionStatus.ATENDIDO,
                    resolved_by=advisor,
                    resolved_at=self._clock(),
                )
            )
        return ReviewOutcome(saved, None)

    def _decide(
        self, event_id: UUID, advisor: str, target: QuoteStatus, reason: str | None
    ) -> ReviewOutcome:
        with self._inbox.review_transaction(event_id):
            event = self._pending(event_id)
            if event.kind != "client_confirmed" or event.quote_id is None:
                raise ReviewError("Solo un borrador confirmado por el cliente puede revisarse.")
            quote = self._quotes.get(event.quote_id)
            if quote is None:
                raise ReviewError("El borrador ya no existe.")
            try:
                reviewed = review_quote(quote, target)
            except ValueError as exc:
                raise ReviewError(str(exc)) from exc
            self._quotes.save(reviewed)
            approved = target is QuoteStatus.APPROVED_FOR_BILLING
            saved = self._inbox.save(
                replace(
                    event,
                    status=AttentionStatus.APROBADO if approved else AttentionStatus.RECHAZADO,
                    resolved_by=advisor,
                    resolved_at=self._clock(),
                    reason=reason,
                )
            )
            if self._on_decision is not None:
                self._on_decision(saved, APPROVED_TEXT if approved else REJECTED_TEXT)
        return ReviewOutcome(saved, APPROVED_TEXT if approved else REJECTED_TEXT)

    def mark_client_notified(self, event_id: UUID, *, delivered: bool) -> AdvisorEvent:
        event = self._inbox.get(event_id)
        if event is None:
            raise ReviewError("Evento inexistente.")
        return self._inbox.save(replace(event, client_notified=delivered))
