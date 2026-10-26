from __future__ import annotations

from typing import Protocol

from xeon.application.policy_schema import StorePolicy


class PolicyRepository(Protocol):
    def get(self, tenant_id: str, topic: str) -> str | None: ...

    def load(self, tenant_id: str) -> StorePolicy: ...
