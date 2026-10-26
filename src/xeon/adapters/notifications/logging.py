"""Initial human handoff adapter: metadata-only structured event."""

import logging
from uuid import UUID

from xeon.application.ports.advisor import AdvisorEventKind

_LOG = logging.getLogger(__name__)


class LoggingAdvisorNotifier:
    def notify(
        self,
        *,
        tenant_id: str,
        event: AdvisorEventKind,
        conversation_key: str | None = None,
        quote_id: UUID | None = None,
    ) -> None:
        # Never log the conversation key: for WhatsApp it embeds the customer's phone number.
        _LOG.info("advisor_event tenant=%s event=%s", tenant_id, event)
