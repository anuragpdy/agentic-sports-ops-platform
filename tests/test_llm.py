import asyncio

import pytest

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.schemas.llm import LLMRequest, Message


def test_factory_returns_fake_provider() -> None:
    provider: LLMProvider = get_provider(Settings(_env_file=None, llm_provider="fake"))
    assert provider.name == "fake"


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_provider(Settings(_env_file=None, llm_provider="nope"))


def test_fake_provider_echoes_last_user_message() -> None:
    provider = get_provider(Settings(_env_file=None, llm_provider="fake"))
    request = LLMRequest(
        messages=[
            Message(role="system", content="Be brief."),
            Message(role="user", content="What is 2 + 2?"),
        ]
    )
    response = asyncio.run(provider.complete(request))
    assert response.text == "[fake] What is 2 + 2?"
    assert response.input_tokens > 0
