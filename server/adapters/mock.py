"""Mock adapter: realistic fake data with artificial delays so progress is visible.

Environment knobs (for demos and screenshots):
- ``MYTOOL_UI_MOCK_SCENARIO``: ok (default) | empty | error | no_key
- ``MYTOOL_UI_MOCK_DELAY``: delay multiplier, e.g. 0 for instant, 2 for slow
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Literal, get_args

from server.adapters import mock_data
from server.adapters.base import ApplyOutcome, ProgressCallback
from server.contracts import (
    AnalyzeResult,
    Finding,
    ProgressEvent,
    Stage,
    Suggestion,
    TokenUsage,
    VerificationResult,
)
from server.errors import API_KEY_MISSING, CANCELLED, AdapterError

Scenario = Literal["ok", "empty", "error", "no_key"]

_STEP_SECONDS = 0.22


class MockAdapter:
    name = "mock"

    def __init__(self, scenario: Scenario = "ok", delay_scale: float = 1.0) -> None:
        self.scenario: Scenario = scenario
        self.delay_scale = delay_scale

    @classmethod
    def from_env(cls) -> MockAdapter:
        raw = os.environ.get("MYTOOL_UI_MOCK_SCENARIO", "ok")
        scenario: Scenario = raw if raw in get_args(Scenario) else "ok"  # type: ignore[assignment]
        delay = float(os.environ.get("MYTOOL_UI_MOCK_DELAY", "1"))
        return cls(scenario=scenario, delay_scale=delay)

    def api_key_configured(self) -> bool:
        return self.scenario != "no_key"

    def analyze(
        self,
        root: Path,
        *,
        verify: bool,
        on_progress: ProgressCallback,
        cancel: threading.Event,
    ) -> AnalyzeResult:
        if not self.api_key_configured():
            raise AdapterError(API_KEY_MISSING, "ANTHROPIC_API_KEY tanımlı değil.")
        run = _MockRun(self, on_progress, cancel)
        run.parse()
        findings = run.static_analysis()
        suggestions = run.llm(findings)
        suggestions = run.verify(suggestions) if verify else _mark_unverified(suggestions)
        run.emit("done", "Analiz tamamlandı")
        return AnalyzeResult(
            root=str(root),
            files=mock_data.file_summaries(findings),
            findings=findings,
            suggestions=suggestions,
            token_usage=_token_usage(len(suggestions)),
        )

    def apply(self, root: Path, suggestions: list[Suggestion]) -> ApplyOutcome:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return ApplyOutcome(
            applied_ids=[s.id for s in suggestions],
            changed_files=sorted({s.patch.file for s in suggestions}),
            backup_path=str(root / ".mytool" / "backup" / stamp),
        )


class _MockRun:
    """One analysis run; keeps progress/cancel plumbing out of the data flow."""

    def __init__(
        self, adapter: MockAdapter, on_progress: ProgressCallback, cancel: threading.Event
    ) -> None:
        self.adapter = adapter
        self.on_progress = on_progress
        self.cancel = cancel

    def emit(
        self, stage: Stage, message: str, current: int | None = None, total: int | None = None
    ) -> None:
        if self.cancel.is_set():
            raise AdapterError(CANCELLED, "Analiz iptal edildi.")
        self.on_progress(ProgressEvent(stage=stage, message=message, current=current, total=total))
        time.sleep(_STEP_SECONDS * self.adapter.delay_scale)

    def parse(self) -> None:
        total = len(mock_data.FILES)
        for i, (path, _) in enumerate(mock_data.FILES, start=1):
            self.emit("parsing", f"{path} ayrıştırılıyor", i, total)

    def static_analysis(self) -> list[Finding]:
        self.emit("static_analysis", "ruff check çalıştırılıyor")
        if self.adapter.scenario == "error":
            raise AdapterError(
                "analyzer_failed",
                "ruff çalıştırılamadı: komut bulunamadı. `pip install ruff` ile kurabilirsiniz.",
            )
        findings = [] if self.adapter.scenario == "empty" else list(mock_data.FINDINGS)
        self.emit("static_analysis", f"{len(findings)} bulgu bulundu")
        return findings

    def llm(self, findings: list[Finding]) -> list[Suggestion]:
        wanted = {f.id for f in findings}
        suggestions = [s for s in mock_data.SUGGESTIONS if wanted.issuperset(s.finding_ids)]
        rules = {f.id: f.rule_code for f in findings}
        for i, s in enumerate(suggestions, start=1):
            rule = rules[s.finding_ids[0]]
            self.emit("llm", f"{rule} için açıklama ve yama hazırlanıyor", i, len(suggestions))
        return suggestions

    def verify(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        for i, s in enumerate(suggestions, start=1):
            self.emit("verify", f"{s.patch.file} geçici kopyada doğrulanıyor", i, len(suggestions))
        return suggestions


def _mark_unverified(suggestions: list[Suggestion]) -> list[Suggestion]:
    skipped = VerificationResult(
        status="skipped", detail="Doğrulama kullanıcı tarafından kapatıldı.", duration_ms=0
    )
    return [s.model_copy(update={"verification": skipped}) for s in suggestions]


def _token_usage(n_suggestions: int) -> TokenUsage:
    return TokenUsage(input_tokens=1840 * n_suggestions, output_tokens=410 * n_suggestions)
