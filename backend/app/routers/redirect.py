from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.links import get_link_by_code

router = APIRouter(tags=["redirect"])


@router.get("/{code}", include_in_schema=False)
def redirect(
    code: Annotated[str, Path(pattern=r"^[0-9A-Za-z]{4,32}$")],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    link = get_link_by_code(db, code)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")
    # 302, not 301: browsers must keep asking us so clicks can be counted and links
    # expired or edited later.
    return RedirectResponse(link.original_url, status_code=status.HTTP_302_FOUND)
