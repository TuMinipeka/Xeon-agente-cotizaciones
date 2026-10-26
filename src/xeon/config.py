from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(RuntimeError):
    """Raised when a selected runtime profile is incomplete."""


def _require_api_key(
    value: SecretStr | None,
    key_file: Path | None,
    *,
    file_error: str,
    missing_error: str,
) -> SecretStr:
    if value is not None and value.get_secret_value().strip():
        return value

    if key_file is not None:
        try:
            file_value = key_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SettingsError(file_error) from exc
        if file_value:
            return SecretStr(file_value)

    raise SettingsError(missing_error)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    data_source: Literal["synthetic", "sql", "rest", "csv"] = "synthetic"
    tenant_id: str = "whatsapp"
    currency: str = "COP"
    connector_root: Path = Path("connectors")
    sql_url_file: Path = Path("secrets/store_database_url.txt")
    state_store: Literal["memory", "postgres"] = "memory"
    xeon_state_url_file: Path = Path("secrets/xeon_state_url.txt")
    default_timezone: str = "America/Bogota"

    llm_provider: Literal["mock", "groq", "grok"] = "grok"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_max_output_tokens: int = Field(default=2048, ge=1, le=32_000)
    llm_timeout_seconds: float = Field(default=120, gt=0, le=600)
    agent_max_steps: int = Field(default=6, ge=1, le=24)
    conversation_max_turns: int = Field(default=6, ge=1)
    conversation_max_conversations: int = Field(default=1000, ge=1)

    groq_api_key: SecretStr | None = None
    groq_api_key_file: Path | None = None
    grok_api_key: SecretStr | None = None
    grok_api_key_file: Path | None = Path("secrets/grok_api_key.txt")
    grok_base_url: str = "https://api.reto.pltk.mx/v1"
    grok_model: str = "grok-4.6"

    # Observabilidad: JSONL opcional y tarifa por millon de tokens. La unidad de la pasarela del
    # reto no esta documentada; las tarifas son un supuesto configurable, no un precio oficial.
    metrics_path: Path | None = None
    llm_price_input_per_mtok: Decimal | None = None
    llm_price_output_per_mtok: Decimal | None = None
    llm_price_unit: str = "unidad-no-documentada"

    whatsapp_send_enabled: bool = False
    kapso_api_base_url: str = "https://api.kapso.ai"
    kapso_api_key: SecretStr | None = None
    kapso_api_key_file: Path | None = None
    kapso_phone_number_id: str = ""
    kapso_webhook_secret: SecretStr | None = None
    kapso_webhook_secret_file: Path | None = Path("secrets/kapso_webhook_secret.txt")
    meta_graph_version: str = "v24.0"

    log_level: str = "INFO"

    @field_validator("currency")
    @classmethod
    def canonical_currency(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("CURRENCY debe ser un codigo monetario de tres letras.")
        return code

    def require_sql_url(self) -> str:
        if "secrets" not in self.sql_url_file.parts:
            raise SettingsError("SQL_URL_FILE debe apuntar a un archivo dentro de secrets/.")
        try:
            value = self.sql_url_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SettingsError("No se pudo leer SQL_URL_FILE.") from exc
        if not value:
            raise SettingsError("SQL_URL_FILE esta vacio.")
        return value

    def require_state_url(self) -> str:
        if "secrets" not in self.xeon_state_url_file.resolve().parts:
            raise SettingsError("XEON_STATE_URL_FILE debe estar dentro de secrets/.")
        try:
            value = self.xeon_state_url_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SettingsError("No se pudo leer XEON_STATE_URL_FILE.") from exc
        if not value:
            raise SettingsError("XEON_STATE_URL_FILE esta vacio.")
        if not value.startswith("postgresql+psycopg://"):
            raise SettingsError("STATE_STORE=postgres requiere una URL PostgreSQL psycopg.")
        return value

    def require_groq_api_key(self) -> SecretStr:
        return _require_api_key(
            self.groq_api_key,
            self.groq_api_key_file,
            file_error="No se pudo leer GROQ_API_KEY_FILE.",
            missing_error=(
                "LLM_PROVIDER=groq requiere GROQ_API_KEY o GROQ_API_KEY_FILE; "
                "no se usara una clave implicita."
            ),
        )

    def require_grok_api_key(self) -> SecretStr:
        return _require_api_key(
            self.grok_api_key,
            self.grok_api_key_file,
            file_error="No se pudo leer GROK_API_KEY_FILE.",
            missing_error=(
                "LLM_PROVIDER=grok requiere GROK_API_KEY o GROK_API_KEY_FILE; "
                "no se usara una clave implicita."
            ),
        )

    def require_kapso_api_key(self) -> SecretStr:
        return _require_api_key(
            self.kapso_api_key,
            self.kapso_api_key_file,
            file_error="No se pudo leer KAPSO_API_KEY_FILE.",
            missing_error="WHATSAPP_SEND_ENABLED=true requiere KAPSO_API_KEY o KAPSO_API_KEY_FILE.",
        )

    def require_kapso_webhook_secret(self) -> SecretStr:
        return _require_api_key(
            self.kapso_webhook_secret,
            self.kapso_webhook_secret_file,
            file_error="No se pudo leer KAPSO_WEBHOOK_SECRET_FILE.",
            missing_error=(
                "El webhook Kapso requiere KAPSO_WEBHOOK_SECRET o KAPSO_WEBHOOK_SECRET_FILE."
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
