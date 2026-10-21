import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import MAX_CODE_LENGTH, MIN_CODE_LENGTH
from app.db import get_db
from app.services.links import get_link_by_code

router = APIRouter(tags=["redirect"])

CODE_RE = re.compile(rf"[0-9A-Za-z]{{{MIN_CODE_LENGTH},{MAX_CODE_LENGTH}}}")


# HEAD is allowed so link checkers and crawlers get the same redirect as a GET.
@router.api_route("/{code}", methods=["GET", "HEAD"], include_in_schema=False)
def redirect(code: str, db: Annotated[Session, Depends(get_db)]) -> RedirectResponse:
    # Anything that can't be a code (/favicon.ico, /robots.txt, /ab) is simply "not
    # found", not a validation error, and never reaches the database.
    if not CODE_RE.fullmatch(code):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")
    link = get_link_by_code(db, code)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")
    # 302, not 301: browsers must keep asking us so clicks can be counted and links
    # expired or edited later.
    return RedirectResponse(link.original_url, status_code=status.HTTP_302_FOUND)
