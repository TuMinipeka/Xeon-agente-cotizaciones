"""Build the reviewable commercial seed from a Profit Plus XLSX export.

The raw workbook remains outside Git. Only catalog, taxes and sale prices are exported; identity,
credentials, internal costs, margins, supplier data and shelf locations are deliberately excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

_SHEET_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
_DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_SOURCE_SHEET = "Profit_1 Todos"
_EXPECTED_ROWS = 4_830

_COLOR_TERMS = {
    "AMARILLO": "Amarillo",
    "AZUL": "Azul",
    "BLANCO": "Blanco",
    "CAFE": "Café",
    "DORADO": "Dorado",
    "GRIS": "Gris",
    "MARRON": "Marrón",
    "MORADO": "Morado",
    "NARANJA": "Naranja",
    "NEGRO": "Negro",
    "PLATEADO": "Plateado",
    "ROJO": "Rojo",
    "TRANSPARENTE": "Transparente",
    "VERDE": "Verde",
}
_SELLING_UNIT_RULES = (
    (re.compile(r"(?:POR|X)\s+BULTOS?\b|^BULTOS?\b"), "BULTO"),
    (re.compile(r"\bCAJAS?\b"), "CAJA"),
    (re.compile(r"\bGALON(?:ES)?\b|\bGAL\b"), "GAL"),
    (re.compile(r"\bJUEGOS?\b"), "JUEGO"),
    (re.compile(r"\bKILOS?\b|\bKGS?\b"), "KG"),
    (re.compile(r"\bLITROS?\b|\bLTS?\b"), "L"),
    (re.compile(r"\bPAQUETES?\b|\bPAQ\b"), "PAQUETE"),
    (re.compile(r"\bPARES?\b"), "PAR"),
    (re.compile(r"\bROLLOS?\b"), "ROLLO"),
    (re.compile(r"(?:POR|X)\s+(?:METRO|MTS?)(?:\b|$)"), "M"),
)
_MEASUREMENT_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>MM|CM|MTS?|METROS?|PULG(?:ADAS?)?|KG|KILOS?|GR|GRAMOS?|"
    r"ML|LTS?|LITROS?|GAL(?:ON(?:ES)?)?)\b",
    re.IGNORECASE,
)
_MEASUREMENT_UNITS = {
    "MM": "MM",
    "CM": "CM",
    "M": "M",
    "MT": "M",
    "MTS": "M",
    "METRO": "M",
    "METROS": "M",
    "PULG": "PULG",
    "PULGADA": "PULG",
    "PULGADAS": "PULG",
    "KG": "KG",
    "KILO": "KG",
    "KILOS": "KG",
    "GR": "G",
    "GRAMO": "G",
    "GRAMOS": "G",
    "ML": "ML",
    "LT": "L",
    "LTS": "L",
    "LITRO": "L",
    "LITROS": "L",
    "GAL": "GAL",
    "GALON": "GAL",
    "GALONES": "GAL",
}
_TAX_RATES = {"1": "19", "9": "5", "6": "0", "5": "0"}


def _column_index(reference: str) -> int:
    letters = "".join(char for char in reference if char.isalpha())
    result = 0
    for char in letters.upper():
        result = result * 26 + ord(char) - 64
    return result - 1


def _cell_value(cell: ET.Element, shared: list[str]) -> str | None:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", _SHEET_NS)).strip()
    value_node = cell.find("m:v", _SHEET_NS)
    if value_node is None or value_node.text is None:
        return None
    raw = value_node.text.strip()
    if cell_type == "s":
        return shared[int(raw)].strip()
    return raw


def _read_source_rows(source: Path) -> list[dict[str, str | None]]:
    with zipfile.ZipFile(source) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(node.text or "" for node in item.findall(".//m:t", _SHEET_NS))
                for item in root.findall("m:si", _SHEET_NS)
            ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships.findall("r:Relationship", _REL_NS)
        }
        sheet = next(
            item
            for item in workbook.findall("m:sheets/m:sheet", _SHEET_NS)
            if item.attrib["name"] == _SOURCE_SHEET
        )
        target = targets[sheet.attrib[_DOC_REL]].lstrip("/")
        path = target if target.startswith("xl/") else f"xl/{target}"
        root = ET.fromstring(archive.read(path))
        rows: list[list[str | None]] = []
        for row_node in root.findall(".//m:sheetData/m:row", _SHEET_NS):
            values: dict[int, str | None] = {}
            for cell in row_node.findall("m:c", _SHEET_NS):
                values[_column_index(cell.attrib.get("r", "A1"))] = _cell_value(cell, shared)
            if values:
                rows.append([values.get(index) for index in range(max(values) + 1)])
    header_index = next(
        index
        for index, row in enumerate(rows)
        if any((value or "").strip().upper() == "CODIGO" for value in row)
    )
    headers = [(value or "").strip() for value in rows[header_index]]
    records = []
    for row in rows[header_index + 1 :]:
        padded = row + [None] * (len(headers) - len(row))
        if any(value not in (None, "") for value in padded):
            records.append(dict(zip(headers, padded, strict=True)))
    return records


def _code_name(value: str | None) -> tuple[str, str]:
    match = re.match(r"^\s*(\S+)\s+(.+?)\s*$", value or "")
    if match is None:
        raise ValueError(f"Valor de catálogo inválido: {value!r}")
    return match.group(1), re.sub(r"\s+", " ", match.group(2)).strip()


def _excel_date(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        serial = int(Decimal(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Fecha Excel inválida: {value!r}") from exc
    if serial <= 1:
        return None
    return (date(1899, 12, 30) + timedelta(days=serial)).isoformat()


def _positive_amount(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Precio inválido: {value!r}") from exc
    if amount <= 0:
        return None
    return format(amount.normalize(), "f")


def _colors(description: str) -> list[dict[str, str]]:
    normalized = description.upper().replace("Á", "A").replace("É", "E")
    found = [
        {"code": code, "name": name}
        for code, name in _COLOR_TERMS.items()
        if re.search(rf"\b{re.escape(code)}\b", normalized)
    ]
    return found or [{"code": "NO_APLICA", "name": "No aplica"}]


def _selling_unit(description: str) -> tuple[str, str]:
    normalized = description.upper()
    for pattern, unit in _SELLING_UNIT_RULES:
        if pattern.search(normalized):
            return unit, "DESCRIPTION_RULE"
    return "UNIDAD", "DEFAULT"


def _measurements(description: str) -> list[dict[str, str | int]]:
    result: list[dict[str, str | int]] = []
    for ordinal, match in enumerate(_MEASUREMENT_RE.finditer(description), start=1):
        unit = _MEASUREMENT_UNITS[match.group("unit").upper()]
        result.append(
            {
                "ordinal": ordinal,
                "kind": "UNSPECIFIED",
                "value": match.group("value").replace(",", "."),
                "unit": unit,
                "raw": match.group(0),
            }
        )
    return result


def transform_record(record: dict[str, str | None]) -> dict[str, Any]:
    line_code, line_name = _code_name(record["LINEA"])
    category_code, category_name = _code_name(record["CATEGORIA"])
    subline_code, subline_name = _code_name(record["SUB LINEA"])
    brand_code, brand_name = _code_name(record["COLOR"])
    tax_code, tax_name = _code_name(record["IMPUESTO"])
    description = (record["DESCRIPCION"] or "").strip()
    if not description:
        raise ValueError("Producto sin descripción")
    unit_code, unit_method = _selling_unit(description)
    colors = _colors(description)
    context_parts = [description, line_name, category_name, subline_name]
    if brand_name != "NO APLICA":
        context_parts.append(brand_name)
    context_parts.extend(color["name"] for color in colors if color["code"] != "NO_APLICA")
    result: dict[str, Any] = {
        "sku": (record["CODIGO"] or "").strip(),
        "type_code": (record["TIPO"] or "").strip(),
        "registered_on": _excel_date(record["FECHA DE REGISTRO"]),
        "name": description,
        "line": {"code": line_code, "name": line_name},
        "category": {"code": category_code, "name": category_name},
        "subline": {"code": subline_code, "name": subline_name},
        "brand": {"code": brand_code, "name": brand_name},
        "colors": colors,
        "selling_unit": {"code": unit_code, "method": unit_method},
        "measurements": _measurements(description),
        "tax": {"code": tax_code, "name": tax_name, "rate": _TAX_RATES[tax_code]},
        "prices": [],
        "description_context": " | ".join(dict.fromkeys(context_parts)),
    }
    for level in range(1, 6):
        amount = _positive_amount(record[f"PRECIO UNITARIO {level}"])
        if amount is None:
            continue
        valid_from = _excel_date(record[f"FECHA PU {level}"])
        valid_to = None
        if level == 5:
            valid_from = _excel_date(record["PERIODO PRECIO 5 INIC"]) or valid_from
            valid_to = _excel_date(record["PERIODO PRECIO 5 FIN"])
        result["prices"].append(
            {
                "level": level,
                "amount": amount,
                "valid_from": valid_from,
                "valid_to": valid_to,
            }
        )
    return result


def build_seed(source: Path, output_dir: Path) -> dict[str, Any]:
    records = _read_source_rows(source)
    if len(records) != _EXPECTED_ROWS:
        raise ValueError(f"Se esperaban {_EXPECTED_ROWS} productos y llegaron {len(records)}")
    products = [transform_record(record) for record in records]
    skus = [product["sku"] for product in products]
    if any(not sku for sku in skus) or len(set(skus)) != len(skus):
        raise ValueError("Los SKU deben existir y ser únicos")
    if any(product["type_code"] not in {"V", "S"} for product in products):
        raise ValueError("TIPO solo admite V o S en esta fuente")

    output_dir.mkdir(parents=True, exist_ok=True)
    products_path = output_dir / "products.jsonl"
    serialized = (
        json.dumps(product, ensure_ascii=False, sort_keys=True) + "\n" for product in products
    )
    products_path.write_text(
        "".join(serialized),
        encoding="utf-8",
    )
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest().upper()
    seed_hash = hashlib.sha256(products_path.read_bytes()).hexdigest().upper()
    manifest = {
        "organization": "Ferretería El Campín",
        "source_kind": "Profit Plus XLSX",
        "source_sha256": source_hash,
        "seed_sha256": seed_hash,
        "product_count": len(products),
        "source_sheet": _SOURCE_SHEET,
        "excluded": [
            "business_tax_identifier",
            "credentials",
            "internal_costs",
            "margins",
            "supplier_data",
            "internal_storage_locations",
            "raw_workbook",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("seeds/commercial"))
    args = parser.parse_args()
    manifest = build_seed(args.source, args.output)
    print(
        f"Seed comercial generado: {manifest['product_count']} productos, "
        f"huella {manifest['seed_sha256']}"
    )


if __name__ == "__main__":
    main()
