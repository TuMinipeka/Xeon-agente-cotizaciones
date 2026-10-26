from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from xeon.application.ports.llm import ChatMessage


@dataclass(frozen=True, slots=True)
class PendingCandidates:
    skus: tuple[str, ...]
    names: tuple[str, ...]
    quantity: Decimal | None
    branch: str
    attributes: tuple[dict[str, str], ...] = ()
    question: str = ""


@dataclass(frozen=True, slots=True)
class ProjectContext:
    length_m: Decimal | None = None
    width_m: Decimal | None = None
    purpose: str | None = None

    @property
    def area_m2(self) -> Decimal | None:
        if self.length_m is None or self.width_m is None:
            return None
        return self.length_m * self.width_m


@dataclass(frozen=True, slots=True)
class ProposedLine:
    sku: str
    quantity: Decimal


class ConversationMemory(Protocol):
    def history(self, key: str) -> tuple[ChatMessage, ...]: ...

    def last_sku(self, key: str) -> str | None: ...

    def pending_candidates(self, key: str) -> PendingCandidates | None: ...

    def set_pending_candidates(self, key: str, pending: PendingCandidates | None) -> None: ...

    def project_data(self, key: str) -> ProjectContext: ...

    def remember_project_data(self, key: str, data: ProjectContext) -> None: ...

    def proposal_lines(self, key: str) -> tuple[ProposedLine, ...]: ...

    def remember_proposal(self, key: str, line: ProposedLine) -> None: ...

    def clear_proposal(self, key: str) -> None: ...

    def record(self, key: str, user: str, assistant: str, sku: str | None) -> None: ...
