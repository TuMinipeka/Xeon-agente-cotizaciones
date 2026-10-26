"""Quote PDF rendering port. The document is plain data: formatting happens before the adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PdfLine:
    description: str
    quantity: str
    unit_price: str
    subtotal: str


@dataclass(frozen=True, slots=True)
class QuotePdfDocument:
    store_name: str
    store_details: tuple[str, ...]
    number: str
    version: int
    issued_on: str
    status_label: str
    lines: tuple[PdfLine, ...]
    total: str
    currency: str
    delivery: str
    branch: str
    payment: str
    validity: str
    tax_note: str
    legend: str


class QuotePdfRenderer(Protocol):
    def render(self, document: QuotePdfDocument) -> bytes: ...
