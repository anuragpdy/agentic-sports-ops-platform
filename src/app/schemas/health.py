"""Response shapes for /ready. Only statuses, latencies and fixed reason codes: never URLs,
hostnames or error text, so a response can't leak infrastructure details or secrets."""

from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "down"]
DownReason = Literal["timeout", "connection_error"]
ReadyStatus = Literal["ok", "degraded", "down"]


class CheckResult(BaseModel):
    status: CheckStatus
    # Set only when status == "ok"; how long the whole check took.
    latency_ms: int | None = None
    # Set only when status == "down".
    reason: DownReason | None = None


class ReadyResponse(BaseModel):
    status: ReadyStatus
    checks: dict[str, CheckResult]
