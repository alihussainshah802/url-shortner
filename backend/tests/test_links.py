import re

import pytest
from fastapi.testclient import TestClient

from app.services import links as links_service
from app.services.codes import ALPHABET, generate_code


def create(client: TestClient, url: str):
    return client.post("/api/links", json={"url": url})


def test_create_returns_short_link(client: TestClient) -> None:
    res = create(client, "https://example.com/some/long/path?q=1")
    assert res.status_code == 201
    body = res.json()
    assert re.fullmatch(r"[0-9A-Za-z]{7}", body["code"])
    assert body["short_url"] == f"http://short.test/{body['code']}"
    assert body["original_url"] == "https://example.com/some/long/path?q=1"


@pytest.mark.parametrize(
    "url",
    ["", "not a url", "ftp://example.com/file", "javascript:alert(1)", "example.com"],
)
def test_create_rejects_invalid_urls(client: TestClient, url: str) -> None:
    assert create(client, url).status_code == 422


def test_create_rejects_links_to_this_service(client: TestClient) -> None:
    res = create(client, "http://short.test/abc1234")
    assert res.status_code == 422
    assert "this service" in res.json()["detail"]


def test_redirect_uses_302_and_points_at_original(client: TestClient) -> None:
    code = create(client, "https://example.com/target").json()["code"]
    res = client.get(f"/{code}")
    assert res.status_code == 302
    assert res.headers["location"] == "https://example.com/target"


def test_unknown_code_is_404(client: TestClient) -> None:
    assert client.get("/zzzzzzz").status_code == 404


def test_malformed_code_is_rejected_before_any_lookup(client: TestClient) -> None:
    assert client.get("/ab").status_code == 422


def test_collision_retries_with_a_new_code(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = create(client, "https://example.com/one").json()["code"]
    codes = iter([first, first, "FreshC0"])
    monkeypatch.setattr(links_service, "generate_code", lambda _length: next(codes))
    second = create(client, "https://example.com/two")
    assert second.status_code == 201
    assert second.json()["code"] == "FreshC0"


def test_gives_up_after_repeated_collisions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = create(client, "https://example.com/one").json()["code"]
    monkeypatch.setattr(links_service, "generate_code", lambda _length: first)
    assert create(client, "https://example.com/two").status_code == 503


def test_generate_code_uses_base62_and_requested_length() -> None:
    code = generate_code(12)
    assert len(code) == 12
    assert set(code) <= set(ALPHABET)
    assert len(ALPHABET) == 62


def test_health_still_works(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
