from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import URL

from tests.guided_steps import add_product
from xeon.application.container import build_container
from xeon.config import Settings, SettingsError
from xeon.connectors.schema import ReadQuery, load_connector


def _connector_root(tmp_path: Path, zone: str | None) -> Path:
    if zone is None:
        return Path("connectors")
    root = tmp_path / "connectors"
    root.mkdir(exist_ok=True)
    source = Path("connectors/example-ferreteria.yaml").read_text(encoding="utf-8")
    (root / "example-ferreteria.yaml").write_text(
        source + f"naive_datetime_timezone: {zone}\n", encoding="utf-8"
    )
    return root


def _store(tmp_path: Path, *, naive: bool = False, zone: str | None = None) -> Settings:
    db = tmp_path / "inventario.db"
    now = datetime.now(UTC)
    local = now.astimezone(ZoneInfo(zone or "UTC"))
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
            (
                "FER-01",
                "BOD-7",
                "12",
                *(
                    (
                        local.replace(tzinfo=None).isoformat(sep=" "),
                        (local + timedelta(hours=2)).replace(tzinfo=None).isoformat(sep=" "),
                    )
                    if naive
                    else (now.isoformat(), (now + timedelta(hours=2)).isoformat())
                ),
            ),
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
        connector_root=_connector_root(tmp_path, zone),
        sql_url_file=url_file,
        _env_file=None,
    )


def test_sql_connector_quotes_real_schema_and_resolves_branch(tmp_path: Path) -> None:
    async def run() -> None:
        container = build_container(_store(tmp_path))
        try:
            await add_product(container, "sql-1", "cemento", "FER-01", 2)
            await container.agent.respond_reply("more:view", conversation_key="sql-1")
            await container.agent.respond_reply("delivery:branch_inquiry", conversation_key="sql-1")
            payment = await container.agent.respond_reply("branch:BOD-7", conversation_key="sql-1")
            summary = await container.agent.respond_reply(
                "payment:pending", conversation_key="sql-1"
            )
            assert "Cemento Ferreteria Robles" in summary.text
            assert payment.step == "pago"
            assert container.agent._funnel.state("sql-1").branch_id == "BOD-7"
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


def _stock_text(settings: Settings) -> str:
    async def run() -> str:
        container = build_container(settings)
        try:
            await add_product(container, "sql-n", "cemento", "FER-01", 2)
            await container.agent.respond_reply("more:view", conversation_key="sql-n")
            branch_options = await container.agent.respond_reply(
                "delivery:branch_inquiry", conversation_key="sql-n"
            )
            assert branch_options.step == "sede"
            assert any(option.id == "branch:BOD-7" for option in branch_options.options)
            reply = await container.agent.respond_reply("branch:BOD-7", conversation_key="sql-n")
            assert reply.step == "pago"
            return reply.text
        finally:
            await container.aclose()

    return asyncio.run(run())


def test_naive_datetime_is_rejected_unless_a_zone_is_declared(tmp_path: Path) -> None:
    text = _stock_text(_store(tmp_path, naive=True))
    assert "pendiente de confirmaci" in text
    assert "Ferreteria Robles Principal" not in text


def test_declared_zone_makes_naive_datetime_usable(tmp_path: Path) -> None:
    text = _stock_text(_store(tmp_path, naive=True, zone="America/Bogota"))
    assert "Ferreteria Robles Principal" in text
    assert "stock disponible" in text


def test_naive_zone_converts_to_that_offset_and_rejects_unknown_zone() -> None:
    from datetime import datetime

    from xeon.adapters.inventory.sql import _instant

    naive = datetime(2026, 10, 26, 12, 0, 0)
    assert _instant(naive, "UTC") == "2026-10-26T12:00:00+00:00"
    assert _instant(naive, "America/Bogota") == "2026-10-26T12:00:00-05:00"
    assert _instant("2026-10-26 12:00:00", "UTC") == "2026-10-26T12:00:00+00:00"
    assert _instant("2026-10-26T12:00:00+00:00", "UTC") == "2026-10-26T12:00:00+00:00"
    assert _instant(naive, None) == str(naive)
    data = {"naive_datetime_timezone": "Marte/Olimpo"}
    base = load_connector(Path("connectors/example-ferreteria.yaml")).model_dump()
    with pytest.raises(ValidationError):
        type(load_connector(Path("connectors/example-ferreteria.yaml"))).model_validate(base | data)
