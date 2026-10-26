"""SQLAlchemy Core connection with bound parameters and read-only transactions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine, create_engine, event, text

from xeon.connectors.schema import ReadQuery


class SqlReader:
    def __init__(self, url: str, *, timeout_seconds: int) -> None:
        self._engine: Engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        dialect = self._engine.dialect.name
        if dialect == "sqlite":

            @event.listens_for(self._engine, "connect")
            def sqlite_readonly(connection: Any, _record: Any) -> None:
                connection.execute("PRAGMA query_only = ON")
        elif dialect == "postgresql":

            @event.listens_for(self._engine, "begin")
            def postgres_readonly(connection: Any) -> None:
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")

        self._timeout_seconds = timeout_seconds

    def rows(self, statement: ReadQuery, **params: str | int) -> tuple[Mapping[str, Any], ...]:
        with self._engine.connect() as connection:
            if self._engine.dialect.name == "sqlite":
                connection.exec_driver_sql(f"PRAGMA busy_timeout = {self._timeout_seconds * 1000}")
            elif self._engine.dialect.name == "postgresql":
                connection.exec_driver_sql(
                    f"SET statement_timeout = {self._timeout_seconds * 1000}"
                )
            result = connection.execute(text(statement.sql), params)
            return tuple(dict(row) for row in result.mappings())

    def close(self) -> None:
        self._engine.dispose()


def mapped(row: Mapping[str, Any], query: ReadQuery, field: str, default: Any = None) -> Any:
    column = query.columns.get(field)
    return row.get(column, default) if column is not None else default
