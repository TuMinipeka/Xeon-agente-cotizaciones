"""Conversation-local commercial cart; prices always come from Product."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from xeon.domain.product import Product
from xeon.domain.quote import QuoteLine, as_positive_quantity, build_quote_line


@dataclass(frozen=True, slots=True)
class CartLine:
    label: str
    quantity: Decimal
    product: Product | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("El articulo necesita una descripcion.")
        object.__setattr__(self, "quantity", as_positive_quantity(self.quantity))

    @property
    def key(self) -> str:
        return self.product.sku if self.product is not None else self.label.casefold()


@dataclass(frozen=True, slots=True)
class QuoteCart:
    conversation_key: str
    lines: tuple[CartLine, ...] = ()
    version: int = 0
    quote_version: int = 0
    last_request_id: str | None = None

    def __post_init__(self) -> None:
        if not self.conversation_key.strip() or self.version < 0 or self.quote_version < 0:
            raise ValueError("La identidad y version del carrito deben ser validas.")
        keys = [line.key for line in self.lines]
        if len(keys) != len(set(keys)):
            raise ValueError("El carrito no admite referencias duplicadas.")

    def _changed(self, lines: tuple[CartLine, ...]) -> QuoteCart:
        if lines == self.lines:
            return self
        before = self.confirmed_lines()
        after = tuple(
            build_quote_line(line.product, line.quantity)
            for line in lines
            if line.product is not None
        )
        return replace(
            self,
            lines=lines,
            version=self.version + 1,
            quote_version=self.quote_version + int(before != after),
        )

    def add_item(
        self, product: Product | None, quantity: Decimal | int | str, *, label: str = ""
    ) -> QuoteCart:
        amount = as_positive_quantity(quantity)
        candidate = CartLine(
            label=product.name if product is not None else label, quantity=amount, product=product
        )
        for index, line in enumerate(self.lines):
            if line.key == candidate.key:
                updated = replace(line, quantity=line.quantity + amount)
                return self._changed((*self.lines[:index], updated, *self.lines[index + 1 :]))
        return self._changed((*self.lines, candidate))

    def set_quantity(self, reference: str, quantity: Decimal | int | str) -> QuoteCart:
        amount = as_positive_quantity(quantity)
        index = self._line_index(reference)
        line = self.lines[index]
        updated = replace(line, quantity=amount)
        return self._changed((*self.lines[:index], updated, *self.lines[index + 1 :]))

    def remove_item(self, reference: str, quantity: Decimal | int | str | None = None) -> QuoteCart:
        index = self._line_index(reference)
        line = self.lines[index]
        if quantity is None or as_positive_quantity(quantity) >= line.quantity:
            return self._changed((*self.lines[:index], *self.lines[index + 1 :]))
        updated = replace(line, quantity=line.quantity - as_positive_quantity(quantity))
        return self._changed((*self.lines[:index], updated, *self.lines[index + 1 :]))

    def choose_variant(self, reference: str, product: Product) -> QuoteCart:
        index = self._line_index(reference)
        line = self.lines[index]
        if line.product is not None and line.product.sku == product.sku:
            return self
        selected = replace(line, label=product.name, product=product)
        remaining = (*self.lines[:index], *self.lines[index + 1 :])
        duplicate = next((item for item in remaining if item.key == selected.key), None)
        if duplicate is not None:
            merged = tuple(
                replace(item, quantity=item.quantity + selected.quantity)
                if item.key == selected.key
                else item
                for item in remaining
            )
            return self._changed(merged)
        return self._changed((*self.lines[:index], selected, *self.lines[index + 1 :]))

    def clear(self) -> QuoteCart:
        return self._changed(())

    def confirmed_lines(self) -> tuple[QuoteLine, ...]:
        return tuple(
            build_quote_line(line.product, line.quantity)
            for line in self.lines
            if line.product is not None
        )

    def _line_index(self, reference: str) -> int:
        needle = reference.casefold().strip()
        matches = [
            index
            for index, line in enumerate(self.lines)
            if line.key.casefold() == needle or needle in line.label.casefold()
        ]
        if len(matches) != 1:
            raise LookupError("La referencia del carrito no es unica o no existe.")
        return matches[0]
