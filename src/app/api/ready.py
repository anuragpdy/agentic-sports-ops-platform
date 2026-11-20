"""Readiness endpoint: "can I serve traffic right now?".

Different from /health ("am I alive?"): if Postgres is down, /ready returns 503 so the
platform stops sending traffic, while /health stays 200 so nobody restarts the app.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.core.readiness import DependencyCheck, check_readiness
from app.schemas.health import ReadyResponse

router = APIRouter(tags=["health"])


def get_dependency_checks() -> list[DependencyCheck]:
    """Which dependencies /ready checks. Tests replace this via app.dependency_overrides."""
    # Real Postgres and Redis probes are added in slice 3 (Day 1 plan).
    raise NotImplementedError("real dependency checks are not wired up yet")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    response_model_exclude_none=True,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyResponse}},
)
async def ready(
    response: Response,
    checks: Annotated[list[DependencyCheck], Depends(get_dependency_checks)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadyResponse:
    result = await check_readiness(checks, settings.dependency_check_timeout_seconds)
    if result.status == "down":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
