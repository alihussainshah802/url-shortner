from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# The single source of truth for how long a short code may be. The settings
# validation, the redirect route's pattern and the database column all use
# these, so a link can never be created that the redirect route would refuse.
MIN_CODE_LENGTH = 4
MAX_CODE_LENGTH = 32

REDIS_SCHEMES = ("redis://", "rediss://", "unix://")

# Anchored to this file, not the working directory, so the repo-root .env is
# found no matter where the app or Alembic is started from.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # hide_input_in_errors: a validation error would otherwise print the raw input
    # dict, passwords included, into startup logs.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", hide_input_in_errors=True)

    # Either give a full DATABASE_URL, or the POSTGRES_* parts below and the URL is
    # built (with the password escaped) for you. Secrets are SecretStr so they print
    # as ********** in reprs and logs; read them with get_secret_value().
    database_url: SecretStr = SecretStr("")
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None
    postgres_db: str | None = None
    postgres_host: str = "127.0.0.1"  # not "localhost": it can stall on Windows
    postgres_port: int = 5432
    # How long to wait for Postgres to accept a connection. Without it an unreachable
    # database makes every request hang for the operating system's TCP timeout (often
    # minutes) instead of failing fast with a clean 503.
    database_connect_timeout_seconds: int = Field(default=3, ge=1)
    # Connection pool. Sync routes run on up to 40 worker threads, so the pool is the
    # real limit on concurrent database work. A thread that cannot get a connection
    # within the timeout fails with a clean 503 instead of waiting (the library default
    # is 30 s, which ties up threads and starves even cached redirects). Keep
    # pool_size + max_overflow, times the number of backend replicas, below Postgres's
    # max_connections (100 by default).
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout_seconds: float = Field(default=5, gt=0)

    # Public origin that short links are served from. The redirect route lives on
    # this origin, so it must point at the backend (or whatever fronts it).
    base_url: str = "http://localhost:8000"
    code_length: int = Field(default=7, ge=MIN_CODE_LENGTH, le=MAX_CODE_LENGTH)

    # Redirect cache. Give REDIS_HOST (+ REDIS_PASSWORD), or a full REDIS_URL; with
    # neither, the cache is off and every redirect reads Postgres. Redis is a cache
    # only: if it is down, redirects keep working.
    redis_url: str = ""
    redis_host: str = ""
    redis_port: int = 6379
    redis_password: SecretStr | None = None
    redis_tls: bool = False  # managed cloud Redis usually requires TLS
    cache_ttl_seconds: int = Field(default=3600, ge=1)
    # Kept short so a slow Redis can never make redirects slower than the database.
    redis_timeout_seconds: float = Field(default=0.2, gt=0)

    @field_validator("redis_url")
    @classmethod
    def check_redis_url(cls, value: str) -> str:
        # Redis.from_url raises on a bad scheme at the first request, which would turn
        # a typo into a 500 on every redirect. Reject it when the settings load.
        if value and not value.startswith(REDIS_SCHEMES):
            raise ValueError("REDIS_URL must start with redis://, rediss:// or unix://")
        return value

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if self.database_url.get_secret_value():
            return self
        password = self.postgres_password.get_secret_value() if self.postgres_password else ""
        if not (self.postgres_user and password and self.postgres_db):
            raise ValueError(
                "Set DATABASE_URL, or POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB."
            )
        self.database_url = SecretStr(
            URL.create(
                "postgresql+psycopg",
                username=self.postgres_user,
                password=password,
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
            ).render_as_string(hide_password=False)
        )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
