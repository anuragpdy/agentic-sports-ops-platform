"""Real readiness probes for Postgres and Redis.

Each probe opens a fresh connection, runs the cheapest possible command, and closes it.
No connection is kept from startup, so the app starts even if a dependency is down and
recovers by itself when it comes back. (Day 1 has no pools; a /ready poll every few
seconds costs one short connection per dependency, which is fine.)

Probes do NOT retry: the platform calling /ready polls repeatedly, so each poll is the
retry. Retrying inside one probe would only turn a fast "connection_error" into a slow
"timeout". The overall time limit is applied by app.core.readiness.run_check.
"""

import psycopg
import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff

from app.core.config import Settings
from app.core.readiness import DependencyCheck, Probe


def postgres_probe(database_url: str) -> Probe:
    async def probe() -> None:
        # autocommit=True: don't open a transaction just to run SELECT 1.
        async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as conn:
            await conn.execute("SELECT 1")

    return probe


def redis_probe(redis_url: str, backstop_timeout_seconds: float) -> Probe:
    async def probe() -> None:
        client = aioredis.Redis.from_url(
            redis_url,
            # Deliberately NO retries (redis-py defaults to 10). Do not "fix" this: whoever
            # calls /ready polls again in a few seconds, so that poll IS the retry. Retrying
            # here would turn a stopped Redis (fast "connection_error") into a slow "timeout"
            # and make /ready itself slow exactly when things are broken.
            retry=Retry(NoBackoff(), retries=0),
            # Backstop only: run_check's asyncio.timeout fires first, so a hang is reported
            # as "timeout" rather than redis-py's own TimeoutError ("connection_error").
            socket_connect_timeout=backstop_timeout_seconds,
            socket_timeout=backstop_timeout_seconds,
        )
        try:
            await client.ping()
        finally:
            await client.aclose()

    return probe


def build_dependency_checks(settings: Settings) -> list[DependencyCheck]:
    backstop = settings.dependency_check_timeout_seconds * 2
    return [
        DependencyCheck(
            name="postgres",
            critical=True,
            probe=postgres_probe(settings.database_url.get_secret_value()),
        ),
        # Optional while Redis is only a cache. Revisit when it stores idempotency keys
        # or rate limits (see docs/specs/day01-kickoff.md).
        DependencyCheck(
            name="redis",
            critical=False,
            probe=redis_probe(settings.redis_url, backstop),
        ),
    ]
