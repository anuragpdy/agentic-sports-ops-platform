"""Health endpoint: lets load balancers, Docker and uptime monitors ask "are you alive?"."""

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    version: str


@router.get("/health")
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok", app=settings.app_name, env=settings.app_env, version=__version__
    )
