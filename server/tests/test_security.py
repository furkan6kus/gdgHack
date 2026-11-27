"""Host allow-list and CORS."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _preflight(client: TestClient, origin: str) -> dict[str, str]:
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return dict(response.headers)


def test_foreign_host_rejected(client: TestClient) -> None:
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


def test_cors_allows_vite_origin(client: TestClient) -> None:
    headers = _preflight(client, "http://127.0.0.1:5173")
    assert headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_cors_rejects_other_origin(client: TestClient) -> None:
    assert "access-control-allow-origin" not in _preflight(client, "http://evil.example")
