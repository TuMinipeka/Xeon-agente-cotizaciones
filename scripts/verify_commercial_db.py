"""Report safe structural and row-count checks for the commercial database."""

from __future__ import annotations

import json

import sqlalchemy as sa

from xeon.config import Settings


def inspect_database(connection: sa.Connection) -> dict[str, object]:
    server_version, vector_available, schema_exists = connection.execute(
        sa.text("""SELECT current_setting('server_version'),
        EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector'),
        EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'commercial')""")
    ).one()
    report: dict[str, object] = {
        "server_version": server_version,
        "vector_available": vector_available,
        "commercial_schema": schema_exists,
    }
    if not schema_exists:
        return report
    revision = connection.execute(
        sa.text("SELECT version_num FROM alembic_version")
    ).scalar_one_or_none()
    report["revision"] = revision
    expected_relations = (
        "businesses",
        "branches",
        "warehouses",
        "products",
        "product_prices",
        "stock",
        "product_search_documents",
    )
    existing = {
        row[0]
        for row in connection.execute(
            sa.text("""SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'commercial'""")
        )
    }
    report["missing_relations"] = sorted(set(expected_relations) - existing)
    if set(expected_relations) <= existing:
        report["counts"] = {
            table: connection.execute(
                sa.text(f"SELECT count(*) FROM commercial.{table}")
            ).scalar_one()
            for table in expected_relations
        }
    return report


def main() -> None:
    settings = Settings(_env_file=None)
    engine = sa.create_engine(settings.require_commercial_url(), hide_parameters=True)
    try:
        with engine.connect() as connection:
            report = inspect_database(connection)
    finally:
        engine.dispose()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
