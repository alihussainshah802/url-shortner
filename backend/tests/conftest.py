import os

# Must be set before app modules read settings.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("BASE_URL", "http://short.test")
# Always off in tests, even if a local .env or the shell sets any of them: tests that
# need a cache install their own fake Redis (see test_cache.py).
for _name in ("REDIS_URL", "REDIS_HOST", "REDIS_PASSWORD"):
    os.environ[_name] = ""

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, get_db, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def session_maker() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def client(session_maker: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        with session_maker() as session:
            yield session

    async def override_session_factory() -> sessionmaker[Session]:
        return session_maker

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = override_session_factory
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()
