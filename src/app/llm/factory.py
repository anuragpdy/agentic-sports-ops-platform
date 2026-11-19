"""Picks the provider named in settings. Add real providers here as you implement them."""

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.fake import FakeProvider


def get_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeProvider(model=settings.llm_model)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")
