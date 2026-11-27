"""Analysis pipeline orchestration."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from itertools import count
from pathlib import Path

from mytool.core.analyzers.base import Analyzer, AnalyzerError
from mytool.core.analyzers.ruff import RuffAnalyzer
from mytool.core.config import Config, is_denied
from mytool.core.languages import plugin_for
from mytool.core.languages.base import LanguagePlugin
from mytool.core.llm import (
    LLMClient,
    LLMError,
    LLMFindingRef,
    LLMFix,
    LLMRequest,
    LLMUnitResponse,
    number_lines,
)
from mytool.core.models import (
    AnalysisRun,
    Category,
    CodeUnit,
    ExplainResult,
    FileExplanation,
    Finding,
    ProfileEntry,
    Report,
    Severity,
    Suggestion,
    UnitExplanation,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.parser import unit_for_line
from mytool.core.patching import PatchError, build_patch
from mytool.core.profiling import Workload, WorkloadError, hot_units, measure, profile
from mytool.core.prompts import (
    EXPLAIN_SYSTEM,
    FIX_SYSTEM,
    OPTIMIZE_SYSTEM,
    build_explain_prompt,
    build_fix_prompt,
    build_optimize_prompt,
    build_summary_prompt,
    build_unit_prompt,
)
from mytool.core.verify import (
    Workspace,
    find_project_root,
    tests_usable,
    verify_optimization,
    verify_patch,
)

SKIP_DIRS = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".mytool", "build", "dist"}
)
WINDOW = 15
EXPLAIN_WHOLE_FILE_LINES = 400
NO_PROFILE_DATA = "profil verisi yok: --bench ile bir benchmark betiği ver"
_MAIN_GUARD = re.compile(r"^if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", re.MULTILINE)
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
    reports = [
        Report(
            file=p,
            findings=_with_symbols(p, groups.get(p, [])),
            content_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        for p in files
    ]
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
        error = f"{path.name}: patch eşleşmedi ({exc})"
        if fix.finding_ids:
            error += f": {', '.join(fix.finding_ids)}"
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
    prompt = build_fix_prompt(_request(report.file, group, source))
    response, usage = llm.structured(FIX_SYSTEM, prompt, LLMUnitResponse)
    report.usage = report.usage.add(usage)
    known = {f.id for f in group.findings}
    for fix in response.fixes:
        if not fix.finding_ids or not known.issuperset(fix.finding_ids):
            run.warnings.append(f"{report.file.name}: bilinmeyen bulgu kimliği, öneri atlandı")
            continue
        suggestion, error = _suggestion(ids, report.file, group, source, fix)
        report.suggestions.append(suggestion)
        if error:
            run.warnings.append(error)


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
            (run.errors if exc.fatal else run.warnings).append(f"{report.file.name}: {exc}")
            if exc.fatal:
                return False
    return True


def _verify_one(
    run: AnalysisRun,
    stack: ExitStack,
    workspaces: dict[Path, Workspace],
    cfg: Config,
    suggestion: Suggestion,
) -> VerificationResult:
    patch = suggestion.patch
    plugin = plugin_for(patch.file) if patch else None
    if patch is None or plugin is None:
        return VerificationResult(
            status=VerifyStatus.SKIPPED, method=VerifyMethod.NONE, detail="dil desteklenmiyor"
        )
    try:
        root = find_project_root(patch.file)
        if root not in workspaces:
            workspaces[root] = stack.enter_context(Workspace(root))
        return verify_patch(workspaces[root], patch, plugin, cfg)
    except OSError as exc:
        run.warnings.append(f"{patch.file.name}: doğrulama altyapısı hatası: {exc}")
        return VerificationResult(
            status=VerifyStatus.SKIPPED,
            method=VerifyMethod.NONE,
            detail=f"doğrulama yapılamadı: {exc}",
        )


def _verify_suggestions(run: AnalysisRun, cfg: Config) -> None:
    skipped = VerificationResult(
        status=VerifyStatus.SKIPPED, method=VerifyMethod.NONE, detail="--no-verify"
    )
    workspaces: dict[Path, Workspace] = {}
    with ExitStack() as stack:
        for report in run.reports:
            for index, suggestion in enumerate(report.suggestions):
                if suggestion.patch is None:
                    continue
                result = (
                    _verify_one(run, stack, workspaces, cfg, suggestion) if cfg.verify else skipped
                )
                report.suggestions[index] = suggestion.model_copy(update={"verification": result})


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
    _verify_suggestions(run, cfg)
    return run


def _top_level(units: list[CodeUnit]) -> list[CodeUnit]:
    return [
        u
        for u in units
        if not any(
            o is not u and o.lines.start <= u.lines.start and u.lines.end <= o.lines.end
            for o in units
        )
    ]


def _unit_code(text: str, unit: CodeUnit) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(lines[unit.lines.start - 1 : unit.lines.end])


def _explain_units(
    result: ExplainResult, llm: LLMClient, plugin: LanguagePlugin, text: str
) -> list[UnitExplanation]:
    name = result.file.name
    explained: list[UnitExplanation] = []
    for unit in _top_level(plugin.extract_units(text)):
        code = number_lines(_unit_code(text, unit), unit.lines.start)
        prompt = build_unit_prompt(name, plugin.name, unit.name, code)
        try:
            answer, usage = llm.structured(EXPLAIN_SYSTEM, prompt, UnitExplanation)
        except LLMError as exc:
            (result.errors if exc.fatal else result.warnings).append(f"{name}: {unit.name}: {exc}")
            if exc.fatal:
                break
            continue
        result.usage = result.usage.add(usage)
        explained.append(answer.model_copy(update={"name": unit.name}))
    return explained


def _explain_large(
    result: ExplainResult, llm: LLMClient, plugin: LanguagePlugin, text: str
) -> FileExplanation | None:
    name = result.file.name
    explained = _explain_units(result, llm, plugin, text)
    if not explained:
        result.errors.append(f"{name}: hiçbir birim açıklanamadı")
        return None
    purposes = [(u.name, u.purpose) for u in explained]
    try:
        answer, usage = llm.structured(
            EXPLAIN_SYSTEM, build_summary_prompt(name, purposes), FileExplanation
        )
    except LLMError as exc:
        result.warnings.append(f"{name}: özet üretilemedi: {exc}")
        return FileExplanation(summary="", units=explained)
    result.usage = result.usage.add(usage)
    return FileExplanation(summary=answer.summary, units=explained)


def _explain_whole(
    result: ExplainResult, llm: LLMClient, plugin: LanguagePlugin, text: str
) -> FileExplanation | None:
    name = result.file.name
    prompt = build_explain_prompt(name, plugin.name, number_lines(text, 1))
    try:
        answer, usage = llm.structured(EXPLAIN_SYSTEM, prompt, FileExplanation)
    except LLMError as exc:
        result.errors.append(f"{name}: {exc}")
        return None
    result.usage = result.usage.add(usage)
    return answer


def explain(file: Path, cfg: Config, llm: LLMClient) -> ExplainResult:
    result = ExplainResult(file=file)
    plugin = plugin_for(file)
    if is_denied(file, cfg.deny_patterns):
        result.errors.append(f"{file.name}: deny-list, dosya LLM'e gönderilmez")
    elif plugin is None:
        result.errors.append(f"{file.name}: desteklenmeyen dil")
    else:
        text = file.read_text(encoding="utf-8", errors="replace")
        if len(text.splitlines()) <= EXPLAIN_WHOLE_FILE_LINES:
            result.explanation = _explain_whole(result, llm, plugin, text)
        else:
            result.explanation = _explain_large(result, llm, plugin, text)
    return result


def _select_workload(ws: Workspace, file: Path, bench: Path | None, cfg: Config) -> Workload | None:
    """--bench script, else project tests, else the file itself when it has a main guard."""
    if bench is not None:
        if not bench.resolve().is_relative_to(ws.project_root):
            raise WorkloadError(f"benchmark betiği proje dışında: {bench}")
        return Workload(script=ws.path_for(bench))
    if tests_usable(ws, cfg):
        return Workload()
    if _MAIN_GUARD.search(file.read_text(encoding="utf-8", errors="replace")):
        return Workload(script=ws.path_for(file))
    return None


def _suggest_for_unit(
    run: AnalysisRun,
    report: Report,
    unit: CodeUnit,
    source: str,
    llm: LLMClient,
    ids: Iterator[int],
    total_s: float,
    entries: list[ProfileEntry],
) -> bool:
    """Returns False after a fatal LLM error."""
    code = _unit_code(source, unit)
    own = [e for e in entries if unit.lines.start <= e.line <= unit.lines.end]
    prompt = build_optimize_prompt(
        report.file.name,
        "python",
        unit.name,
        unit.lines.start,
        number_lines(code, unit.lines.start),
        own,
        total_s,
    )
    try:
        response, usage = llm.structured(OPTIMIZE_SYSTEM, prompt, LLMUnitResponse)
    except LLMError as exc:
        (run.errors if exc.fatal else run.warnings).append(f"{report.file.name}: {exc}")
        return not exc.fatal
    report.usage = report.usage.add(usage)
    group = _Group(unit.name, unit.lines.start, unit.lines.end, [])
    for fix in response.fixes:
        perf_fix = fix.model_copy(update={"category": Category.PERF})
        suggestion, error = _suggestion(ids, report.file, group, code, perf_fix)
        report.suggestions.append(suggestion)
        if error:
            run.warnings.append(error)
    return True


def _verify_optimization(
    run: AnalysisRun,
    ws: Workspace,
    report: Report,
    suggestion: Suggestion,
    plugin: LanguagePlugin,
    cfg: Config,
    workload: Workload,
    before: tuple[float, str],
) -> Suggestion:
    assert suggestion.patch is not None
    try:
        result, bench = verify_optimization(ws, suggestion.patch, plugin, cfg, workload, before)
    except OSError as exc:
        run.warnings.append(f"{report.file.name}: doğrulama altyapısı hatası: {exc}")
        result = VerificationResult(
            status=VerifyStatus.SKIPPED,
            method=VerifyMethod.NONE,
            detail=f"doğrulama yapılamadı: {exc}",
        )
        bench = None
    return suggestion.model_copy(update={"verification": result, "benchmark": bench})


def _verify_all(
    run: AnalysisRun,
    ws: Workspace,
    report: Report,
    plugin: LanguagePlugin,
    cfg: Config,
    workload: Workload,
    before: tuple[float, str] | None,
) -> None:
    skipped = VerificationResult(
        status=VerifyStatus.SKIPPED, method=VerifyMethod.NONE, detail="--no-verify"
    )
    for index, suggestion in enumerate(report.suggestions):
        if suggestion.patch is None:
            continue
        if before is None:
            report.suggestions[index] = suggestion.model_copy(update={"verification": skipped})
        else:
            report.suggestions[index] = _verify_optimization(
                run, ws, report, suggestion, plugin, cfg, workload, before
            )


def _optimize_in(
    ws: Workspace,
    run: AnalysisRun,
    report: Report,
    plugin: LanguagePlugin,
    cfg: Config,
    llm: LLMClient,
    bench: Path | None,
) -> None:
    workload = _select_workload(ws, report.file, bench, cfg)
    if workload is None:
        run.errors.append(NO_PROFILE_DATA)
        return
    entries, total_s = profile(ws, workload, ws.path_for(report.file), cfg.subprocess_timeout_s)
    run.profile = entries
    source = report.file.read_text(encoding="utf-8", errors="replace")
    hot = hot_units(entries, total_s, plugin.extract_units(source))
    if not hot:
        run.warnings.append("profilde belirgin sıcak nokta yok")
        return
    before = measure(ws, workload, cfg.subprocess_timeout_s) if cfg.verify else None
    ids = count(1)
    for unit in hot:
        if not _suggest_for_unit(run, report, unit, source, llm, ids, total_s, entries):
            break
    _verify_all(run, ws, report, plugin, cfg, workload, before)


def optimize(file: Path, cfg: Config, llm: LLMClient, bench: Path | None = None) -> AnalysisRun:
    """Profile a workload, ask the LLM about the hot units, keep only measured speedups."""
    run = AnalysisRun()
    plugin = plugin_for(file)
    if is_denied(file, cfg.deny_patterns):
        run.errors.append(f"{file.name}: deny-list, dosya işlenmedi")
    elif plugin is None:
        run.errors.append(f"{file.name}: desteklenmeyen dil")
    else:
        report = Report(file=file, content_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        run.reports.append(report)
        try:
            with Workspace(find_project_root(file)) as ws:
                _optimize_in(ws, run, report, plugin, cfg, llm, bench)
        except (WorkloadError, OSError) as exc:
            run.errors.append(f"{file.name}: {exc}")
    return run
