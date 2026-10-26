from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import URL

from xeon.application.container import build_container
from xeon.config import Settings, SettingsError
from xeon.connectors.schema import ReadQuery, load_connector


def _store(tmp_path: Path) -> Settings:
    db = tmp_path / "inventario.db"
    now = datetime.now(UTC)
    with sqlite3.connect(db) as connection:
        connection.executescript("""
            CREATE TABLE articulos (codigo TEXT, titulo TEXT, unidad_venta TEXT,
                precio_centavos TEXT, alias_texto TEXT);
            CREATE TABLE sucursales (clave TEXT, rotulo TEXT, apodos TEXT);
            CREATE TABLE existencias (codigo_articulo TEXT, bodega TEXT,
                disponibles TEXT, actualizado TEXT, vigente_hasta TEXT);
        """)
        connection.execute(
            "INSERT INTO articulos VALUES (?, ?, ?, ?, ?)",
            ("FER-01", "Cemento Ferreteria Robles", "SAC", "3755000", "cemento"),
        )
        connection.execute(
            "INSERT INTO sucursales VALUES (?, ?, ?)",
            ("BOD-7", "Ferreteria Robles Principal", "Robles|principal"),
        )
        connection.execute(
            "INSERT INTO existencias VALUES (?, ?, ?, ?, ?)",
            ("FER-01", "BOD-7", "12", now.isoformat(), (now + timedelta(hours=2)).isoformat()),
        )
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    url_file = secret_dir / "db_url.txt"
    url_file.write_text(URL.create("sqlite", database=str(db)).render_as_string(), encoding="utf-8")
    return Settings(
        llm_provider="mock",
        data_source="sql",
        tenant_id="example-ferreteria",
        currency="COP",
        connector_root=Path("connectors"),
        sql_url_file=url_file,
        _env_file=None,
    )


def test_sql_connector_quotes_real_schema_and_resolves_branch(tmp_path: Path) -> None:
    async def run() -> None:
        container = build_container(_store(tmp_path))
        try:
            quote = await container.agent.respond("2 bultos de cemento", conversation_key="sql-1")
            stock = await container.agent.respond(
                "¿disponibles en sede Robles?", conversation_key="sql-1"
            )
            summary = await container.agent.respond(
                "resumeme mi cotizacion", conversation_key="sql-1"
            )
            assert "Cemento Ferreteria Robles" in quote.text
            assert "disponible" in stock.text
            assert "Ferreteria Robles Principal" in stock.text
            assert "TOTAL confirmado: $75.100" in summary.text
            cart = container.carts.get("sql-1")
            assert cart is not None
            assert cart.confirmed_lines()[0].unit_price.amount == Decimal("37550")
            assert "sintéticos" not in summary.text
            assert container.branches.list_branches()[0].id == "BOD-7"
        finally:
            await container.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO articulos VALUES (1)",
        "UPDATE articulos SET precio_centavos = 0",
        "DROP TABLE articulos",
        "SELECT * FROM articulos; DROP TABLE articulos",
        "SELECT * FROM articulos -- comentario",
    ],
)
def test_non_select_or_multiple_statements_rejected(sql: str) -> None:
    with pytest.raises(ValidationError):
        ReadQuery(sql=sql, columns={"sku": "codigo"})


def test_bound_search_input_cannot_change_sql(tmp_path: Path) -> None:
    container = build_container(_store(tmp_path))
    try:
        assert container.catalog.search_candidates("' OR 1=1 --") == ()
        assert container.catalog.find_exact("FER-01' OR 1=1 --") is None
        assert container.catalog.find_exact("FER-01") is not None
    finally:
        asyncio.run(container.aclose())


def test_sql_connection_requires_secret_file(tmp_path: Path) -> None:
    settings = Settings(data_source="sql", sql_url_file=tmp_path / "url.txt", _env_file=None)
    with pytest.raises(SettingsError):
        settings.require_sql_url()


def test_example_yaml_validates() -> None:
    assert load_connector(Path("connectors/example-ferreteria.yaml")).price_divisor == 100


@pytest.mark.parametrize("source", ["rest", "csv"])
def test_future_sources_fail_explicitly(source: str) -> None:
    with pytest.raises(SettingsError, match="aun no esta implementado"):
        build_container(Settings(data_source=source, llm_provider="mock", _env_file=None))
