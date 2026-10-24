from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    data_mode: Literal["synthetic"] = "synthetic"
    default_timezone: str = "America/Bogota"

    llm_provider: Literal["mock", "groq", "grok", "hermes"] = "grok"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_max_output_tokens: int = Field(default=2048, ge=1, le=32_000)
    llm_timeout_seconds: float = Field(default=120, gt=0, le=600)
    agent_max_steps: int = Field(default=6, ge=1, le=24)
    conversation_max_turns: int = Field(default=6, ge=1)
    conversation_max_conversations: int = Field(default=1000, ge=1)

    hermes_base_url: str = "http://127.0.0.1:8642/v1"
    hermes_model: str = "gpt-5.6-luna"
    hermes_api_key: SecretStr = SecretStr("xeon-hermes-local-bridge-2026")
    hermes_api_key_file: Path | None = None

    groq_api_key: SecretStr | None = None
    groq_api_key_file: Path | None = None
    grok_api_key: SecretStr | None = None
    grok_api_key_file: Path | None = Path("secrets/grok_api_key.txt")
    grok_base_url: str = "https://api.reto.pltk.mx/v1"
    grok_model: str = "grok-4.20-0309-non-reasoning"

    whatsapp_send_enabled: bool = False
    whatsapp_require_prefix: bool = False
    evolution_api_url: str = "http://evolution-api:8080"
    evolution_instance: str = "xeon-ferreteria"
    evolution_api_key: SecretStr | None = None
    evolution_api_key_file: Path | None = None

    log_level: str = "INFO"

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

    def resolve_hermes_api_key(self) -> SecretStr:
        if self.hermes_api_key_file is not None:
            try:
                value = self.hermes_api_key_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise SettingsError("No se pudo leer HERMES_API_KEY_FILE.") from exc
            if value:
                return SecretStr(value)

        if self.hermes_api_key.get_secret_value().strip():
            return self.hermes_api_key

        raise SettingsError("LLM_PROVIDER=hermes requiere HERMES_API_KEY o HERMES_API_KEY_FILE.")

    def require_evolution_api_key(self) -> SecretStr:
        return _require_api_key(
            self.evolution_api_key,
            self.evolution_api_key_file,
            file_error="No se pudo leer EVOLUTION_API_KEY_FILE.",
            missing_error=(
                "WHATSAPP_SEND_ENABLED=true requiere EVOLUTION_API_KEY o EVOLUTION_API_KEY_FILE."
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
