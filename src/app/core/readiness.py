"""Readiness logic: run dependency checks concurrently, each under a timeout, and combine
the results into ok / degraded / down.

Kept free of FastAPI and of any real database code, so it can be tested with fake probes.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from app.schemas.health import CheckResult, ReadyResponse

logger = logging.getLogger(__name__)

# A probe returns normally if the dependency is usable and raises any exception if not.
Probe = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class DependencyCheck:
    name: str
    # critical=True: if it is down the app is "down" (503). False: only "degraded" (200).
    critical: bool
    probe: Probe


async def run_check(check: DependencyCheck, timeout_seconds: float) -> CheckResult:
    """Run one probe. The timeout covers the whole probe (connect + query), not just connect."""
    start = time.perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            await check.probe()
    except TimeoutError:
        logger.warning("dependency check failed: dependency=%s reason=timeout", check.name)
        return CheckResult(status="down", reason="timeout")
    except Exception as exc:
        # Log only the exception *type*: driver messages can contain hosts or connection
        # strings. Anything that isn't a timeout counts as a connection error.
        logger.warning(
            "dependency check failed: dependency=%s reason=connection_error error_type=%s",
            check.name,
            type(exc).__name__,
        )
        return CheckResult(status="down", reason="connection_error")
    latency_ms = round((time.perf_counter() - start) * 1000)
    return CheckResult(status="ok", latency_ms=latency_ms)


async def check_readiness(
    checks: Sequence[DependencyCheck], timeout_seconds: float
) -> ReadyResponse:
    """Run all checks at the same time, so /ready takes ~max(check), not sum(checks)."""
    results = await asyncio.gather(*(run_check(c, timeout_seconds) for c in checks))
    by_name = {c.name: r for c, r in zip(checks, results, strict=True)}

    failed = [c for c, r in zip(checks, results, strict=True) if r.status == "down"]
    if any(c.critical for c in failed):
        status = "down"
    elif failed:
        status = "degraded"
    else:
        status = "ok"
    return ReadyResponse(status=status, checks=by_name)
