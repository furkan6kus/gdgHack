"""Adapter backed by the real core pipeline (``mytool.core``).

Core models are converted into the UI contract here. The core run of every
analysis is kept in memory (bounded) so ``apply`` can hand the core its own
``Report`` objects, including the content hashes that detect files edited
after the analysis.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from mytool.core import models as core
from mytool.core.apply import apply_suggestions, fix_eligible
from mytool.core.config import Config, load_config
from mytool.core.llm import AnthropicLLM, LLMClient
from mytool.core.pipeline import Cancelled, analyze
from mytool.core.verify import find_project_root

from server.adapters.base import ApplyOutcome, ProgressCallback
from server.contracts import (
    AnalyzeResult,
    FileSummary,
    Finding,
    Patch,
    ProgressEvent,
    SeverityCounts,
    Suggestion,
    TokenUsage,
    VerificationResult,
)
from server.errors import API_KEY_MISSING, CANCELLED, AdapterError

log = logging.getLogger(__name__)

LLMFactory = Callable[[Config], LLMClient]

MAX_RUNS = 20  # same bound as the job store
ANALYSIS_FAILED = "analysis_failed"
APPLY_FAILED = "apply_failed"


class CoreAdapter:
    name = "core"

    def __init__(self, llm_factory: LLMFactory = AnthropicLLM) -> None:
        self._llm_factory = llm_factory
        self._runs: OrderedDict[str, core.AnalysisRun] = OrderedDict()
        self._lock = threading.Lock()

    def api_key_configured(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

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
        cfg = load_config(verify=verify)

        def forward(event: core.ProgressEvent) -> None:
            on_progress(ProgressEvent.model_validate(event.model_dump(mode="json")))

        try:
            run = analyze(
                root,
                cfg,
                self._llm_factory(cfg),
                on_progress=forward,
                should_cancel=cancel.is_set,
            )
        except Cancelled as exc:
            raise AdapterError(CANCELLED, "Analiz iptal edildi.") from exc
        for warning in run.warnings:
            log.warning("analyze %s: %s", root, warning)
        if run.errors:
            raise AdapterError(ANALYSIS_FAILED, " · ".join(run.errors), status_code=500)
        token = uuid.uuid4().hex[:8]
        self._remember(token, run)
        return to_ui_result(root, run, token)

    def apply(self, root: Path, suggestions: list[Suggestion]) -> ApplyOutcome:
        token = _token_of(suggestions)
        with self._lock:
            run = self._runs.get(token) if token else None
        if run is None:
            raise AdapterError(APPLY_FAILED, "Analiz sonucu bulunamadı; yeniden analiz edin.", 409)
        wanted = {_core_id(s.id) for s in suggestions}
        eligible = {s.id for r in run.reports for s in r.suggestions if fix_eligible(s)}
        if not wanted <= eligible:  # the server already checks; core re-checks
            raise AdapterError(APPLY_FAILED, "Yalnızca testleri geçen öneriler uygulanabilir.")
        project = find_project_root(root / "x" if root.is_dir() else root)
        result = apply_suggestions(run.reports, wanted, project / ".mytool" / "backup")
        applied = [o for o in result.outcomes if o.applied]
        if not applied:
            reasons = "; ".join(f"{o.file.name}: {o.reason}" for o in result.skipped)
            raise AdapterError(APPLY_FAILED, f"Hiçbir öneri uygulanamadı: {reasons}", 409)
        base = _base_dir(root)
        return ApplyOutcome(
            applied_ids=[f"{token}-{o.suggestion_id}" for o in applied],
            changed_files=sorted({_rel(o.file, base) for o in applied}),
            backup_path=str(result.backup_dir or ""),
        )

    def _remember(self, token: str, run: core.AnalysisRun) -> None:
        with self._lock:
            self._runs[token] = run
            while len(self._runs) > MAX_RUNS:
                self._runs.popitem(last=False)


# --------------------------------------------------------------------------- conversion


def to_ui_result(root: Path, run: core.AnalysisRun, token: str) -> AnalyzeResult:
    base = _base_dir(root)
    findings = [_finding(f, base) for r in run.reports for f in r.findings]
    suggestions = [
        _suggestion(s, token, base)
        for r in run.reports
        for s in r.suggestions
        if s.patch is not None
    ]
    usage = run.usage
    return AnalyzeResult(
        root=str(root),
        files=[_file_summary(r, base) for r in run.reports],
        findings=findings,
        suggestions=suggestions,
        token_usage=TokenUsage(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens),
    )


def _finding(f: core.Finding, base: Path) -> Finding:
    return Finding(
        id=f.id,
        tool=f.tool,
        file=_rel(f.file, base),
        line_start=f.lines.start,
        line_end=f.lines.end,
        severity=f.severity.value,
        rule_code=f.rule,
        message=f.message,
    )


def _suggestion(s: core.Suggestion, token: str, base: Path) -> Suggestion:
    assert s.patch is not None
    return Suggestion(
        id=f"{token}-{s.id}",
        finding_ids=s.finding_ids,
        category=s.category.value,
        explanation=s.explanation,
        patch=Patch(
            file=_rel(s.patch.file, base), original_text=s.patch.original, new_text=s.patch.new
        ),
        verification=_verification(s),
    )


def _verification(s: core.Suggestion) -> VerificationResult:
    """Only test-backed passes count as ``passed``; a syntax-only check is ``skipped``."""
    v = s.verification
    if v is None:
        return VerificationResult(status="skipped", detail="Doğrulanmadı.", duration_ms=0)
    ms = round(v.duration_s * 1000)
    if v.status == core.VerifyStatus.FAILED:
        return VerificationResult(status="failed", detail=v.detail, duration_ms=ms)
    if fix_eligible(s):
        return VerificationResult(
            status="passed", detail=v.detail or "Testler geçti.", duration_ms=ms
        )
    if v.method == core.VerifyMethod.SYNTAX:
        detail = "Doğrulanamadı: yalnız sözdizimi denetlendi"
        return VerificationResult(
            status="skipped",
            detail=f"{detail} ({v.detail})." if v.detail else f"{detail}.",
            duration_ms=ms,
        )
    if v.detail == "--no-verify":
        return VerificationResult(
            status="skipped", detail="Doğrulama kullanıcı tarafından kapatıldı.", duration_ms=0
        )
    return VerificationResult(status="skipped", detail=v.detail or "Doğrulanmadı.", duration_ms=ms)


def _file_summary(report: core.Report, base: Path) -> FileSummary:
    counts = SeverityCounts()
    for f in report.findings:
        setattr(counts, f.severity.value, getattr(counts, f.severity.value) + 1)
    try:
        line_count = len(report.file.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        line_count = 0
    return FileSummary(path=_rel(report.file, base), line_count=line_count, counts=counts)


def _base_dir(root: Path) -> Path:
    """Paths shown in the UI are relative to the analyzed folder (or a file's folder)."""
    return (root if root.is_dir() else root.parent).resolve()


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _token_of(suggestions: list[Suggestion]) -> str | None:
    tokens = {s.id.split("-", 1)[0] for s in suggestions}
    return tokens.pop() if len(tokens) == 1 else None


def _core_id(ui_id: str) -> str:
    return ui_id.split("-", 1)[1] if "-" in ui_id else ui_id
