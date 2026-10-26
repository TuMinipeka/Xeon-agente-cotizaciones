from __future__ import annotations

from typing import Protocol


class PolicyRepository(Protocol):
    def get(self, tenant_id: str, topic: str) -> str | None: ...
