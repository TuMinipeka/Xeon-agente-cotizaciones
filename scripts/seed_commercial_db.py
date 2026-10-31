"""Load the versioned commercial catalog into the isolated PostgreSQL database."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from xeon.config import Settings

EXPECTED_REVISION = "0005_vector_search_foundation"
BUSINESS_CODE = "FERRETERIA_EL_CAMPIN"
OBSERVED_AT = datetime(2026, 10, 31, 12, tzinfo=UTC)
VALID_UNTIL = datetime(2027, 10, 31, 12, tzinfo=UTC)

UNITS = {
    "UNIDAD": ("Unidad", "COUNT", False),
    "JUEGO": ("Juego", "COUNT", False),
    "PAR": ("Par", "COUNT", False),
    "M": ("Metro", "LENGTH", True),
    "CM": ("Centímetro", "LENGTH", True),
    "MM": ("Milímetro", "LENGTH", True),
    "PULG": ("Pulgada", "LENGTH", True),
    "L": ("Litro", "VOLUME", True),
    "ML": ("Mililitro", "VOLUME", True),
    "GAL": ("Galón", "VOLUME", True),
    "KG": ("Kilogramo", "MASS", True),
    "G": ("Gramo", "MASS", True),
    "BULTO": ("Bulto", "PACKAGE", False),
    "CAJA": ("Caja", "PACKAGE", False),
    "PAQUETE": ("Paquete", "PACKAGE", False),
    "ROLLO": ("Rollo", "PACKAGE", False),
}


def load_seed(seed_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads((seed_dir / "manifest.json").read_text(encoding="utf-8"))
    raw = (seed_dir / "products.jsonl").read_text(encoding="utf-8").replace("\r\n", "\n")
    fingerprint = hashlib.sha256(raw.encode()).hexdigest().upper()
    if fingerprint != manifest["seed_sha256"]:
        raise ValueError("La huella de products.jsonl no coincide con el manifiesto.")
    products = [json.loads(line) for line in raw.splitlines() if line]
    if len(products) != manifest["product_count"]:
        raise ValueError("La cantidad de productos no coincide con el manifiesto.")
    if len({product["sku"] for product in products}) != len(products):
        raise ValueError("El seed contiene SKU duplicados.")
    return manifest, products


def ensure_seed_allowed(settings: Settings) -> None:
    if settings.app_env == "production":
        raise RuntimeError("El stock de esta semilla de prueba no puede cargarse en producción.")


def _scalar(connection: sa.Connection, sql: str, values: dict[str, Any]) -> Any:
    return connection.execute(sa.text(sql), values).scalar_one()


def _dimension(
    connection: sa.Connection,
    table: str,
    business_id: int,
    value: dict[str, str],
) -> int:
    return int(
        _scalar(
            connection,
            f"""INSERT INTO commercial.{table} (business_id, source_code, name)
            VALUES (:business_id, :source_code, :name)
            ON CONFLICT (business_id, source_code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id""",
            {"business_id": business_id, "source_code": value["code"], "name": value["name"]},
        )
    )


def _insert_links(
    connection: sa.Connection,
    table: str,
    target_column: str,
    product_id: int,
    target_ids: Iterable[int],
) -> None:
    connection.execute(
        sa.text(
            f"INSERT INTO commercial.{table} (product_id, {target_column}) "
            f"VALUES (:product_id, :target_id) ON CONFLICT DO NOTHING"
        ),
        [{"product_id": product_id, "target_id": target_id} for target_id in target_ids],
    )


def seed_database(
    connection: sa.Connection, manifest: dict[str, Any], products: list[dict[str, Any]]
) -> None:
    revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    if revision != EXPECTED_REVISION:
        raise RuntimeError(f"La base comercial debe estar migrada a {EXPECTED_REVISION}.")
    connection.execute(sa.text("SELECT pg_advisory_xact_lock(hashtext('xeon-commercial-seed'))"))

    connection.execute(
        sa.text("DELETE FROM commercial.businesses WHERE code = :code"), {"code": BUSINESS_CODE}
    )
    connection.execute(
        sa.text(
            "DELETE FROM commercial.import_batches WHERE source_id IN "
            "(SELECT id FROM commercial.data_sources WHERE code = 'FERRETERIA_EL_CAMPIN_XLSX')"
        )
    )
    connection.execute(
        sa.text("DELETE FROM commercial.data_sources WHERE code = 'FERRETERIA_EL_CAMPIN_XLSX'")
    )
    source_id = int(
        _scalar(
            connection,
            """INSERT INTO commercial.data_sources
            (code, name, source_kind, source_sha256)
            VALUES ('FERRETERIA_EL_CAMPIN_XLSX', :name, 'XLSX', :hash) RETURNING id""",
            {"name": manifest["organization"], "hash": manifest["source_sha256"]},
        )
    )
    batch_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"xeon:{manifest['seed_sha256']}"))
    connection.execute(
        sa.text("""INSERT INTO commercial.import_batches
        (id, source_id, status, source_rows) VALUES (:id, :source_id, 'RUNNING', :rows)"""),
        {"id": batch_id, "source_id": source_id, "rows": len(products)},
    )
    business_id = int(
        _scalar(
            connection,
            """INSERT INTO commercial.businesses (code, legal_name, display_name)
            VALUES (:code, :name, :name) RETURNING id""",
            {"code": BUSINESS_CODE, "name": manifest["organization"]},
        )
    )
    branch_id = int(
        _scalar(
            connection,
            """INSERT INTO commercial.branches (business_id, code, name, city)
            VALUES (:business_id, 'BUCARAMANGA', 'Bucaramanga', 'Bucaramanga') RETURNING id""",
            {"business_id": business_id},
        )
    )
    warehouses = {
        code: int(
            _scalar(
                connection,
                """INSERT INTO commercial.warehouses (branch_id, code, name)
                VALUES (:branch_id, :code, :name) RETURNING id""",
                {"branch_id": branch_id, "code": code, "name": name},
            )
        )
        for code, name in (("BODEGA_1", "Bodega 1"), ("BODEGA_2", "Bodega 2"))
    }
    connection.execute(
        sa.text("INSERT INTO commercial.product_types VALUES (:code, :name, :stock)"),
        [
            {"code": "V", "name": "Venta", "stock": True},
            {"code": "S", "name": "Servicio", "stock": False},
        ],
    )
    connection.execute(
        sa.text("""INSERT INTO commercial.units_of_measure
        (code, name, dimension, allows_fraction) VALUES (:code, :name, :dimension, :fraction)"""),
        [
            {"code": code, "name": values[0], "dimension": values[1], "fraction": values[2]}
            for code, values in UNITS.items()
        ],
    )
    connection.execute(
        sa.text("INSERT INTO commercial.currencies VALUES ('COP', 'Peso colombiano', 0)")
    )
    price_lists = {
        level: int(
            _scalar(
                connection,
                """INSERT INTO commercial.price_lists
                (business_id, code, name, priority, is_default, includes_tax)
                VALUES (:business_id, :code, :name, :priority, :default, true) RETURNING id""",
                {
                    "business_id": business_id,
                    "code": f"PRICE_{level}",
                    "name": f"Precio {level}",
                    "priority": level,
                    "default": level == 1,
                },
            )
        )
        for level in range(1, 6)
    }
    connection.execute(
        sa.text("INSERT INTO commercial.stock_quantity_types VALUES (:code, :name, :effect)"),
        [
            {"code": "ON_HAND", "name": "Existencia", "effect": 1},
            {"code": "COMMITTED", "name": "Comprometido", "effect": -1},
            {"code": "INCOMING", "name": "En tránsito", "effect": 0},
            {"code": "TO_DISPATCH", "name": "Por despachar", "effect": -1},
        ],
    )

    tax_classes: dict[str, tuple[int, str]] = {}
    for product in products:
        tax = product["tax"]
        if tax["code"] not in tax_classes:
            tax_id = int(
                _scalar(
                    connection,
                    """INSERT INTO commercial.tax_classes
                    (business_id, source_code, name, applies_to_sales, applies_to_purchases)
                    VALUES (:business_id, :code, :name, true, false) RETURNING id""",
                    {"business_id": business_id, "code": tax["code"], "name": tax["name"]},
                )
            )
            connection.execute(
                sa.text("""INSERT INTO commercial.tax_rates
                (tax_class_id, rate, valid_from) VALUES (:id, :rate, '2000-01-01')"""),
                {"id": tax_id, "rate": tax["rate"]},
            )
            tax_classes[tax["code"]] = (tax_id, tax["rate"])

    stock_rows: list[dict[str, Any]] = []
    for product in products:
        line_id = _dimension(connection, "lines", business_id, product["line"])
        category_id = _dimension(connection, "categories", business_id, product["category"])
        subline_id = _dimension(connection, "sublines", business_id, product["subline"])
        brand_id = _dimension(connection, "brands", business_id, product["brand"])
        color_ids = [
            _dimension(connection, "colors", business_id, color) for color in product["colors"]
        ]
        connection.execute(
            sa.text(
                "INSERT INTO commercial.line_categories VALUES "
                "(:line, :category) ON CONFLICT DO NOTHING"
            ),
            {"line": line_id, "category": category_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO commercial.category_sublines VALUES "
                "(:category, :subline) ON CONFLICT DO NOTHING"
            ),
            {"category": category_id, "subline": subline_id},
        )
        product_id = int(
            _scalar(
                connection,
                """INSERT INTO commercial.products
                (business_id, product_type_code, import_batch_id, sku, name, registered_on,
                 specs, description_context)
                VALUES (:business_id, :type, :batch, :sku, :name, :registered,
                        CAST(:specs AS jsonb), :context) RETURNING id""",
                {
                    "business_id": business_id,
                    "type": product["type_code"],
                    "batch": batch_id,
                    "sku": product["sku"],
                    "name": product["name"],
                    "registered": product["registered_on"],
                    "specs": json.dumps({"measurements": product["measurements"]}),
                    "context": product["description_context"],
                },
            )
        )
        _insert_links(connection, "product_brands", "brand_id", product_id, [brand_id])
        _insert_links(connection, "product_colors", "color_id", product_id, color_ids)
        _insert_links(connection, "product_lines", "line_id", product_id, [line_id])
        _insert_links(connection, "product_categories", "category_id", product_id, [category_id])
        _insert_links(connection, "product_sublines", "subline_id", product_id, [subline_id])
        unit = product["selling_unit"]
        connection.execute(
            sa.text("""INSERT INTO commercial.product_units
            (product_id, unit_code, is_primary, conversion_to_primary, assignment_method)
            VALUES (:product, :unit, true, 1, :method)"""),
            {"product": product_id, "unit": unit["code"], "method": unit["method"]},
        )
        if product["measurements"]:
            connection.execute(
                sa.text("""INSERT INTO commercial.product_measurements
                (product_id, ordinal, measurement_kind, value, unit_code, raw_text)
                VALUES (:product, :ordinal, :kind, :value, :unit, :raw)"""),
                [
                    {
                        "product": product_id,
                        "ordinal": measurement["ordinal"],
                        "kind": measurement["kind"],
                        "value": measurement["value"],
                        "unit": measurement["unit"],
                        "raw": measurement["raw"],
                    }
                    for measurement in product["measurements"]
                ],
            )
        tax_id = tax_classes[product["tax"]["code"]][0]
        connection.execute(
            sa.text("""INSERT INTO commercial.product_tax_assignments
            (product_id, tax_class_id, valid_from) VALUES (:product, :tax, '2000-01-01')"""),
            {"product": product_id, "tax": tax_id},
        )
        if product["prices"]:
            connection.execute(
                sa.text("""INSERT INTO commercial.product_prices
                (product_id, price_list_id, currency_code, amount, valid_from, valid_to,
                 observed_at, import_batch_id)
                VALUES (:product, :list, 'COP', :amount, :valid_from, :valid_to,
                        :observed, :batch)"""),
                [
                    {
                        "product": product_id,
                        "list": price_lists[price["level"]],
                        "amount": price["amount"],
                        "valid_from": price["valid_from"] or date(2000, 1, 1),
                        "valid_to": price["valid_to"],
                        "observed": OBSERVED_AT,
                        "batch": batch_id,
                    }
                    for price in product["prices"]
                ],
            )
        else:
            connection.execute(
                sa.text("""INSERT INTO commercial.data_quality_issues
                (batch_id, sku, issue_code, severity, details)
                VALUES (:batch, :sku, 'MISSING_PRICE', 'ERROR', '{}'::jsonb)"""),
                {"batch": batch_id, "sku": product["sku"]},
            )
        content_hash = hashlib.sha256(product["description_context"].encode()).hexdigest().upper()
        connection.execute(
            sa.text("""INSERT INTO commercial.product_search_documents
            (product_id, content, content_hash) VALUES (:product, :content, :hash)"""),
            {
                "product": product_id,
                "content": product["description_context"],
                "hash": content_hash,
            },
        )
        if product["type_code"] == "V":
            for warehouse_code, warehouse_id in warehouses.items():
                on_hand = 100 if warehouse_code == "BODEGA_1" else 50
                for quantity_type, quantity in (
                    ("ON_HAND", on_hand),
                    ("COMMITTED", 0),
                    ("INCOMING", 0),
                    ("TO_DISPATCH", 0),
                ):
                    stock_rows.append(
                        {
                            "product": product_id,
                            "warehouse": warehouse_id,
                            "unit": unit["code"],
                            "type": quantity_type,
                            "quantity": quantity,
                            "observed": OBSERVED_AT,
                            "valid": VALID_UNTIL,
                            "source": source_id,
                            "batch": batch_id,
                        }
                    )

    connection.execute(
        sa.text("""INSERT INTO commercial.stock
        (product_id, warehouse_id, unit_code, quantity_type_code, quantity, observed_at,
         valid_until, source_id, import_batch_id)
        VALUES (:product, :warehouse, :unit, :type, :quantity, :observed, :valid,
                :source, :batch)"""),
        stock_rows,
    )
    connection.execute(
        sa.text("""UPDATE commercial.import_batches
        SET status = 'COMPLETED', accepted_rows = :rows, completed_at = now() WHERE id = :id"""),
        {"rows": len(products), "id": batch_id},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", type=Path, default=Path("seeds/commercial"))
    args = parser.parse_args()
    settings = Settings(_env_file=None)
    ensure_seed_allowed(settings)
    manifest, products = load_seed(args.seed_dir)
    engine = sa.create_engine(settings.require_commercial_url(), hide_parameters=True)
    try:
        with engine.begin() as connection:
            seed_database(connection, manifest, products)
    finally:
        engine.dispose()
    print(f"Base comercial cargada: {len(products)} productos.")


if __name__ == "__main__":
    main()
