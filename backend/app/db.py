from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def engine_options(settings: Settings) -> dict[str, Any]:
    """create_engine arguments. The timeouts and pool limits apply to Postgres only:
    other drivers (SQLite in tests) use different pools and reject these options."""
    options: dict[str, Any] = {"pool_pre_ping": True}
    if make_url(settings.database_url.get_secret_value()).get_backend_name() == "postgresql":
        options["connect_args"] = {"connect_timeout": settings.database_connect_timeout_seconds}
        options["pool_size"] = settings.database_pool_size
        options["max_overflow"] = settings.database_max_overflow
        options["pool_timeout"] = settings.database_pool_timeout_seconds
    return options


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url.get_secret_value(), **engine_options(settings))


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


# async on purpose: FastAPI runs a plain `def` dependency in a worker thread, and
# the point of this one is to cost nothing. Routes that may not need the database
# (cache hits) take the factory and open a session only when they do.
async def get_session_factory() -> sessionmaker[Session]:
    return get_sessionmaker()
