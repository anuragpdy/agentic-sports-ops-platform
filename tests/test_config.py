import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "5")
    settings = Settings(_env_file=None)
    assert settings.app_env == "staging"
    assert settings.llm_timeout_seconds == 5.0


def test_invalid_setting_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production-ish")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_api_key_is_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-very-secret")
    settings = Settings(_env_file=None)
    assert "sk-very-secret" not in repr(settings)
    assert settings.llm_api_key.get_secret_value() == "sk-very-secret"
