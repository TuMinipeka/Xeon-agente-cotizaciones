"""Report safe structural and row-count checks for the commercial database."""

from __future__ import annotations

import json

import sqlalchemy as sa

from xeon.config import Settings


def inspect_database(connection: sa.Connection) -> dict[str, object]:
    database, server_version, vector_available, schema_exists = connection.execute(
        sa.text("""SELECT current_database(), current_setting('server_version'),
        EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector'),
        EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'commercial')""")
    ).one()
    report: dict[str, object] = {
        "database": database,
        "server_version": server_version,
        "vector_available": vector_available,
        "commercial_schema": schema_exists,
    }
    if not schema_exists:
        return report
    report["vector_installed_version"] = connection.execute(
        sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar_one_or_none()
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
        "product_embeddings",
        "data_quality_issues",
        "import_batches",
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
    expected_views = {
        "available_stock",
        "branch_stock",
        "catalog_products",
        "current_product_prices",
    }
    existing_views = {
        row[0]
        for row in connection.execute(
            sa.text("""SELECT table_name FROM information_schema.views
            WHERE table_schema = 'commercial'""")
        )
    }
    report["missing_views"] = sorted(expected_views - existing_views)
    if expected_views <= existing_views:
        report["view_counts"] = {
            view: connection.execute(
                sa.text(f"SELECT count(*) FROM commercial.{view}")
            ).scalar_one()
            for view in sorted(expected_views)
        }
    report["completed_batches"] = connection.execute(
        sa.text("SELECT count(*) FROM commercial.import_batches WHERE status = 'COMPLETED'")
    ).scalar_one()
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
