import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, sessionmaker

from app.config import MAX_CODE_LENGTH, MIN_CODE_LENGTH
from app.db import get_session_factory
from app.services.cache import LinkCache, get_cache_dep
from app.services.links import get_link_by_code

router = APIRouter(tags=["redirect"])

CODE_RE = re.compile(rf"[0-9A-Za-z]{{{MIN_CODE_LENGTH},{MAX_CODE_LENGTH}}}")


def redirect_to(url: str, cache: LinkCache, *, hit: bool) -> RedirectResponse:
    # 302, not 301: browsers must keep asking us so clicks can be counted and links
    # expired or edited later.
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    if cache.enabled:
        # Lets load tests and monitoring see the cache hit rate from outside. BYPASS
        # means Redis is configured but was not usable, so it must not count as a miss.
        if hit:
            response.headers["X-Cache"] = "HIT"
        else:
            response.headers["X-Cache"] = "MISS" if cache.available else "BYPASS"
    return response


# HEAD is allowed so link checkers and crawlers get the same redirect as a GET.
@router.api_route("/{code}", methods=["GET", "HEAD"], include_in_schema=False)
def redirect(
    code: str,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
    cache: Annotated[LinkCache, Depends(get_cache_dep)],
) -> RedirectResponse:
    # Anything that can't be a code (/favicon.ico, /robots.txt, /ab) is simply "not
    # found", not a validation error, and never reaches the cache or the database.
    if not CODE_RE.fullmatch(code):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")

    cached = cache.get(code)
    if cached is not None:
        return redirect_to(cached, cache, hit=True)  # no database session was opened

    with session_factory() as db:
        link = get_link_by_code(db, code)
    if link is None:
        # Misses are not cached: scanners probe random codes that never repeat.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")
    cache.set(code, link.original_url)
    return redirect_to(link.original_url, cache, hit=False)
