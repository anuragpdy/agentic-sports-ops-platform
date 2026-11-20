"""Unit tests for the real probes, with the drivers replaced by fakes: no network."""

import asyncio
from typing import Any

import psycopg
import pytest
import redis.asyncio as aioredis
from pydantic import SecretStr

from app.core.config import Settings
from app.core.dependency_checks import build_dependency_checks, postgres_probe, redis_probe


def test_checks_are_wired_with_spec_criticality() -> None:
    checks = build_dependency_checks(Settings(_env_file=None))
    assert [(c.name, c.critical) for c in checks] == [("postgres", True), ("redis", False)]


class FakeConn:
    """Stands in for psycopg.AsyncConnection. Records calls; can fail on execute."""

    def __init__(self, calls: dict[str, Any], execute_error: Exception | None) -> None:
        self.calls = calls
        self.execute_error = execute_error

    async def __aenter__(self) -> "FakeConn":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.calls["closed"] = True

    async def execute(self, query: str) -> None:
        self.calls["query"] = query
        if self.execute_error:
            raise self.execute_error


def patch_postgres(
    monkeypatch: pytest.MonkeyPatch, execute_error: Exception | None = None
) -> dict[str, Any]:
    calls: dict[str, Any] = {}

    async def fake_connect(conninfo: str, **kwargs: Any) -> FakeConn:
        calls["conninfo"] = conninfo
        calls["kwargs"] = kwargs
        return FakeConn(calls, execute_error)

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", fake_connect)
    return calls


def test_postgres_probe_uses_url_and_autocommit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = patch_postgres(monkeypatch)
    asyncio.run(postgres_probe("postgresql://u:p@h/db")())
    assert calls == {
        "conninfo": "postgresql://u:p@h/db",
        "kwargs": {"autocommit": True},
        "query": "SELECT 1",
        "closed": True,
    }


def test_postgres_probe_closes_connection_even_when_query_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = patch_postgres(monkeypatch, execute_error=psycopg.OperationalError("boom"))
    with pytest.raises(psycopg.OperationalError):
        asyncio.run(postgres_probe("postgresql://u:p@h/db")())
    assert calls["query"] == "SELECT 1"
    assert calls["closed"] is True


class FakeRedis:
    def __init__(self, ping_error: Exception | None) -> None:
        self.ping_error = ping_error
        self.closed = False

    async def ping(self) -> bool:
        if self.ping_error:
            raise self.ping_error
        return True

    async def aclose(self) -> None:
        self.closed = True


def patch_redis(monkeypatch: pytest.MonkeyPatch, fake: FakeRedis) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_from_url(url: str, **kwargs: Any) -> FakeRedis:
        seen["url"] = url
        seen.update(kwargs)
        return fake

    monkeypatch.setattr(aioredis.Redis, "from_url", fake_from_url)
    return seen


def test_redis_probe_pings_without_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis(ping_error=None)
    seen = patch_redis(monkeypatch, fake)
    asyncio.run(redis_probe("redis://h:6379/0", backstop_timeout_seconds=2.0)())
    assert seen["url"] == "redis://h:6379/0"
    assert seen["retry"].get_retries() == 0
    assert seen["socket_connect_timeout"] == 2.0
    assert fake.closed


def test_redis_probe_closes_client_even_when_ping_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis(ping_error=ConnectionError("boom"))
    patch_redis(monkeypatch, fake)
    with pytest.raises(ConnectionError):
        asyncio.run(redis_probe("redis://h:6379/0", backstop_timeout_seconds=2.0)())
    assert fake.closed


def test_redis_backstop_is_longer_than_check_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    # The outer asyncio.timeout must fire first, so a hang is reported as "timeout".
    seen = patch_redis(monkeypatch, FakeRedis(ping_error=None))
    settings = Settings(
        _env_file=None,
        dependency_check_timeout_seconds=1.0,
        database_url=SecretStr("postgresql://localhost/x"),
    )
    redis_check = build_dependency_checks(settings)[1]
    asyncio.run(redis_check.probe())
    assert seen["socket_connect_timeout"] > settings.dependency_check_timeout_seconds
    assert seen["socket_timeout"] > settings.dependency_check_timeout_seconds
