"""Notification boundary for human follow-up, without message contents."""

from typing import Literal, Protocol


class AdvisorNotifier(Protocol):
    def notify(
        self, *, tenant_id: str, event: Literal["advisor_requested", "client_confirmed"]
    ) -> None: ...
