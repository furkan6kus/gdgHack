"""Analysis pipeline orchestration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import count
from pathlib import Path

from mytool.core.analyzers.base import Analyzer, AnalyzerError
from mytool.core.analyzers.ruff import RuffAnalyzer
from mytool.core.config import Config, is_denied
from mytool.core.languages import plugin_for
from mytool.core.llm import (
    LLMClient,
    LLMError,
    LLMFindingRef,
    LLMFix,
    LLMRequest,
    number_lines,
)
from mytool.core.models import AnalysisRun, CodeUnit, Finding, Report, Severity, Suggestion
from mytool.core.parser import unit_for_line
from mytool.core.patching import PatchError, build_patch

SKIP_DIRS = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".mytool", "build", "dist"}
)
WINDOW = 15
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


@dataclass(frozen=True)
class _Group:
    unit_name: str | None
    start: int
    end: int
    findings: list[Finding]


def _unit_groups(units: list[CodeUnit], findings: list[Finding]) -> list[_Group]:
    by_unit: dict[str, list[Finding]] = defaultdict(list)
    spans: dict[str, CodeUnit] = {}
    for finding in findings:
        unit = unit_for_line(units, finding.lines.start) if finding.symbol else None
        if unit is not None:
            by_unit[unit.name].append(finding)
            spans[unit.name] = unit
    return [
        _Group(name, spans[name].lines.start, spans[name].lines.end, items)
        for name, items in by_unit.items()
    ]


def _window_groups(findings: list[Finding], total_lines: int) -> list[_Group]:
    groups: list[_Group] = []
    for finding in sorted(findings, key=lambda f: f.lines.start):
        start = max(1, finding.lines.start - WINDOW)
        end = min(total_lines, finding.lines.end + WINDOW)
        if groups and start <= groups[-1].end:
            last = groups[-1]
            groups[-1] = _Group(None, last.start, max(last.end, end), [*last.findings, finding])
        else:
            groups.append(_Group(None, start, end, [finding]))
    return groups


def _make_groups(path: Path, text_lines: list[str], findings: list[Finding]) -> list[_Group]:
    in_unit = [f for f in findings if f.symbol]
    module_level = [f for f in findings if not f.symbol]
    groups = _unit_groups(_units_for(path), in_unit) if in_unit else []
    return groups + _window_groups(module_level, len(text_lines))


def _request(path: Path, group: _Group, source: str) -> LLMRequest:
    plugin = plugin_for(path)
    return LLMRequest(
        file_name=path.name,
        language=plugin.name if plugin else "unknown",
        unit_name=group.unit_name,
        start_line=group.start,
        code=number_lines(source, group.start),
        findings=[LLMFindingRef(f.id, f.rule, f.lines.start, f.message) for f in group.findings],
    )


def _suggestion(
    ids: Iterator[int], path: Path, group: _Group, source: str, fix: LLMFix
) -> tuple[Suggestion, str | None]:
    """Build a suggestion; the second value is an error message when the patch did not match."""
    patch, error = None, None
    try:
        patch = build_patch(source, path, group.start, fix)
    except PatchError as exc:
        error = f"{path.name}: patch eşleşmedi ({exc}): {', '.join(fix.finding_ids)}"
    suggestion = Suggestion(
        id=f"sug-{next(ids)}",
        finding_ids=fix.finding_ids,
        category=fix.category,
        explanation=fix.explanation,
        patch=patch,
    )
    return suggestion, error


def _handle_group(
    run: AnalysisRun, report: Report, group: _Group, source: str, llm: LLMClient, ids: Iterator[int]
) -> None:
    response, usage = llm.suggest(_request(report.file, group, source))
    report.usage = report.usage.add(usage)
    known = {f.id for f in group.findings}
    for fix in response.fixes:
        if not fix.finding_ids or not known.issuperset(fix.finding_ids):
            run.errors.append(f"{report.file.name}: bilinmeyen bulgu kimliği, öneri atlandı")
            continue
        suggestion, error = _suggestion(ids, report.file, group, source, fix)
        report.suggestions.append(suggestion)
        if error:
            run.errors.append(error)


def _suggest_for_report(
    run: AnalysisRun, report: Report, llm: LLMClient, ids: Iterator[int]
) -> bool:
    """Returns False when a fatal LLM error means the remaining calls should be skipped."""
    text_lines = report.file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    for group in _make_groups(report.file, text_lines, report.findings):
        source = "".join(text_lines[group.start - 1 : group.end])
        try:
            _handle_group(run, report, group, source, llm, ids)
        except LLMError as exc:
            run.errors.append(f"{report.file.name}: {exc}")
            if exc.fatal:
                return False
    return True


def analyze(
    target: Path,
    cfg: Config,
    llm: LLMClient | None,
    analyzers: Sequence[Analyzer] | None = None,
) -> AnalysisRun:
    run = analyze_static(target, cfg, analyzers)
    if llm is None:
        return run
    ids = count(1)
    for report in run.reports:
        if report.findings and not _suggest_for_report(run, report, llm, ids):
            break
    return run
