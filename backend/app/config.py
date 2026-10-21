from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str
    # Public origin that short links are served from. The redirect route lives on
    # this origin, so it must point at the backend (or whatever fronts it).
    base_url: str = "http://localhost:8000"
    code_length: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # database_url comes from the environment
