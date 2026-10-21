import fakeredis
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.main import app
from app.models import Link
from app.services import cache as cache_module
from app.services.cache import (
    KEY_PREFIX,
    RETRY_AFTER_SECONDS,
    LinkCache,
    get_cache,
    get_cache_dep,
)

TTL = 600
TARGET = "https://example.com/cached"
NO_ENV = {"_env_file": None, "database_url": "sqlite://"}


class FlakyRedis:
    """Delegates to a fake Redis, but raises like an unreachable server while `down`."""

    def __init__(self, backend: fakeredis.FakeRedis, *, down: bool = True) -> None:
        self.backend = backend
        self.down = down
        self.calls = 0

    def get(self, key: str) -> str | None:
        self.calls += 1
        if self.down:
            raise RedisConnectionError("connection refused")
        return self.backend.get(key)  # type: ignore[return-value]

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.calls += 1
        if self.down:
            raise RedisConnectionError("connection refused")
        self.backend.set(key, value, ex=ex)

    def close(self) -> None:
        pass


@pytest.fixture
def redis_server() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cached_client(client: TestClient, redis_server: fakeredis.FakeRedis) -> TestClient:
    app.dependency_overrides[get_cache_dep] = _async_value(lambda: LinkCache(redis_server, TTL))
    return client


@pytest.fixture
def fresh_settings(monkeypatch: pytest.MonkeyPatch):
    """Lets a test set REDIS_* env vars and rebuild get_settings()/get_cache() from them."""

    def apply(**env: str) -> None:
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        get_cache.cache_clear()

    yield apply
    monkeypatch.undo()
    get_settings.cache_clear()
    get_cache.cache_clear()


def _async_value(factory):
    """Wraps a factory as an async dependency override (the real dependencies are async)."""

    async def dependency():
        return factory()

    return dependency


def create_code(client: TestClient) -> str:
    return client.post("/api/links", json={"url": TARGET}).json()["code"]


# --- behaviour of the cache on the redirect route ------------------------------------


def test_first_redirect_misses_then_later_ones_hit(cached_client: TestClient) -> None:
    code = create_code(cached_client)

    first = cached_client.get(f"/{code}")
    second = cached_client.get(f"/{code}")

    assert (first.status_code, first.headers["x-cache"]) == (302, "MISS")
    assert (second.status_code, second.headers["x-cache"]) == (302, "HIT")
    assert first.headers["location"] == second.headers["location"] == TARGET


def test_a_hit_is_served_without_touching_the_database(
    cached_client: TestClient, session_maker: sessionmaker[Session]
) -> None:
    code = create_code(cached_client)
    cached_client.get(f"/{code}")  # fills the cache

    with session_maker() as session:
        session.execute(delete(Link))
        session.commit()

    res = cached_client.get(f"/{code}")
    assert (res.status_code, res.headers["x-cache"]) == (302, "HIT")
    assert res.headers["location"] == TARGET


def test_a_hit_never_opens_a_database_session(
    cached_client: TestClient, session_maker: sessionmaker[Session]
) -> None:
    from app.db import get_session_factory

    code = create_code(cached_client)
    cached_client.get(f"/{code}")  # fills the cache

    opened: list[int] = []

    async def counting_factory() -> sessionmaker[Session]:
        def make() -> Session:
            opened.append(1)
            return session_maker()

        return make  # type: ignore[return-value]

    app.dependency_overrides[get_session_factory] = counting_factory

    assert cached_client.get(f"/{code}").headers["x-cache"] == "HIT"
    assert opened == []  # a hit needed no session
    cached_client.get("/zzzzzzz")  # a miss does
    assert opened == [1]


def test_cached_entries_expire(
    cached_client: TestClient, redis_server: fakeredis.FakeRedis
) -> None:
    code = create_code(cached_client)
    cached_client.get(f"/{code}")

    ttl = redis_server.ttl(KEY_PREFIX + code)
    assert 0 < ttl <= TTL


def test_unknown_codes_are_not_cached(
    cached_client: TestClient, redis_server: fakeredis.FakeRedis
) -> None:
    res = cached_client.get("/zzzzzzz")
    assert res.status_code == 404
    assert redis_server.keys("*") == []


def test_head_uses_the_cache_too(cached_client: TestClient) -> None:
    code = create_code(cached_client)
    cached_client.get(f"/{code}")

    res = cached_client.head(f"/{code}")
    assert (res.status_code, res.headers["x-cache"]) == (302, "HIT")


def test_no_cache_header_when_the_cache_is_off(client: TestClient) -> None:
    code = create_code(client)
    res = client.get(f"/{code}")
    assert res.status_code == 302
    assert "x-cache" not in res.headers


# --- Redis down: redirects keep working, and the header says BYPASS -------------------


def test_redirects_keep_working_when_redis_is_down(
    client: TestClient, redis_server: fakeredis.FakeRedis
) -> None:
    flaky = FlakyRedis(redis_server)
    app.dependency_overrides[get_cache_dep] = _async_value(lambda: LinkCache(flaky, TTL))  # type: ignore[arg-type]
    code = create_code(client)

    res = client.get(f"/{code}")
    assert res.status_code == 302
    assert res.headers["location"] == TARGET
    assert res.headers["x-cache"] == "BYPASS"  # not MISS: Redis was never usable


def test_header_distinguishes_a_real_miss_from_an_outage(
    client: TestClient, redis_server: fakeredis.FakeRedis
) -> None:
    flaky = FlakyRedis(redis_server, down=False)
    app.dependency_overrides[get_cache_dep] = _async_value(lambda: LinkCache(flaky, TTL))  # type: ignore[arg-type]
    code = create_code(client)

    assert client.get(f"/{code}").headers["x-cache"] == "MISS"  # Redis up, nothing cached yet
    flaky.down = True
    assert client.get(f"/{code}").headers["x-cache"] == "BYPASS"  # first request trips it
    assert client.get(f"/{code}").headers["x-cache"] == "BYPASS"  # skipped during the window


def test_after_a_failure_redis_is_skipped_until_the_retry_window_passes(
    monkeypatch: pytest.MonkeyPatch, redis_server: fakeredis.FakeRedis
) -> None:
    now = [1000.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: now[0])
    flaky = FlakyRedis(redis_server)
    cache = LinkCache(flaky, TTL)  # type: ignore[arg-type]

    assert cache.get("abcd123") is None  # first call hits Redis and fails
    assert flaky.calls == 1
    assert cache.enabled and not cache.available

    for _ in range(10):  # inside the window: Redis is not even tried
        assert cache.get("abcd123") is None
        cache.set("abcd123", TARGET)
    assert flaky.calls == 1

    now[0] += RETRY_AFTER_SECONDS + 0.1  # window over: try again
    assert cache.available
    assert cache.get("abcd123") is None
    assert flaky.calls == 2


def test_cache_recovers_once_redis_is_back(
    monkeypatch: pytest.MonkeyPatch, redis_server: fakeredis.FakeRedis
) -> None:
    now = [1000.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: now[0])
    flaky = FlakyRedis(redis_server)
    cache = LinkCache(flaky, TTL)  # type: ignore[arg-type]
    assert cache.get("abcd123") is None

    flaky.down = False  # Redis comes back
    now[0] += RETRY_AFTER_SECONDS + 0.1
    cache.set("abcd123", TARGET)
    assert cache.get("abcd123") == TARGET
    assert cache.available


# --- settings and the real get_cache() construction -----------------------------------


def test_cache_settings_defaults_and_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("REDIS_URL", "REDIS_HOST", "REDIS_PASSWORD"):  # conftest blanks these
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(**NO_ENV)  # type: ignore[arg-type]
    assert defaults.redis_url == defaults.redis_host == ""
    assert defaults.redis_password is None
    assert defaults.cache_ttl_seconds == 3600
    assert defaults.redis_timeout_seconds == pytest.approx(0.2)

    for bad in ({"cache_ttl_seconds": 0}, {"redis_timeout_seconds": 0}):
        with pytest.raises(ValidationError):
            Settings(**NO_ENV, **bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("url", ["localhost:6379", "http://localhost:6379", "127.0.0.1"])
def test_a_redis_url_without_a_redis_scheme_is_rejected(url: str) -> None:
    with pytest.raises(ValidationError, match="REDIS_URL must start with"):
        Settings(**NO_ENV, redis_url=url)  # type: ignore[arg-type]


@pytest.mark.parametrize("url", ["", "redis://h:6379/0", "rediss://h:6380/1", "unix:///tmp/r.sock"])
def test_valid_redis_urls_are_accepted(url: str) -> None:
    assert Settings(**NO_ENV, redis_url=url).redis_url == url  # type: ignore[arg-type]


def test_get_cache_is_off_when_nothing_is_configured(fresh_settings) -> None:
    fresh_settings(REDIS_URL="", REDIS_HOST="")
    cache = get_cache()
    assert not cache.enabled and not cache.available
    assert cache.get("abcd123") is None


def test_get_cache_from_host_and_password_applies_timeouts_and_ttl(fresh_settings) -> None:
    fresh_settings(
        REDIS_URL="",
        REDIS_HOST="redis.internal",
        REDIS_PORT="6390",
        REDIS_PASSWORD="p@ss/w:rd#?%",  # no URL escaping needed with separate settings
        REDIS_TIMEOUT_SECONDS="0.5",
        CACHE_TTL_SECONDS="120",
    )
    cache = get_cache()
    assert cache.enabled and cache.ttl_seconds == 120

    kwargs = cache.client.connection_pool.connection_kwargs
    assert (kwargs["host"], kwargs["port"]) == ("redis.internal", 6390)
    assert kwargs["password"] == "p@ss/w:rd#?%"
    assert kwargs["socket_timeout"] == kwargs["socket_connect_timeout"] == 0.5
    assert kwargs["decode_responses"] is True


def test_get_cache_can_use_tls_for_managed_redis(fresh_settings) -> None:
    from redis.connection import SSLConnection

    fresh_settings(
        REDIS_URL="", REDIS_HOST="redis.example.com", REDIS_PORT="6380", REDIS_TLS="true"
    )
    assert get_cache().client.connection_pool.connection_class is SSLConnection

    fresh_settings(REDIS_TLS="false")
    assert get_cache().client.connection_pool.connection_class is not SSLConnection


def test_get_cache_from_url_applies_timeouts_and_ttl(fresh_settings) -> None:
    fresh_settings(REDIS_URL="redis://h:6379/2", REDIS_HOST="", CACHE_TTL_SECONDS="90")
    cache = get_cache()
    assert cache.ttl_seconds == 90

    kwargs = cache.client.connection_pool.connection_kwargs
    assert (kwargs["host"], kwargs["db"]) == ("h", 2)
    assert kwargs["socket_timeout"] == pytest.approx(0.2)


# --- startup and shutdown -------------------------------------------------------------


def test_a_bad_redis_url_stops_startup_instead_of_breaking_every_redirect(fresh_settings) -> None:
    fresh_settings(REDIS_URL="localhost:6379")
    with pytest.raises(ValidationError, match="REDIS_URL"), TestClient(app):
        pass


def test_shutdown_closes_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    class Spy(LinkCache):
        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr("app.main.get_cache", lambda: Spy(None, TTL))
    with TestClient(app):
        assert closed == []
    assert closed == [True]
