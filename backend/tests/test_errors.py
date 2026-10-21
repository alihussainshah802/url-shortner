import logging
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.db import get_db, get_session_factory
from app.main import app

SECRET = "S3cret-Pa$$w0rd"


def broken_database() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("connection refused"))


@pytest.fixture
def db_down(client: TestClient) -> TestClient:
    """The same client, but every database access fails like an unreachable Postgres."""

    def failing_db():
        raise broken_database()
        yield  # pragma: no cover  (makes this a generator like the real dependency)

    class FailingFactory:
        def __call__(self):
            raise broken_database()

    async def failing_factory():
        return FailingFactory()

    app.dependency_overrides[get_db] = failing_db
    app.dependency_overrides[get_session_factory] = failing_factory
    return client


# --- input validation on POST /api/links ----------------------------------------------


@pytest.mark.parametrize(
    ("payload", "error_type"),
    [
        ({}, "missing"),
        ({"url": 123}, "url_type"),
        ({"url": "ftp://example.com/x"}, "url_scheme"),
        ({"url": "https://example.com/" + "a" * 2100}, "url_too_long"),
        ({"url": "https://user:pw@example.com/x"}, "url_credentials"),
        ({"url": "https://:pw@example.com/x"}, "url_credentials"),
        ({"url": "https://user@example.com/x"}, "url_credentials"),
    ],
)
def test_invalid_links_get_a_422_with_a_stable_error_type(
    client: TestClient, payload: dict, error_type: str
) -> None:
    res = client.post("/api/links", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"][0]["type"] == error_type


def test_malformed_json_and_wrong_content_type_are_422(client: TestClient) -> None:
    bad_json = client.post(
        "/api/links", content='{"url": ', headers={"content-type": "application/json"}
    )
    assert bad_json.status_code == 422
    plain = client.post(
        "/api/links", content="https://example.com", headers={"content-type": "text/plain"}
    )
    assert plain.status_code == 422


def test_a_link_without_credentials_is_still_accepted(client: TestClient) -> None:
    res = client.post(
        "/api/links", json={"url": "https://example.com/a@b"}
    )  # @ in the path is fine
    assert res.status_code == 201


# --- request ids ----------------------------------------------------------------------


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    for path in ("/api/health", "/zzzzzzz", "/favicon.ico"):
        assert re.fullmatch(r"[0-9a-f]{32}", client.get(path).headers["x-request-id"])


def test_a_sane_caller_supplied_request_id_is_echoed(client: TestClient) -> None:
    res = client.get("/api/health", headers={"X-Request-ID": "trace-abc_123.4"})
    assert res.headers["x-request-id"] == "trace-abc_123.4"


@pytest.mark.parametrize("bad", ["has spaces", "a" * 65, "semi;colon", "<script>"])
def test_an_unsafe_request_id_is_replaced(client: TestClient, bad: str) -> None:
    res = client.get("/api/health", headers={"X-Request-ID": bad})
    assert res.headers["x-request-id"] != bad
    assert re.fullmatch(r"[0-9a-f]{32}", res.headers["x-request-id"])


# --- error responses ------------------------------------------------------------------


def test_database_down_is_a_clean_503_not_a_raw_500(
    db_down: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        res = db_down.get("/abcd123")

    assert res.status_code == 503
    body = res.json()
    assert "temporarily unavailable" in body["detail"]
    assert body["request_id"] == res.headers["x-request-id"]
    assert res.headers["retry-after"] == "5"
    assert body["request_id"] in caplog.text  # the id ties the log line to the response


def test_creating_a_link_with_the_database_down_is_also_a_503(db_down: TestClient) -> None:
    res = db_down.post("/api/links", json={"url": "https://example.com/x"})
    assert res.status_code == 503
    assert res.json()["detail"].startswith("The service is temporarily unavailable")


def test_an_unexpected_error_is_a_json_500_with_a_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    def boom():
        raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_db] = boom
    quiet = TestClient(app, follow_redirects=False, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.errors"):
        res = quiet.post("/api/links", json={"url": "https://example.com/x"})

    assert res.status_code == 500
    body = res.json()
    assert body["detail"] == "Something went wrong on our side. Try again."
    assert "secret internal detail" not in res.text  # never leak internals to clients
    assert body["request_id"] == res.headers["x-request-id"]
    assert "secret internal detail" in caplog.text  # but the log has the real cause


# --- readiness ------------------------------------------------------------------------


def test_liveness_never_touches_the_database(db_down: TestClient) -> None:
    assert db_down.get("/api/health").json() == {"status": "ok"}


def test_readiness_is_ok_when_the_database_answers(client: TestClient) -> None:
    res = client.get("/api/health/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "ok", "cache": "off"}


def test_readiness_is_503_when_the_database_is_down(db_down: TestClient) -> None:
    res = db_down.get("/api/health/ready")
    assert res.status_code == 503
    assert res.json() == {"status": "unavailable", "database": "down", "cache": "off"}


# --- secrets are not leaked -----------------------------------------------------------


def test_secrets_are_hidden_in_reprs() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="postgresql://u:" + SECRET + "@h/db",
        redis_host="r",
        redis_password=SECRET,
    )
    assert SECRET not in repr(settings)
    assert SECRET not in str(settings)


def test_secrets_are_not_printed_in_validation_errors() -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url="",
            postgres_user="only-a-user",
            postgres_password=SECRET,
            redis_host="r",
            redis_password=SECRET,
        )
    assert SECRET not in str(caught.value)


# --- the database must fail fast, not make requests wait ---------------------------


def settings_for(url: str, **overrides: object) -> Settings:
    return Settings(_env_file=None, database_url=url, **overrides)  # type: ignore[call-arg]


def test_postgres_gets_connect_and_pool_limits() -> None:
    from app.db import engine_options

    options = engine_options(settings_for("postgresql+psycopg://u:p@db:5432/x"))
    assert options["connect_args"] == {"connect_timeout": 3}
    assert options["pool_pre_ping"] is True
    # The library defaults (5 + 10 connections, 30 s wait) let a burst tie up worker
    # threads for half a minute before failing.
    assert (options["pool_size"], options["max_overflow"], options["pool_timeout"]) == (10, 10, 5)


def test_pool_limits_are_configurable() -> None:
    from app.db import engine_options

    options = engine_options(
        settings_for(
            "postgresql+psycopg://u:p@db:5432/x",
            database_pool_size=2,
            database_max_overflow=0,
            database_pool_timeout_seconds=1.5,
        )
    )
    assert (options["pool_size"], options["max_overflow"], options["pool_timeout"]) == (2, 0, 1.5)


def test_other_databases_get_none_of_the_postgres_options() -> None:
    from app.db import engine_options

    assert engine_options(settings_for("sqlite://")) == {"pool_pre_ping": True}


@pytest.mark.parametrize(
    "bad",
    [
        {"database_connect_timeout_seconds": 0},
        {"database_pool_size": 0},
        {"database_max_overflow": -1},
        {"database_pool_timeout_seconds": 0},
    ],
)
def test_database_limits_reject_values_that_would_disable_them(bad: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        settings_for("sqlite://", **bad)


def test_a_full_pool_gives_up_and_becomes_a_503(client: TestClient) -> None:
    from sqlalchemy.exc import TimeoutError as PoolTimeoutError

    def pool_full():
        raise PoolTimeoutError("QueuePool limit of size 10 overflow 10 reached")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = pool_full
    res = client.post("/api/links", json={"url": "https://example.com/x"})
    assert res.status_code == 503
    assert res.json()["detail"].startswith("The service is temporarily unavailable")
