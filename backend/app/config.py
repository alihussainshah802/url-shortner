from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# The single source of truth for how long a short code may be. The settings
# validation, the redirect route's pattern and the database column all use
# these, so a link can never be created that the redirect route would refuse.
MIN_CODE_LENGTH = 4
MAX_CODE_LENGTH = 32

# Anchored to this file, not the working directory, so the repo-root .env is
# found no matter where the app or Alembic is started from.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Either give a full DATABASE_URL, or the POSTGRES_* parts below and the URL is
    # built (with the password escaped) for you.
    database_url: str = ""
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    postgres_host: str = "127.0.0.1"  # not "localhost": it can stall on Windows
    postgres_port: int = 5432

    # Public origin that short links are served from. The redirect route lives on
    # this origin, so it must point at the backend (or whatever fronts it).
    base_url: str = "http://localhost:8000"
    code_length: int = Field(default=7, ge=MIN_CODE_LENGTH, le=MAX_CODE_LENGTH)

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if self.database_url:
            return self
        if not (self.postgres_user and self.postgres_password and self.postgres_db):
            raise ValueError(
                "Set DATABASE_URL, or POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB."
            )
        self.database_url = URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
