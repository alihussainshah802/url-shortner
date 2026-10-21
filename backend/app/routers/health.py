from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.services.cache import LinkCache, get_cache_dep

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Deliberately does not touch the database, so a
    database blip never makes an orchestrator kill a healthy process."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
def ready(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
    cache: Annotated[LinkCache, Depends(get_cache_dep)],
) -> dict[str, str] | JSONResponse:
    """Readiness: can this instance serve traffic. Needs the database; Redis is only
    reported, because redirects work without it."""
    cache_state = "off" if not cache.enabled else ("ok" if cache.available else "down")
    try:
        with session_factory() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "down", "cache": cache_state},
        )
    return {"status": "ok", "database": "ok", "cache": cache_state}
