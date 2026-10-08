from pathlib import Path

import pytest

from xeon.config import Settings, SettingsError


def test_grok_profile_requires_an_explicit_secret() -> None:
    settings = Settings(llm_provider="grok", reto_key=None, reto_key_file=None, _env_file=None)

    with pytest.raises(SettingsError, match="requiere RETO_KEY"):
        settings.require_reto_key()


def test_secret_can_be_loaded_from_a_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "reto_key"
    secret_file.write_text("local-secret\n", encoding="utf-8")
    settings = Settings(llm_provider="grok", reto_key_file=secret_file, _env_file=None)

    assert settings.require_reto_key().get_secret_value() == "local-secret"
