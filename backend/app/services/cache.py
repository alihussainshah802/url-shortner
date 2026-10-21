import logging
import time
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "link:"
# After a Redis failure, skip Redis for this long instead of paying the timeout on
# every request while it is down.
RETRY_AFTER_SECONDS = 5.0


class LinkCache:
    """Look-aside cache for code -> original URL.

    Fails open: any Redis problem is logged and treated as a cache miss, so a cache
    outage never becomes a redirect outage.
    """

    def __init__(self, client: Redis | None, ttl_seconds: int) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._skip_until = 0.0

    @property
    def enabled(self) -> bool:
        """A Redis is configured at all."""
        return self._client is not None

    @property
    def available(self) -> bool:
        """Configured, and not currently being skipped after a failure."""
        return self._live_client() is not None

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    @property
    def client(self) -> Redis | None:
        return self._client

    def get(self, code: str) -> str | None:
        client = self._live_client()
        if client is None:
            return None
        try:
            value = client.get(KEY_PREFIX + code)
        except RedisError as error:
            self._tripped(error)
            return None
        return value if isinstance(value, str) else None

    def set(self, code: str, original_url: str) -> None:
        client = self._live_client()
        if client is None:
            return
        try:
            client.set(KEY_PREFIX + code, original_url, ex=self._ttl)
        except RedisError as error:
            self._tripped(error)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def _live_client(self) -> Redis | None:
        if self._client is None or time.monotonic() < self._skip_until:
            return None
        return self._client

    def _tripped(self, error: RedisError) -> None:
        self._skip_until = time.monotonic() + RETRY_AFTER_SECONDS
        logger.warning(
            "Redis unavailable (%s); serving redirects from the database for %.0fs",
            type(error).__name__,
            RETRY_AFTER_SECONDS,
        )


@lru_cache
def get_cache() -> LinkCache:
    settings = get_settings()
    options = {
        "decode_responses": True,
        "socket_timeout": settings.redis_timeout_seconds,
        "socket_connect_timeout": settings.redis_timeout_seconds,
    }
    client: Redis | None = None
    if settings.redis_url:
        client = Redis.from_url(settings.redis_url, **options)
    elif settings.redis_host:
        # Host + password as separate settings, so the password never has to be
        # escaped into a URL.
        password = settings.redis_password.get_secret_value() if settings.redis_password else ""
        client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=password or None,  # "" in .env means no password
            ssl=settings.redis_tls,
            **options,
        )
    return LinkCache(client, settings.cache_ttl_seconds)


# async on purpose: FastAPI runs a plain `def` dependency on a worker thread, which
# would cost every redirect a thread hop just to fetch an object that already exists.
async def get_cache_dep() -> LinkCache:
    return get_cache()
