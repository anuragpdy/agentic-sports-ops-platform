"""Application settings, loaded from environment variables (and a local .env file).

One place for all configuration: the rest of the code calls get_settings() and never
reads os.environ directly. pydantic validates types at startup, so a bad value fails
fast with a clear error instead of breaking deep inside a request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
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


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it (reading env + .env on every call is wasteful)."""
    return Settings()
