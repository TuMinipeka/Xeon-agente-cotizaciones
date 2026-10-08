from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Self

MONEY_QUANTUM = Decimal("0.01")
DEFAULT_CURRENCY = "COP"


class InvalidMoneyError(ValueError):
    """Raised when an amount cannot be represented as commercial money."""


class CurrencyMismatchError(ValueError):
    """Raised when two money values use different currencies."""


def parse_decimal(value: Decimal | int | str, *, error: type[Exception]) -> Decimal:
    if isinstance(value, bool | float):
        raise error("Los importes y cantidades no aceptan float ni bool.")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(value)
    except Exception as exc:
        raise error("Valor numerico invalido.") from exc
    if not amount.is_finite():
        raise error("El valor debe ser un numero finito.")
    return amount


def as_money_decimal(value: Decimal | int | str) -> Decimal:
    amount = parse_decimal(value, error=InvalidMoneyError)
    if amount < 0:
        raise InvalidMoneyError("El importe no puede ser negativo.")
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class Money:
    __slots__ = ("amount", "currency")

    def __init__(self, amount: Decimal | int | str, currency: str = DEFAULT_CURRENCY) -> None:
        if not currency.strip():
            raise InvalidMoneyError("La moneda es obligatoria.")
        self.amount = as_money_decimal(amount)
        self.currency = currency.strip().upper()

    @classmethod
    def zero(cls, currency: str = DEFAULT_CURRENCY) -> Self:
        return cls(Decimal("0.00"), currency)

    def plus(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise CurrencyMismatchError("No se pueden sumar monedas distintas.")
        return Money(self.amount + other.amount, self.currency)

    def times(self, quantity: Decimal) -> Money:
        if quantity <= 0:
            raise InvalidMoneyError("La cantidad debe ser mayor que cero.")
        return Money(self.amount * quantity, self.currency)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __hash__(self) -> int:
        return hash((self.amount, self.currency))

    def __repr__(self) -> str:
        return f"Money({self.amount!s}, {self.currency!r})"
