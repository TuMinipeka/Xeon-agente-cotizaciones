import asyncio
from pathlib import Path

import pytest

from xeon.adapters.llm.factory import build_llm
from xeon.adapters.llm.mock import MockLLM
from xeon.config import Settings, SettingsError


def test_grok_is_the_default_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("LLM_PROVIDER", "GROK_BASE_URL", "GROK_MODEL", "GROK_API_KEY_FILE"):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "grok"
    assert settings.grok_base_url == "https://api.reto.pltk.mx/v1"
    assert settings.grok_model == "grok-4.6"
    assert settings.grok_api_key_file == Path("secrets/grok_api_key.txt")


def test_groq_profile_requires_an_explicit_secret() -> None:
    settings = Settings(
        llm_provider="groq", groq_api_key=None, groq_api_key_file=None, _env_file=None
    )

    with pytest.raises(SettingsError, match="requiere GROQ_API_KEY"):
        settings.require_groq_api_key()


def test_secret_can_be_loaded_from_a_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "groq_api_key"
    secret_file.write_text("local-secret\n", encoding="utf-8")
    settings = Settings(llm_provider="groq", groq_api_key_file=secret_file, _env_file=None)

    assert settings.require_groq_api_key().get_secret_value() == "local-secret"


def test_grok_profile_requires_an_explicit_secret() -> None:
    settings = Settings(
        llm_provider="grok",
        grok_model="test-model",
        grok_api_key=None,
        grok_api_key_file=None,
        _env_file=None,
    )

    with pytest.raises(SettingsError, match="requiere GROK_API_KEY"):
        build_llm(settings)


def test_grok_missing_key_file_has_sanitized_error(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing-grok-api-key"
    settings = Settings(
        llm_provider="grok",
        grok_api_key=None,
        grok_api_key_file=missing_file,
        _env_file=None,
    )

    with pytest.raises(SettingsError, match="No se pudo leer GROK_API_KEY_FILE") as exc:
        build_llm(settings)

    assert str(missing_file) not in str(exc.value)


def test_grok_profile_requires_an_explicit_model() -> None:
    settings = Settings(
        llm_provider="grok", grok_api_key="test-secret", grok_model="  ", _env_file=None
    )

    with pytest.raises(SettingsError, match="requiere GROK_MODEL explicito"):
        build_llm(settings)


def test_grok_secret_can_be_loaded_from_a_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "grok_api_key"
    secret_file.write_text("local-test-secret\n", encoding="utf-8")
    settings = Settings(
        llm_provider="grok",
        grok_model="test-model",
        grok_api_key=None,
        grok_api_key_file=secret_file,
        _env_file=None,
    )

    assert settings.require_grok_api_key().get_secret_value() == "local-test-secret"


def test_grok_factory_reports_the_constructed_provider_and_model(tmp_path: Path) -> None:
    secret_file = tmp_path / "grok_api_key"
    secret_file.write_text("local-test-secret\n", encoding="utf-8")
    settings = Settings(
        llm_provider="grok",
        grok_api_key=None,
        grok_api_key_file=secret_file,
        _env_file=None,
    )

    llm = build_llm(settings)
    try:
        assert llm.provider_name == "grok"
        assert llm.model == "grok-4.6"
    finally:
        asyncio.run(llm.aclose())


def test_grok_factory_reuses_openai_compatible_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_adapter(**kwargs: object) -> MockLLM:
        captured.update(kwargs)
        return MockLLM()

    monkeypatch.setattr("xeon.adapters.llm.factory.OpenAICompatibleLLM", fake_adapter)
    settings = Settings(
        llm_provider="grok", grok_api_key="test-secret", grok_model="test-model", _env_file=None
    )

    assert isinstance(build_llm(settings), MockLLM)
    assert captured["provider_name"] == "grok"
    assert captured["base_url"] == "https://api.reto.pltk.mx/v1"
    assert captured["model"] == "test-model"


def test_kapso_channel_defaults_and_missing_secret(tmp_path: Path) -> None:
    settings = Settings(
        llm_provider="mock",
        kapso_webhook_secret=None,
        kapso_webhook_secret_file=tmp_path / "absent",
        _env_file=None,
    )
    assert settings.kapso_api_base_url == "https://api.kapso.ai"
    assert settings.meta_graph_version == "v24.0"
    with pytest.raises(SettingsError, match="KAPSO_WEBHOOK_SECRET_FILE") as error:
        settings.require_kapso_webhook_secret()
    assert str(tmp_path) not in str(error.value)


def test_kapso_secrets_can_be_loaded_from_files(tmp_path: Path) -> None:
    api_file = tmp_path / "api"
    webhook_file = tmp_path / "webhook"
    api_file.write_text("test-api-key", encoding="utf-8")
    webhook_file.write_text("test-webhook-secret", encoding="utf-8")
    settings = Settings(
        llm_provider="mock",
        kapso_api_key_file=api_file,
        kapso_webhook_secret_file=webhook_file,
        _env_file=None,
    )
    assert settings.require_kapso_api_key().get_secret_value() == "test-api-key"
    assert settings.require_kapso_webhook_secret().get_secret_value() == "test-webhook-secret"
