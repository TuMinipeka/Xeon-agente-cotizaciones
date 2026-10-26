"""Initial human handoff adapter: metadata-only structured event."""

import logging
from typing import Literal

_LOG = logging.getLogger(__name__)


class LoggingAdvisorNotifier:
    def notify(
        self, *, tenant_id: str, event: Literal["advisor_requested", "client_confirmed"]
    ) -> None:
        _LOG.info("advisor_event tenant=%s event=%s", tenant_id, event)
