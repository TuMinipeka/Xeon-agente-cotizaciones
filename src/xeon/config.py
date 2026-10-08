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

    llm_provider: Literal["mock", "grok"] = "mock"
    llm_model: str = "grok-4.6"
    llm_base_url: str = "https://api.reto.pltk.mx/v1"
    llm_max_output_tokens: int = Field(default=2048, ge=1, le=32_000)
    llm_timeout_seconds: float = Field(default=120, gt=0, le=600)
    agent_max_steps: int = Field(default=6, ge=1, le=24)

    reto_key: SecretStr | None = None
    reto_key_file: Path | None = None
    log_level: str = "INFO"

    def require_reto_key(self) -> SecretStr:
        if self.reto_key is not None and self.reto_key.get_secret_value().strip():
            return self.reto_key

        if self.reto_key_file is not None:
            try:
                value = self.reto_key_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise SettingsError("No se pudo leer RETO_KEY_FILE.") from exc
            if value:
                return SecretStr(value)

        raise SettingsError(
            "LLM_PROVIDER=grok requiere RETO_KEY o RETO_KEY_FILE; no se usara una clave implicita."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
