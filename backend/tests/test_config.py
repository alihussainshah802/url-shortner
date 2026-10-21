from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import ENV_FILE, MAX_CODE_LENGTH, MIN_CODE_LENGTH, Settings, get_settings
from app.main import app


def settings_with(code_length: int) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]  # keep tests independent of a local .env
        database_url="sqlite://",
        base_url="http://short.test",
        code_length=code_length,
    )


def test_env_file_is_anchored_to_the_repo_root_not_the_working_directory() -> None:
    assert ENV_FILE.is_absolute()
    assert ENV_FILE.name == ".env"
    assert ENV_FILE.parent == Path(__file__).resolve().parents[2]


def test_env_file_is_found_from_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == ENV_FILE


def test_database_url_is_built_from_parts_with_the_password_escaped() -> None:
    password = "p@ss/w:rd#?%"
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="",
        postgres_user="shortner",
        postgres_password=password,
        postgres_db="shortner",
        postgres_host="db",
    )
    url = make_url(settings.database_url.get_secret_value())
    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.host, url.port, url.database) == ("shortner", "db", 5432, "shortner")
    assert url.password == password
    assert password not in settings.database_url.get_secret_value()  # percent-encoded


def test_an_explicit_database_url_wins_over_the_parts() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url="sqlite://",
        postgres_user="u",
        postgres_password="p",
        postgres_db="d",
    )
    assert settings.database_url.get_secret_value() == "sqlite://"


def test_missing_database_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None, database_url="", postgres_user="only-a-user")  # type: ignore[call-arg]


@pytest.mark.parametrize("length", [MIN_CODE_LENGTH, 7, MAX_CODE_LENGTH])
def test_accepts_code_lengths_in_range(length: int) -> None:
    assert settings_with(length).code_length == length


@pytest.mark.parametrize("length", [-1, 0, 3, MAX_CODE_LENGTH + 1, 40])
def test_rejects_code_lengths_out_of_range(length: int) -> None:
    with pytest.raises(ValidationError):
        settings_with(length)


@pytest.mark.parametrize("length", [MIN_CODE_LENGTH, MAX_CODE_LENGTH])
def test_links_at_the_length_limits_still_redirect(client: TestClient, length: int) -> None:
    app.dependency_overrides[get_settings] = lambda: settings_with(length)

    created = client.post("/api/links", json={"url": "https://example.com/limit"}).json()
    assert len(created["code"]) == length

    res = client.get(f"/{created['code']}")
    assert res.status_code == 302
    assert res.headers["location"] == "https://example.com/limit"


def test_bad_code_length_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODE_LENGTH", "3")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError), TestClient(app):
            pass
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
