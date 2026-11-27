from pathlib import Path

from fastapi.testclient import TestClient

from server.adapters.mock import MockAdapter
from server.app import create_app
from .conftest import ClientFactory


def test_missing_build_serves_instructions(make_client: ClientFactory) -> None:
    response = make_client().get("/")
    assert response.status_code == 200
    assert "npm run build" in response.text


def test_built_frontend_is_served(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>built</title>")
    app = create_app(MockAdapter(delay_scale=0), dist_dir=tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "built" in response.text
        assert client.get("/api/health").status_code == 200
