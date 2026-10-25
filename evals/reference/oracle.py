"""Independent reference oracle. This module reads only frozen JSON fixtures."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _fold(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


class FixtureMismatch(RuntimeError):
    """Frozen fixtures are missing or no longer match their recorded digest."""


class Oracle:
    def __init__(self, root: Path = FIXTURES) -> None:
        files = {
            name: (root / name).read_bytes()
            for name in ("catalog.json", "inventory.json", "policies.json")
        }
        digest = hashlib.sha256()
        for name, data in sorted(files.items()):
            digest.update(name.encode() + b"\0" + data)
        self.fingerprint = digest.hexdigest()
        if self.fingerprint != (root / "fixtures.sha256").read_text(encoding="ascii").strip():
            raise FixtureMismatch(
                "La huella de fixtures no coincide; reexporte y revise la semilla."
            )
        self.catalog: list[dict[str, Any]] = json.loads(files["catalog.json"])
        self.inventory: list[dict[str, Any]] = json.loads(files["inventory.json"])
        self.policies: dict[str, Any] = json.loads(files["policies.json"])

    def find_product(self, query: str) -> dict[str, Any] | None:
        needle = _fold(query).strip()
        if not needle:
            return None
        matches = [
            product
            for product in self.catalog
            if needle == _fold(str(product["sku"]))
            or needle == _fold(str(product["name"]))
            or any(needle == _fold(str(alias)) for alias in product["aliases"])
        ]
        return matches[0] if matches else None

    def unit_price(self, query: str) -> Decimal:
        product = self.find_product(query)
        if product is None:
            raise LookupError(f"Producto no encontrado en fixture: {query}")
        return Decimal(str(product["unit_price"]))

    def subtotal(self, query: str, quantity: str | Decimal) -> Decimal:
        amount = Decimal(str(quantity))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("La cantidad debe ser positiva y finita.")
        return (self.unit_price(query) * amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def stock(self, query: str, branch_id: str) -> Decimal:
        product = self.find_product(query)
        if product is None:
            raise LookupError(f"Producto no encontrado en fixture: {query}")
        return sum(
            (
                Decimal(str(row["quantity"]))
                for row in self.inventory
                if row["sku"] == product["sku"] and row["branch_id"] == branch_id
            ),
            Decimal("0"),
        )
