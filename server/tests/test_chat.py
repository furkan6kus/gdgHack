"""Chat with Claude about a file: answers, proposed edits, checks and apply."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from mytool.core.llm import T
from mytool.core.models import TokenUsage

from server.app import create_app
from server.chat import _ModelAnswer, _ModelEdit
from server.history import HistoryStore
from server.tests.test_core_adapter import _adapter


class FakeChatLLM:
    def __init__(self, answer: _ModelAnswer) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def structured(self, system: str, prompt: str, schema: type[T]) -> tuple[T, TokenUsage]:
        self.prompts.append(prompt)
        return cast(T, self.answer), TokenUsage(input_tokens=100, output_tokens=20)


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def _client(tmp_path: Path, answer: _ModelAnswer) -> tuple[TestClient, FakeChatLLM, Path]:
    root = tmp_path / "p"
    root.mkdir()
    (root / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    fake = FakeChatLLM(answer)
    app = create_app(
        _adapter(),
        dist_dir=tmp_path / "no-dist",
        history=HistoryStore(tmp_path / "h.json"),
        chat_llm=lambda cfg: fake,
    )
    return TestClient(app, base_url="http://127.0.0.1"), fake, root


ADD_SUB = _ModelAnswer(
    reply="Çıkarma fonksiyonu ekledim.",
    edits=[
        _ModelEdit(
            original="    return a + b\n",
            replacement="    return a + b\n\n\ndef sub(a, b):\n    return a - b\n",
            explanation="sub fonksiyonu eklendi.",
        )
    ],
)


def _ask(client: TestClient, root: Path, text: str) -> dict[str, Any]:
    body = {"path": str(root), "file": "calc.py", "messages": [{"role": "user", "content": text}]}
    response = client.post("/api/chat", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_chat_proposes_checked_edit_and_apply_records_history(tmp_path: Path) -> None:
    client, fake, root = _client(tmp_path, ADD_SUB)
    with client:
        answer = _ask(client, root, "çıkarma fonksiyonu ekle")
        assert answer["reply"] == "Çıkarma fonksiyonu ekledim."
        (edit,) = answer["edits"]
        assert edit["applicable"] is True
        assert "1 | def add(a, b):" in fake.prompts[0]
        assert "Kullanıcı: çıkarma fonksiyonu ekle" in fake.prompts[0]

        body = {k: edit[k] for k in ("file", "original", "replacement", "explanation")}
        applied = client.post("/api/chat/apply", json={"path": str(root), **body})
        assert applied.status_code == 200, applied.text
        assert "def sub(a, b)" in (root / "calc.py").read_text()
        (entry,) = client.get("/api/history").json()
        assert entry["explanations"] == ["sub fonksiyonu eklendi."]


def test_edit_that_breaks_syntax_is_not_applicable(tmp_path: Path) -> None:
    broken = _ModelAnswer(
        reply="x",
        edits=[
            _ModelEdit(
                original="    return a + b\n", replacement="    return a +\n", explanation=""
            )
        ],
    )
    client, _, root = _client(tmp_path, broken)
    with client:
        (edit,) = _ask(client, root, "boz")["edits"]
        assert edit["applicable"] is False
        assert "derlenmiyor" in edit["problem"]
        body = {k: edit[k] for k in ("file", "original", "replacement", "explanation")}
        response = client.post("/api/chat/apply", json={"path": str(root), **body})
    assert response.status_code == 409
    assert (root / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"


def test_file_outside_root_is_refused(tmp_path: Path) -> None:
    client, _, root = _client(tmp_path, ADD_SUB)
    (tmp_path / "secret.py").write_text("x = 1\n")
    body = {
        "path": str(root),
        "file": "../secret.py",
        "messages": [{"role": "user", "content": "?"}],
    }
    with client:
        response = client.post("/api/chat", json=body)
    assert response.status_code == 403


def test_chat_needs_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    client, _, root = _client(tmp_path, ADD_SUB)
    body = {"path": str(root), "file": "calc.py", "messages": [{"role": "user", "content": "?"}]}
    with client:
        response = client.post("/api/chat", json=body)
    assert response.json()["code"] == "api_key_missing"
