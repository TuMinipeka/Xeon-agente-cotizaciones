from pathlib import Path

import pytest

from xeon.adapters.llm.factory import build_llm
from xeon.adapters.llm.mock import MockLLM
from xeon.config import Settings, SettingsError


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
    assert captured["base_url"] == "https://api.x.ai/v1"
    assert captured["model"] == "test-model"


def test_evolution_secret_error_message_is_preserved() -> None:
    settings = Settings(evolution_api_key=None, evolution_api_key_file=None, _env_file=None)

    with pytest.raises(SettingsError, match="requiere EVOLUTION_API_KEY"):
        settings.require_evolution_api_key()
