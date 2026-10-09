from fastapi import APIRouter

from ... import __version__
from ...core.config import get_settings
from ...models import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(version=__version__, environment=settings.environment)
