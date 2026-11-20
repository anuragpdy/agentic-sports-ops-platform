"""Unit tests for /ready. All probes are fakes: no containers, no network."""

import asyncio
import logging
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.ready import get_dependency_checks
from app.core.config import Settings, get_settings
from app.core.readiness import DependencyCheck, Probe
from app.main import app

SECRET_ERROR = "connect failed: postgresql://user:hunter2@db.internal:5432/app"


async def ok() -> None:
    return None


async def refused() -> None:
    raise ConnectionRefusedError(SECRET_ERROR)


async def hangs() -> None:
    await asyncio.sleep(10)


def slow_ok(seconds: float) -> Probe:
    async def probe() -> None:
        await asyncio.sleep(seconds)

    return probe


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_checks(postgres: Probe, redis: Probe, timeout: float = 1.0) -> None:
    """Swap the real checks (and timeout) for fakes for this test."""
    checks = [
        DependencyCheck(name="postgres", critical=True, probe=postgres),
        DependencyCheck(name="redis", critical=False, probe=redis),
    ]
    app.dependency_overrides[get_dependency_checks] = lambda: checks
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, dependency_check_timeout_seconds=timeout
    )


def test_all_ok(client: TestClient) -> None:
    use_checks(postgres=ok, redis=ok)
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    for name in ("postgres", "redis"):
        assert body["checks"][name]["status"] == "ok"
        assert isinstance(body["checks"][name]["latency_ms"], int)
        assert "reason" not in body["checks"][name]


def test_redis_down_is_degraded_not_503(client: TestClient) -> None:
    use_checks(postgres=ok, redis=refused)
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] == {"status": "down", "reason": "connection_error"}
    assert body["checks"]["postgres"]["status"] == "ok"


def test_postgres_down_is_503(client: TestClient) -> None:
    use_checks(postgres=refused, redis=ok)
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "down"
    assert body["checks"]["postgres"] == {"status": "down", "reason": "connection_error"}


def test_both_down_is_503(client: TestClient) -> None:
    use_checks(postgres=refused, redis=refused)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "down"


def test_hanging_postgres_times_out_quickly(client: TestClient) -> None:
    use_checks(postgres=hangs, redis=ok, timeout=0.1)
    start = time.perf_counter()
    response = client.get("/ready")
    elapsed = time.perf_counter() - start
    assert response.status_code == 503
    assert response.json()["checks"]["postgres"] == {"status": "down", "reason": "timeout"}
    assert elapsed < 1.0


def test_checks_run_concurrently(client: TestClient) -> None:
    # Each probe takes 0.3 s. Sequential would be >= 0.6 s; concurrent is ~0.3 s.
    use_checks(postgres=slow_ok(0.3), redis=slow_ok(0.3))
    start = time.perf_counter()
    response = client.get("/ready")
    elapsed = time.perf_counter() - start
    assert response.json()["status"] == "ok"
    assert elapsed < 0.55


def test_error_text_never_leaks(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    use_checks(postgres=refused, redis=refused)
    with caplog.at_level(logging.WARNING):
        response = client.get("/ready")
    for secret in ("hunter2", "db.internal", "postgresql://"):
        assert secret not in response.text
        assert secret not in caplog.text
    # ...but the log still says which dependency failed and how.
    assert "dependency=postgres reason=connection_error" in caplog.text
    assert "error_type=ConnectionRefusedError" in caplog.text


def test_health_ignores_dependencies(client: TestClient) -> None:
    use_checks(postgres=refused, redis=refused)
    assert client.get("/health").status_code == 200
