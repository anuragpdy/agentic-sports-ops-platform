"""A deterministic, offline provider for tests, CI and local dev without API keys."""

import time

from app.schemas.llm import LLMRequest, LLMResponse


class FakeProvider:
    name = "fake"

    def __init__(self, model: str = "fake-model") -> None:
        self.model = model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.perf_counter()
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        text = f"[fake] {last_user}"
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=sum(len(m.content.split()) for m in request.messages),
            output_tokens=len(text.split()),
            latency_ms=(time.perf_counter() - start) * 1000,
        )
