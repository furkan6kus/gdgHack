"""Change history (apply -> record -> undo) and Telegram message texts."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.contracts import AnalyzeResult, Finding, Severity, TokenUsage
from server.history import HistoryStore
from server.notify import TelegramNotifier, error_message, result_message
from server.schemas import ErrorPayload
from server.tests.conftest import result_of, run_job
from server.tests.test_core_adapter import _adapter, _project


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@contextmanager
def _applied_once(tmp_path: Path) -> Iterator[tuple[TestClient, Path, dict[str, Any]]]:
    """A running app where one suggestion of a fresh project has been applied."""
    root = _project(tmp_path / "p")
    history = HistoryStore(tmp_path / "h.json")
    app = create_app(_adapter(), dist_dir=tmp_path / "no-dist", history=history)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        job_id, events = run_job(client, root)
        (sug,) = result_of(events)["suggestions"]
        body = {"job_id": job_id, "suggestion_ids": [sug["id"]]}
        response = client.post("/api/apply", json=body)
        assert response.status_code == 200, response.text
        yield client, root, response.json()


def test_apply_is_recorded_and_can_be_undone(tmp_path: Path) -> None:
    original = "import os\n\n\ndef add(a, b):\n    return a + b\n"
    with _applied_once(tmp_path) as (client, root, applied):
        (entry,) = client.get("/api/history").json()
        assert entry["id"] == applied["history_id"]
        (change,) = entry["files"]
        assert change["name"] == "calc.py"
        assert change["before"] == original
        assert change["after"] == (root / "calc.py").read_text()
        assert entry["explanations"] == ["Kullanılmayan import."]

        undone = client.post(f"/api/history/{entry['id']}/undo", json={})
        assert undone.status_code == 200 and undone.json()["undone"] is True
        assert (root / "calc.py").read_text() == original
        again = client.post(f"/api/history/{entry['id']}/undo", json={})
        assert again.json()["code"] == "already_undone"


def test_undo_refuses_after_manual_edit(tmp_path: Path) -> None:
    with _applied_once(tmp_path) as (client, root, applied):
        (root / "calc.py").write_text("# elle düzenlendi\n")
        response = client.post(f"/api/history/{applied['history_id']}/undo", json={})
    assert response.status_code == 409
    assert response.json()["code"] == "file_changed"
    assert (root / "calc.py").read_text() == "# elle düzenlendi\n"


def test_history_survives_restart(tmp_path: Path) -> None:
    with _applied_once(tmp_path):
        pass
    assert len(HistoryStore(tmp_path / "h.json").entries()) == 1


def test_health_reports_telegram(tmp_path: Path) -> None:
    app = create_app(
        _adapter(),
        dist_dir=tmp_path / "no-dist",
        notifier=TelegramNotifier(token="t", chat_id="c"),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").json()["telegram_configured"] is True


def test_notify_test_needs_configuration(client: TestClient) -> None:
    response = client.post("/api/notify/test", json={})
    assert response.json()["code"] == "telegram_not_configured"


def _finding(line: int, severity: Severity, message: str) -> Finding:
    return Finding(
        id=f"f{line}",
        tool="ruff",
        file="sepet.py",
        line_start=line,
        line_end=line,
        severity=severity,
        rule_code="X",
        message=message,
    )


def test_result_message_is_short_and_worst_first() -> None:
    result = AnalyzeResult(
        root="C:/p/sepet.py",
        files=[],
        findings=[
            _finding(20, "warning", "`os` içe aktarılmış ama kullanılmıyor"),
            _finding(16, "error", "Girinti hiçbir üst satırın girintisiyle eşleşmiyor"),
        ],
        suggestions=[],
        token_usage=TokenUsage(),
    )
    assert result_message(Path("C:/p/sepet.py"), result) == (
        "🔴 sepet.py hazır: 1 ciddi hata, 1 küçük sorun\n"
        "• Satır 16: Girinti hiçbir üst satırın girintisiyle eşleşmiyor\n"
        "• Satır 20: 'os' içe aktarılmış ama kullanılmıyor"
    )


def test_only_minor_findings() -> None:
    result = AnalyzeResult(
        root="r",
        files=[],
        findings=[_finding(1, "warning", "x")],
        suggestions=[],
        token_usage=TokenUsage(),
    )
    assert result_message(Path("calc.py"), result).startswith(
        "🟡 calc.py hazır: 1 küçük sorun, ciddi hata yok"
    )


def test_long_lists_are_cut() -> None:
    findings = [_finding(i, "error", "Uzun " * 40) for i in range(1, 6)]
    result = AnalyzeResult(
        root="r", files=[], findings=findings, suggestions=[], token_usage=TokenUsage()
    )
    lines = result_message(Path("a.py"), result).splitlines()
    assert len(lines) == 5  # header, 3 findings, "…ve 2 sorun daha"
    assert lines[-1] == "…ve 2 sorun daha"
    assert all(len(line) < 110 for line in lines)


def test_clean_and_error_messages() -> None:
    clean = AnalyzeResult(root="r", files=[], findings=[], suggestions=[], token_usage=TokenUsage())
    assert result_message(Path("proje"), clean) == "✅ proje hazır: sorun bulunmadı."
    error = ErrorPayload(code="analysis_failed", message="API anahtarı geçersiz")
    assert error_message(Path("proje"), error) == "⚠️ proje analiz edilemedi: API anahtarı geçersiz"


def test_notifier_unconfigured_sends_nothing() -> None:
    import asyncio

    assert asyncio.run(TelegramNotifier(token="", chat_id="").send("x")) is False


def test_job_finish_triggers_notification(tmp_path: Path) -> None:
    sent: list[str] = []
    done = threading.Event()

    class Recorder(TelegramNotifier):
        async def send(self, text: str) -> bool:
            sent.append(text)
            done.set()
            return True

    root = _project(tmp_path / "p")
    app = create_app(
        _adapter(), dist_dir=tmp_path / "no-dist", notifier=Recorder(token="t", chat_id="c")
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        run_job(client, root)
        assert done.wait(5)
    assert sent[0].startswith("🟡 p hazır:")


def test_applied_message() -> None:
    from server.notify import applied_message

    text = applied_message(Path("C:/p/hesap"), ["calc.py"], 1, "`os` kaldırıldı.")
    assert text == "🛠 calc.py: 1 düzeltme uygulandı.\n'os' kaldırıldı."
