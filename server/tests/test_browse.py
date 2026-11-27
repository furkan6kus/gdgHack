"""Folder browsing and its secrets deny-list."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import browse

SECRETS = [".env", ".env.local", "server.pem", "id_rsa", "credentials.json", "secrets.yaml"]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    root.mkdir()
    for name in [*SECRETS, "main.py"]:
        (root / name).write_text("x")
    for name in (".ssh", ".hidden_dir", "src"):
        (root / name).mkdir()
    return root


def _names(client: TestClient, path: Path, **params: str) -> list[str]:
    response = client.get("/api/browse", params={"path": str(path), **params})
    assert response.status_code == 200
    return [e["name"] for e in response.json()["entries"]]


def test_listing_hides_secrets_and_hidden(client: TestClient, tree: Path) -> None:
    assert _names(client, tree) == ["src", "main.py"]


def test_show_hidden_still_hides_secrets(client: TestClient, tree: Path) -> None:
    names = _names(client, tree, show_hidden="true")
    assert names == [".hidden_dir", "src", "main.py"]


def test_browse_denied_dir(client: TestClient, tree: Path) -> None:
    response = client.get("/api/browse", params={"path": str(tree / ".ssh")})
    assert response.status_code == 403
    assert response.json()["code"] == "path_denied"


def test_parent_field(client: TestClient, tree: Path) -> None:
    body = client.get("/api/browse", params={"path": str(tree / "src")}).json()
    assert body["parent"] == str(tree.resolve())
    assert body["path"] == str((tree / "src").resolve())


def test_root_has_no_parent(client: TestClient) -> None:
    assert client.get("/api/browse", params={"path": "/"}).json()["parent"] is None


@pytest.mark.parametrize("name", ["PROD.KEY", ".ENV", "Id_RSA.pub", "Credentials.JSON", ".SSH"])
def test_is_denied_case_insensitive(name: str) -> None:
    assert browse.is_denied(name)


@pytest.mark.parametrize("name", ["main.py", "src", "environment.py", "keyboard.txt"])
def test_is_denied_allows_normal_names(name: str) -> None:
    assert not browse.is_denied(name)


def test_browse_file_lists_its_folder(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("x = 1\n")
    response = client.get("/api/browse", params={"path": str(tmp_path / "main.py")})
    assert response.status_code == 200
    assert response.json()["path"] == str(tmp_path.resolve())


def test_places_include_home(client: TestClient) -> None:
    response = client.get("/api/places")
    assert response.status_code == 200
    places = response.json()
    assert places[0] == {"name": "Ev", "path": str(Path.home()), "kind": "home"}
    assert all(p["kind"] in {"home", "folder", "drive"} for p in places)


def test_places_follow_moved_xdg_download_dir(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moved = tmp_path / "elsewhere" / "İndirilenler"
    moved.mkdir(parents=True)
    (tmp_path / "user-dirs.dirs").write_text(f'XDG_DOWNLOAD_DIR="{moved}"\n', encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    by_name = {p["name"]: p["path"] for p in client.get("/api/places").json()}
    assert by_name["İndirilenler"] == str(moved)
