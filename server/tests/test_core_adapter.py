"""CoreAdapter against the real core pipeline (real ruff + pytest, fake LLM)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from mytool.core.config import Config
from mytool.core.llm import LLMError, LLMFix, LLMUnitResponse, T
from mytool.core.models import Category, TokenUsage

from server.adapters.core_adapter import CoreAdapter
from server.app import create_app
from server.contracts import ProgressEvent
from server.errors import AdapterError
from server.tests.conftest import result_of, run_job


class FakeLLM:
    """Removes the line the finding points at (`import os`)."""

    def __init__(self, error: LLMError | None = None) -> None:
        self.error = error
        self.calls = 0

    def structured(self, system: str, prompt: str, schema: type[T]) -> tuple[T, TokenUsage]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if "import os" not in prompt:
            return cast(T, LLMUnitResponse(fixes=[])), TokenUsage()
        finding_id = prompt.split("- id=", 1)[1].split()[0]
        fix = LLMFix(
            finding_ids=[finding_id],
            category=Category.BUG,
            explanation="Kullanılmayan import.",
            original="import os\n",
            replacement="",
        )
        return cast(T, LLMUnitResponse(fixes=[fix])), TokenUsage(input_tokens=7, output_tokens=3)


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def _project(root: Path, *, with_tests: bool = True) -> Path:
    root.mkdir()
    (root / "calc.py").write_text("import os\n\n\ndef add(a, b):\n    return a + b\n")
    if with_tests:
        (root / "test_calc.py").write_text(
            "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
        )
    return root


def _adapter(llm: Any = None) -> CoreAdapter:
    fake = llm or FakeLLM()
    return CoreAdapter(llm_factory=lambda cfg: fake)


def _analyze(adapter: CoreAdapter, root: Path, *, verify: bool = True) -> Any:
    events: list[ProgressEvent] = []
    result = adapter.analyze(
        root, verify=verify, on_progress=events.append, cancel=threading.Event()
    )
    return result, events


def test_findings_and_passed_suggestion(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    result, events = _analyze(_adapter(), root)
    (finding,) = [f for f in result.findings if f.rule_code == "F401"]
    assert finding.file == "calc.py"
    assert (finding.line_start, finding.severity) == (1, "warning")
    (sug,) = result.suggestions
    assert sug.finding_ids == [finding.id]
    assert sug.patch.file == "calc.py"
    assert sug.verification.status == "passed"
    assert result.token_usage.input_tokens == 7
    assert {e.stage for e in events} >= {"parsing", "static_analysis", "llm", "verify", "done"}
    assert result.sources == {"calc.py": "import os\n\n\ndef add(a, b):\n    return a + b\n"}


def test_syntax_only_verification_is_applicable_but_untested(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", with_tests=False)
    result, _ = _analyze(_adapter(), root)
    (sug,) = result.suggestions
    assert sug.verification.status == "passed"
    assert sug.verification.tested is False
    assert "Testle doğrulanmadı" in sug.verification.detail


def test_tested_pass_is_marked_tested(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    result, _ = _analyze(_adapter(), root)
    assert result.suggestions[0].verification.tested is True


def test_untested_suggestion_can_be_applied(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", with_tests=False)
    adapter = _adapter()
    result, _ = _analyze(adapter, root)
    outcome = adapter.apply(root, result.suggestions)
    assert outcome.changed_files == ["calc.py"]
    assert not (root / "calc.py").read_text().startswith("import os")


def test_no_verify_marks_skipped(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    result, events = _analyze(_adapter(), root, verify=False)
    assert result.suggestions[0].verification.status == "skipped"
    assert "verify" not in {e.stage for e in events}


def test_cancel_maps_to_cancelled(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(AdapterError) as info:
        _adapter().analyze(root, verify=True, on_progress=lambda e: None, cancel=cancel)
    assert info.value.code == "cancelled"


def test_fatal_llm_error_is_user_facing(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    llm = FakeLLM(LLMError("API anahtarı geçersiz (ANTHROPIC_API_KEY)", fatal=True))
    with pytest.raises(AdapterError) as info:
        _analyze(_adapter(llm), root)
    assert info.value.code == "analysis_failed"
    assert "API anahtarı geçersiz" in info.value.message


def test_missing_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    root = _project(tmp_path / "p")
    with pytest.raises(AdapterError) as info:
        _analyze(_adapter(), root)
    assert info.value.code == "api_key_missing"


def test_end_to_end_apply_writes_file_and_backup(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    app = create_app(_adapter(), dist_dir=tmp_path / "no-dist")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        job_id, events = run_job(client, root)
        (sug,) = result_of(events)["suggestions"]
        response = client.post("/api/apply", json={"job_id": job_id, "suggestion_ids": [sug["id"]]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["applied_ids"] == [sug["id"]]
    assert body["changed_files"] == ["calc.py"]
    assert (root / "calc.py").read_text().startswith("\n\ndef add")
    backups = list((root / ".mytool" / "backup").rglob("calc.py"))
    assert [b.read_text() for b in backups] == ["import os\n\n\ndef add(a, b):\n    return a + b\n"]


def test_apply_refuses_file_changed_after_analysis(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    adapter = _adapter()
    result, _ = _analyze(adapter, root)
    (root / "calc.py").write_text("import os\n# edited\n")
    with pytest.raises(AdapterError) as info:
        adapter.apply(root, result.suggestions)
    assert info.value.code == "apply_failed"
    assert "değişti" in info.value.message


def test_verify_flag_reaches_core_config(tmp_path: Path) -> None:
    seen: list[Config] = []

    def factory(cfg: Config) -> FakeLLM:
        seen.append(cfg)
        return FakeLLM()

    adapter = CoreAdapter(llm_factory=factory)
    _analyze(adapter, _project(tmp_path / "p"), verify=False)
    assert seen[0].verify is False


def test_llm_choice_reaches_core_config(tmp_path: Path) -> None:
    from server.contracts import LLMChoice

    seen: list[Config] = []

    def factory(cfg: Config) -> FakeLLM:
        seen.append(cfg)
        return FakeLLM()

    CoreAdapter(llm_factory=factory).analyze(
        _project(tmp_path / "p"),
        verify=False,
        on_progress=lambda e: None,
        cancel=threading.Event(),
        llm=LLMChoice(model="claude-opus-5-5", effort="high"),
    )
    assert (seen[0].model, seen[0].effort) == ("claude-opus-5-5", "high")
