"""Data shapes for any LLM call. All providers use these, so callers never see SDK types."""

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    max_tokens: int = Field(default=512, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class LLMResponse(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
