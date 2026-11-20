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


def test_dependency_settings_have_working_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.dependency_check_timeout_seconds == 1.0
    assert "localhost" in settings.database_url.get_secret_value()


def test_database_url_is_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql://user:hunter2-secret@db:5432/app"
    monkeypatch.setenv("DATABASE_URL", url)
    settings = Settings(_env_file=None)
    assert "hunter2-secret" not in repr(settings)
    assert "hunter2-secret" not in str(settings.model_dump())
    assert settings.database_url.get_secret_value() == url


@pytest.mark.parametrize("bad", ["0", "-1", "abc"])
def test_dependency_timeout_must_be_positive_number(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    monkeypatch.setenv("DEPENDENCY_CHECK_TIMEOUT_SECONDS", bad)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
