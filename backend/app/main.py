from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.errors import register_error_handlers
from app.middleware import RequestIdMiddleware
from app.routers import health, links, redirect
from app.services.cache import get_cache


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Read the settings and build the cache client once at startup, so a bad value
    # (e.g. CODE_LENGTH=3 or a REDIS_URL typo) stops the server immediately instead
    # of failing every request later.
    get_settings()
    cache = get_cache()
    yield
    cache.close()


app = FastAPI(title="url-shortner API", lifespan=lifespan)

app.add_middleware(RequestIdMiddleware)
register_error_handlers(app)

# Everything the frontend calls lives under /api, so the Vite dev proxy can
# forward a single prefix and no CORS configuration is needed.
app.include_router(health.router, prefix="/api")
app.include_router(links.router, prefix="/api")

# Catch-all for short codes. Registered last so it never shadows another route.
app.include_router(redirect.router)
