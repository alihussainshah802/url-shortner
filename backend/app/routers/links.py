from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.schemas import LinkCreate, LinkRead
from app.services.links import CodeGenerationError, create_link

router = APIRouter(tags=["links"])


@router.post("/links", response_model=LinkRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: LinkCreate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LinkRead:
    target = str(payload.url)
    # A short link pointing back at this service would redirect in a loop.
    if urlsplit(target).netloc.lower() == urlsplit(settings.base_url).netloc.lower():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Links to this service can't be shortened.",
        )

    try:
        link = create_link(db, target, settings.code_length)
    except CodeGenerationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Couldn't generate a unique code. Try again.",
        ) from None

    return LinkRead(
        code=link.code,
        short_url=f"{settings.base_url.rstrip('/')}/{link.code}",
        original_url=link.original_url,
        created_at=link.created_at,
    )
