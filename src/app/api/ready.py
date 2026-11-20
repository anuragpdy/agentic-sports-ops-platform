"""Readiness endpoint: "can I serve traffic right now?".

Different from /health ("am I alive?"): if Postgres is down, /ready returns 503 so the
platform stops sending traffic, while /health stays 200 so nobody restarts the app.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.core.dependency_checks import build_dependency_checks
from app.core.readiness import DependencyCheck, check_readiness
from app.schemas.health import ReadyResponse

router = APIRouter(tags=["health"])


def get_dependency_checks(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DependencyCheck]:
    """Which dependencies /ready checks. Tests replace this via app.dependency_overrides."""
    return build_dependency_checks(settings)


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
