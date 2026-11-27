"""Analysis pipeline orchestration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from mytool.core.analyzers.base import Analyzer, AnalyzerError
from mytool.core.analyzers.ruff import RuffAnalyzer
from mytool.core.config import Config, is_denied
from mytool.core.languages import plugin_for
from mytool.core.models import AnalysisRun, CodeUnit, Finding, Report, Severity
from mytool.core.parser import unit_for_line

SKIP_DIRS = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".mytool", "build", "dist"}
)
_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def _candidates(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    found: list[Path] = []
    for path in target.rglob("*"):
        rel_dirs = path.relative_to(target).parts[:-1]
        if path.is_file() and not SKIP_DIRS.intersection(rel_dirs):
            found.append(path)
    return found


def collect_files(target: Path, cfg: Config) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    skipped: list[str] = []
    for path in sorted(_candidates(target)):
        if plugin_for(path) is None:
            continue
        if is_denied(path, cfg.deny_patterns):
            skipped.append(f"{path}: deny-list")
        else:
            files.append(path)
    return files, skipped


def _units_for(path: Path) -> list[CodeUnit]:
    plugin = plugin_for(path)
    if plugin is None:
        return []
    return plugin.extract_units(path.read_text(encoding="utf-8", errors="replace"))


def _run_analyzers(
    analyzers: Sequence[Analyzer], files: list[Path], timeout_s: float
) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    errors: list[str] = []
    for analyzer in analyzers:
        try:
            findings.extend(analyzer.run(files, timeout_s))
        except AnalyzerError as exc:
            errors.append(f"{analyzer.name}: {exc}")
    return findings, errors


def _cap(findings: list[Finding], limit: int) -> tuple[list[Finding], int]:
    ordered = sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER[f.severity], str(f.file), f.lines.start, f.column or 0),
    )
    return ordered[:limit], max(0, len(ordered) - limit)


def _group_by_file(findings: list[Finding], files: list[Path]) -> dict[Path, list[Finding]]:
    resolved = {f.resolve(): f for f in files}
    groups: dict[Path, list[Finding]] = defaultdict(list)
    for finding in findings:
        original = resolved.get(finding.file.resolve())
        if original is not None:
            groups[original].append(finding)
    return groups


def _with_symbols(path: Path, findings: list[Finding]) -> list[Finding]:
    units = _units_for(path) if findings else []
    result: list[Finding] = []
    for finding in sorted(findings, key=lambda f: (f.lines.start, f.column or 0)):
        unit = unit_for_line(units, finding.lines.start)
        result.append(finding.model_copy(update={"symbol": unit.name if unit else None}))
    return result


def analyze_static(
    target: Path, cfg: Config, analyzers: Sequence[Analyzer] | None = None
) -> AnalysisRun:
    files, skipped = collect_files(target, cfg)
    findings, errors = _run_analyzers(
        analyzers if analyzers is not None else [RuffAnalyzer()],
        files,
        float(cfg.subprocess_timeout_s),
    )
    kept, hidden = _cap(findings, cfg.max_findings)
    groups = _group_by_file(kept, files)
    reports = [Report(file=p, findings=_with_symbols(p, groups.get(p, []))) for p in files]
    return AnalysisRun(reports=reports, errors=errors, skipped=skipped, truncated=hidden)
