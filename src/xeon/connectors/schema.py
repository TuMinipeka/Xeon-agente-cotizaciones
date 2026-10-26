"""Validated, data-only SQL connector definition. Never contains credentials."""

from __future__ import annotations

import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_BLOCKED = re.compile(
    r"\b(?:insert|update|delete|drop|alter|create|truncate|merge|exec|execute|call|grant|revoke|attach|detach|pragma|into)\b",
    re.I,
)


class ReadQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sql: str
    columns: dict[str, str]

    @field_validator("sql")
    @classmethod
    def select_only(cls, value: str) -> str:
        statement = value.strip()
        if (
            not re.match(r"(?is)^select\s", statement)
            or ";" in statement
            or "--" in statement
            or "/*" in statement
            or _BLOCKED.search(statement)
        ):
            raise ValueError("El conector admite un unico SELECT sin comentarios ni DML/DDL.")
        return statement

    @field_validator("columns")
    @classmethod
    def valid_columns(cls, value: dict[str, str]) -> dict[str, str]:
        if not value or any(
            not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", col)
            for key, col in value.items()
        ):
            raise ValueError("Los nombres de columnas deben ser identificadores simples.")
        return value


class ConnectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    find_by_sku: ReadQuery
    search_text: ReadQuery
    stock_by_sku: ReadQuery
    list_branches: ReadQuery
    price_divisor: int = Field(default=1, gt=0)
    unit_map: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=5, ge=1, le=60)
    catalog_version: str = "sql-live"
    # Zona IANA con la que se interpretan fechas sin tzinfo (p. ej. MySQL DATETIME).
    # Sin declararla, una fecha sin zona se rechaza.
    naive_datetime_timezone: str | None = None

    @field_validator("naive_datetime_timezone")
    @classmethod
    def known_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
                raise ValueError("naive_datetime_timezone no es una zona IANA conocida.") from exc
        return value

    @model_validator(mode="after")
    def required_binds(self) -> ConnectorConfig:
        for name in ("find_by_sku", "stock_by_sku"):
            if ":sku" not in getattr(self, name).sql:
                raise ValueError(f"{name} requiere parametro :sku")
        if ":query" not in self.search_text.sql:
            raise ValueError("search_text requiere parametro :query")
        if ":limit" not in self.search_text.sql:
            raise ValueError("search_text requiere parametro :limit")
        required = {
            "find_by_sku": {"sku", "name", "unit", "price"},
            "search_text": {"sku", "name", "unit", "price"},
            "stock_by_sku": {"branch_id", "quantity"},
            "list_branches": {"id", "name"},
        }
        for name, fields in required.items():
            if not fields.issubset(getattr(self, name).columns):
                raise ValueError(f"{name} no mapea todos los campos obligatorios")
        return self


def load_connector(path: Path) -> ConnectorConfig:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ConnectorConfig.model_validate(data)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ValueError("Configuracion del conector SQL invalida.") from exc
