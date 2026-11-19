"""The one interface every LLM provider implements (the "plug socket").

Code elsewhere depends on LLMProvider, never on a vendor SDK, so swapping
OpenAI / Groq / Gemini / Ollama is a config change, not a rewrite.
"""

from typing import Protocol

from app.schemas.llm import LLMRequest, LLMResponse


class LLMError(Exception):
    """Raised by providers for any failure (timeout, rate limit, bad response)."""


class LLMProvider(Protocol):
    name: str

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send messages to the model and return its reply."""
        ...
