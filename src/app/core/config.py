"""Application settings, loaded from environment variables (and a local .env file).

One place for all configuration: the rest of the code calls get_settings() and never
reads os.environ directly. pydantic validates types at startup, so a bad value fails
fast with a clear error instead of breaking deep inside a request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ai-project-template"
    app_env: Literal["local", "ci", "staging", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    llm_provider: str = "fake"
    llm_model: str = "fake-model"
    llm_timeout_seconds: float = 30.0
    llm_api_key: SecretStr = SecretStr("")

    # Dependencies. Defaults point at a local, password-less dev setup so the app and the
    # tests start without a .env (e.g. in CI). DATABASE_URL is a SecretStr because a real
    # URL contains the password; SecretStr hides it in repr() and logs.
    database_url: SecretStr = SecretStr("postgresql://localhost:5432/postgres")
    redis_url: str = "redis://localhost:6379/0"
    # Upper bound for one whole readiness check (connect + query). Must be > 0.
    dependency_check_timeout_seconds: float = Field(default=1.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it (reading env + .env on every call is wasteful)."""
    return Settings()
