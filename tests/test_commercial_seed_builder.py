from __future__ import annotations

from scripts.build_commercial_seed import (
    _colors,
    _excel_date,
    _measurements,
    _positive_amount,
    _selling_unit,
    transform_record,
)


def _record() -> dict[str, str | None]:
    return {
        "CODIGO": "A-1",
        "TIPO": "V",
        "FECHA DE REGISTRO": "45292",
        "DESCRIPCION": "PINTURA BLANCO X GALON",
        "LINEA": "4 PINTURAS",
        "CATEGORIA": "6 ESMALTES",
        "SUB LINEA": "4 PINTURA",
        "COLOR": "20 ACME",
        "IMPUESTO": "1 TASA 19%",
        "PRECIO UNITARIO 1": "120000",
        "FECHA PU 1": "1",
        "PRECIO UNITARIO 2": "0",
        "FECHA PU 2": "1",
        "PRECIO UNITARIO 3": "120000",
        "FECHA PU 3": "45292",
        "PRECIO UNITARIO 4": "120000",
        "FECHA PU 4": "45292",
        "PRECIO UNITARIO 5": "120000",
        "FECHA PU 5": "45292",
        "PERIODO PRECIO 5 INIC": "45292",
        "PERIODO PRECIO 5 FIN": "45657",
    }


def test_transform_keeps_only_positive_sale_prices_and_classifications() -> None:
    product = transform_record(_record())
    assert product["sku"] == "A-1"
    assert product["brand"] == {"code": "20", "name": "ACME"}
    assert product["colors"] == [{"code": "BLANCO", "name": "Blanco"}]
    assert product["selling_unit"] == {"code": "GAL", "method": "DESCRIPTION_RULE"}
    assert [price["level"] for price in product["prices"]] == [1, 3, 4, 5]
    assert product["tax"]["rate"] == "19"


def test_unknown_dates_and_zero_prices_do_not_become_commercial_values() -> None:
    assert _excel_date("1") is None
    assert _positive_amount("0") is None
    assert _positive_amount("-50") is None


def test_measurements_and_units_are_inferred_only_by_explicit_rules() -> None:
    assert _selling_unit("ANGEO VERDE X MTS") == ("M", "DESCRIPTION_RULE")
    assert _selling_unit("MARTILLO 16 OZ") == ("UNIDAD", "DEFAULT")
    assert _selling_unit("REVOLVEDORA PARA 1/2 BULTO") == ("UNIDAD", "DEFAULT")
    assert _measurements("TUBO 2 PULGADAS X 6 MTS") == [
        {"ordinal": 1, "kind": "UNSPECIFIED", "value": "2", "unit": "PULG", "raw": "2 PULGADAS"},
        {"ordinal": 2, "kind": "UNSPECIFIED", "value": "6", "unit": "M", "raw": "6 MTS"},
    ]


def test_color_defaults_to_not_applicable() -> None:
    assert _colors("LAMINA LISA") == [{"code": "NO_APLICA", "name": "No aplica"}]
