from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(RuntimeError):
    """Raised when a selected runtime profile is incomplete."""


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

    llm_provider: Literal["mock", "groq", "hermes"] = "mock"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_max_output_tokens: int = Field(default=2048, ge=1, le=32_000)
    llm_timeout_seconds: float = Field(default=120, gt=0, le=600)
    agent_max_steps: int = Field(default=6, ge=1, le=24)

    hermes_base_url: str = "http://127.0.0.1:8642/v1"
    hermes_model: str = "gpt-5.6-luna"
    hermes_api_key: SecretStr = SecretStr("xeon-hermes-local-bridge-2026")
    hermes_api_key_file: Path | None = None

    groq_api_key: SecretStr | None = None
    groq_api_key_file: Path | None = None

    whatsapp_send_enabled: bool = False
    evolution_api_url: str = "http://evolution-api:8080"
    evolution_instance: str = "xeon-ferreteria"
    evolution_api_key: SecretStr | None = None
    evolution_api_key_file: Path | None = None

    log_level: str = "INFO"

    def require_groq_api_key(self) -> SecretStr:
        if self.groq_api_key is not None and self.groq_api_key.get_secret_value().strip():
            return self.groq_api_key

        if self.groq_api_key_file is not None:
            try:
                value = self.groq_api_key_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise SettingsError("No se pudo leer GROQ_API_KEY_FILE.") from exc
            if value:
                return SecretStr(value)

        raise SettingsError(
            "LLM_PROVIDER=groq requiere GROQ_API_KEY o GROQ_API_KEY_FILE; "
            "no se usara una clave implicita."
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
        if self.evolution_api_key is not None and self.evolution_api_key.get_secret_value().strip():
            return self.evolution_api_key

        if self.evolution_api_key_file is not None:
            try:
                value = self.evolution_api_key_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise SettingsError("No se pudo leer EVOLUTION_API_KEY_FILE.") from exc
            if value:
                return SecretStr(value)

        raise SettingsError(
            "WHATSAPP_SEND_ENABLED=true requiere EVOLUTION_API_KEY o EVOLUTION_API_KEY_FILE."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
