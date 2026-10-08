from decimal import Decimal

import pytest

from xeon.domain.money import CurrencyMismatchError, InvalidMoneyError, Money
from xeon.domain.quote import InvalidQuantityError, as_positive_quantity


def test_money_quantizes_to_two_decimals() -> None:
    money = Money("28900.006", "COP")

    assert money.amount == Decimal("28900.01")
    assert money.currency == "COP"


def test_money_rejects_float() -> None:
    with pytest.raises(InvalidMoneyError, match="float"):
        Money(12.5)  # type: ignore[arg-type]


def test_money_rejects_negative_amount() -> None:
    with pytest.raises(InvalidMoneyError, match="negativo"):
        Money("-1.00")


def test_money_times_quantity_keeps_decimal_precision() -> None:
    unit_price = Money("1850.00", "COP")

    assert unit_price.times(Decimal("300")) == Money("555000.00", "COP")


def test_cannot_add_different_currencies() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money("10.00", "COP").plus(Money("10.00", "USD"))


@pytest.mark.parametrize("quantity", [0, -1, "0", Decimal("0")])
def test_quantity_must_be_positive(quantity: int | str | Decimal) -> None:
    with pytest.raises(InvalidQuantityError, match="mayor que cero"):
        as_positive_quantity(quantity)


def test_quantity_rejects_float() -> None:
    with pytest.raises(InvalidQuantityError, match="float"):
        as_positive_quantity(1.5)  # type: ignore[arg-type]
