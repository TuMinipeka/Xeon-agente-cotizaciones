"""Conector SQL contra PostgreSQL y MySQL reales (compose.db-test.yaml, credenciales de prueba).

Se excluyen por defecto: `uv run --group db-test pytest -m integration tests/integration`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from xeon.adapters.sql.connection import SqlReader
from xeon.application.container import build_container
from xeon.config import Settings
from xeon.connectors.schema import ReadQuery, load_connector

pytestmark = pytest.mark.integration

EXAMPLE = Path("connectors/example-ferreteria.yaml")


@dataclass(frozen=True)
class Engine:
    name: str
    read_only_url: str
    admin_url: str


ENGINES = {
    "postgresql": Engine(
        "postgresql",
        "postgresql+psycopg://tienda_ro:solo-prueba-lectura@127.0.0.1:55432/tienda",
        "postgresql+psycopg://tienda_admin:solo-prueba-admin@127.0.0.1:55432/tienda",
    ),
    "mysql": Engine(
        "mysql",
        "mysql+pymysql://tienda_ro:solo-prueba-lectura@127.0.0.1:53450/tienda",
        "mysql+pymysql://root:solo-prueba-root@127.0.0.1:53450/tienda",
    ),
}


@pytest.fixture(params=sorted(ENGINES))
def engine(request: pytest.FixtureRequest) -> Engine:
    return ENGINES[request.param]


def _connector_root(tmp_path: Path, engine: Engine, *, utc_text: bool) -> Path:
    """MySQL no tiene DATETIME con zona: el YAML declara la zona con naive_datetime_timezone."""
    root = tmp_path / "connectors"
    root.mkdir(exist_ok=True)
    text_yaml = EXAMPLE.read_text(encoding="utf-8")
    if engine.name == "mysql" and utc_text:
        text_yaml += "naive_datetime_timezone: UTC\n"
    (root / "example-ferreteria.yaml").write_text(text_yaml, encoding="utf-8")
    return root


def _settings(tmp_path: Path, engine: Engine, *, utc_text: bool = True) -> Settings:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(exist_ok=True)
    url_file = secret_dir / "db_url.txt"
    url_file.write_text(engine.read_only_url, encoding="utf-8")
    return Settings(
        llm_provider="mock",
        data_source="sql",
        tenant_id="example-ferreteria",
        currency="COP",
        connector_root=_connector_root(tmp_path, engine, utc_text=utc_text),
        sql_url_file=url_file,
        _env_file=None,
    )


def _count(url: str, table: str) -> int:
    admin = create_engine(url)
    try:
        with admin.connect() as connection:
            return int(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
    finally:
        admin.dispose()


def test_quote_and_stock_use_prices_from_the_real_database(engine: Engine, tmp_path: Path) -> None:
    async def run() -> None:
        container = build_container(_settings(tmp_path, engine))
        try:
            quote = await container.agent.respond("2 bultos de cemento", conversation_key="db-1")
            stock = await container.agent.respond(
                "¿disponibles en sede Robles?", conversation_key="db-1"
            )
            summary = await container.agent.respond(
                "resumeme mi cotizacion", conversation_key="db-1"
            )
            assert "Cemento Ferreteria Robles" in quote.text
            assert "Ferreteria Robles Principal" in stock.text
            assert "TOTAL confirmado: $75.100" in summary.text
            assert [branch.id for branch in container.branches.list_branches()] == ["BOD-7"]
            snapshots = container.inventory.list_snapshots("FER-01")
            assert snapshots[0].quantity == 12
        finally:
            await container.aclose()

    asyncio.run(run())


def test_search_limit_and_binding_work_per_dialect(engine: Engine, tmp_path: Path) -> None:
    container = build_container(_settings(tmp_path, engine))
    try:
        assert [p.id.value for p in container.catalog.search_candidates("pala", limit=1)] == [
            "FER-02"
        ]
        assert container.catalog.search_candidates("' OR 1=1 --") == ()
        assert container.catalog.find_exact("FER-01' OR 1=1 --") is None
        product = container.catalog.find_exact("FER-02")
        assert product is not None
        assert product.list_price.amount == Decimal("43700")
    finally:
        asyncio.run(container.aclose())


def test_read_only_user_cannot_write_even_through_the_connector(engine: Engine) -> None:
    reader = SqlReader(engine.read_only_url, timeout_seconds=5)
    before = _count(engine.admin_url, "articulos")
    forged = ReadQuery.model_construct(
        sql="INSERT INTO articulos VALUES ('HACK', 'x', 'UND', 1, 'x')", columns={}
    )
    try:
        with pytest.raises(SQLAlchemyError):
            reader.rows(forged)
        with pytest.raises(SQLAlchemyError):
            reader.rows(
                ReadQuery.model_construct(
                    sql="UPDATE articulos SET precio_centavos = 0", columns={}
                )
            )
    finally:
        reader.close()
    assert _count(engine.admin_url, "articulos") == before


def test_session_is_read_only_even_for_a_writer_account(engine: Engine) -> None:
    reader = SqlReader(engine.admin_url, timeout_seconds=5)
    before = _count(engine.admin_url, "articulos")
    try:
        with pytest.raises(SQLAlchemyError, match=r"(?i)read.only"):
            reader.rows(
                ReadQuery.model_construct(
                    sql="INSERT INTO articulos VALUES ('HACK', 'x', 'UND', 1, 'x')", columns={}
                )
            )
        with pytest.raises(SQLAlchemyError, match=r"(?i)read.only"):
            reader.rows(ReadQuery.model_construct(sql="DELETE FROM existencias", columns={}))
    finally:
        reader.close()
    assert _count(engine.admin_url, "articulos") == before


def test_connector_yaml_with_dml_is_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    data["find_by_sku"]["sql"] = "DELETE FROM articulos WHERE codigo = :sku"
    path = tmp_path / "malicioso.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalida"):
        load_connector(path)


def test_naive_datetime_is_reported_as_unavailable_not_guessed(tmp_path: Path) -> None:
    """Hallazgo: un DATETIME sin zona (MySQL) hace que el stock quede pendiente de un asesor."""

    async def run() -> None:
        container = build_container(_settings(tmp_path, ENGINES["mysql"], utc_text=False))
        try:
            await container.agent.respond("2 bultos de cemento", conversation_key="db-2")
            stock = await container.agent.respond(
                "¿disponibles en sede Robles?", conversation_key="db-2"
            )
            assert "pendiente de confirmaci" in stock.text
            assert "Ferreteria Robles Principal" not in stock.text
        finally:
            await container.aclose()

    asyncio.run(run())
