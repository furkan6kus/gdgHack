"""Analysis pipeline orchestration."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from itertools import count
from pathlib import Path

from mytool.core.analyzers.base import Analyzer, AnalyzerError
from mytool.core.analyzers.messages_tr import SYNTAX_RULES
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
    Patch,
    ProfileEntry,
    ProgressEvent,
    Report,
    Severity,
    Stage,
    Suggestion,
    TokenUsage,
    UnitExplanation,
    UnitKind,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.parser import def_line, unit_for_line
from mytool.core.patching import PatchError, build_patch
from mytool.core.pricing import estimate_cost
from mytool.core.profiling import Workload, WorkloadError, hot_units, measure, profile
from mytool.core.prompts import (
    EXPLAIN_SYSTEM,
    FIX_SYSTEM,
    OPTIMIZE_SYSTEM,
    SHRINK_SYSTEM,
    build_explain_prompt,
    build_fix_prompt,
    build_optimize_prompt,
    build_shrink_prompt,
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
SHRINK_MIN_LINES = 8
SHRINK_MAX_LINE = 100
NO_PROFILE_DATA = "profil verisi yok: --bench ile bir benchmark betiği ver"
MAIN_GUARD = re.compile(r"^if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", re.MULTILINE)
_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


class Cancelled(Exception):
    """Raised when `should_cancel` returned True; temp workspaces are already cleaned up."""


@dataclass(frozen=True)
class Progress:
    """Optional progress sink and cancellation check, polled between units of work."""

    on_progress: Callable[[ProgressEvent], None] | None = None
    should_cancel: Callable[[], bool] | None = None

    def emit(
        self, stage: Stage, message: str, current: int | None = None, total: int | None = None
    ) -> None:
        if self.should_cancel is not None and self.should_cancel():
            raise Cancelled
        if self.on_progress is not None:
            self.on_progress(
                ProgressEvent(stage=stage, message=message, current=current, total=total)
            )


_SILENT = Progress()


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


def _hash_files(files: list[Path], progress: Progress) -> dict[Path, str]:
    hashes: dict[Path, str] = {}
    for index, path in enumerate(files, start=1):
        progress.emit(Stage.PARSING, f"{path.name} okunuyor", index, len(files))
        hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def analyze_static(
    target: Path,
    cfg: Config,
    analyzers: Sequence[Analyzer] | None = None,
    progress: Progress = _SILENT,
) -> AnalysisRun:
    files, skipped = collect_files(target, cfg)
    hashes = _hash_files(files, progress)
    progress.emit(Stage.STATIC_ANALYSIS, "statik analiz çalıştırılıyor")
    findings, errors = _run_analyzers(
        analyzers if analyzers is not None else [RuffAnalyzer()],
        files,
        float(cfg.subprocess_timeout_s),
    )
    progress.emit(Stage.STATIC_ANALYSIS, f"{len(findings)} bulgu bulundu")
    kept, hidden = _cap(findings, cfg.max_findings)
    groups = _group_by_file(kept, files)
    reports = [
        Report(file=p, findings=_with_symbols(p, groups.get(p, [])), content_sha256=hashes[p])
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
    # A file with syntax errors does not parse until all of them are fixed, so they go to
    # the model together, with the whole file, and come back as one verifiable fix.
    syntax = [f for f in findings if f.rule in SYNTAX_RULES]
    rest = [f for f in findings if f.rule not in SYNTAX_RULES]
    groups = [_Group(None, 1, len(text_lines), syntax)] if syntax and text_lines else []
    in_unit = [f for f in rest if f.symbol]
    module_level = [f for f in rest if not f.symbol]
    groups += _unit_groups(_units_for(path), in_unit) if in_unit else []
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


@dataclass(frozen=True)
class _Plan:
    report: Report
    text_lines: list[str]
    groups: list[_Group]


def _plan(report: Report) -> _Plan:
    text = report.file.read_text(encoding="utf-8", errors="replace")
    text_lines = text.splitlines(keepends=True)
    return _Plan(report, text_lines, _make_groups(report.file, text_lines, report.findings))


def _suggest_for_report(
    run: AnalysisRun,
    plan: _Plan,
    llm: LLMClient,
    ids: Iterator[int],
    before_group: Callable[[_Group], bool],
) -> bool:
    """Returns False when the remaining calls should be skipped (fatal LLM error or budget)."""
    report, text_lines = plan.report, plan.text_lines
    for group in plan.groups:
        if not before_group(group):
            return False
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


def _verify_suggestions(run: AnalysisRun, cfg: Config, progress: Progress = _SILENT) -> None:
    skipped = VerificationResult(
        status=VerifyStatus.SKIPPED, method=VerifyMethod.NONE, detail="--no-verify"
    )
    total = sum(1 for r in run.reports for s in r.suggestions if s.patch is not None)
    step = count(1)
    workspaces: dict[Path, Workspace] = {}
    with ExitStack() as stack:
        for report in run.reports:
            for index, suggestion in enumerate(report.suggestions):
                if suggestion.patch is None:
                    continue
                if cfg.verify:
                    message = f"{report.file.name}: düzeltme deneniyor"
                    progress.emit(Stage.VERIFY, message, next(step), total)
                result = (
                    _verify_one(run, stack, workspaces, cfg, suggestion) if cfg.verify else skipped
                )
                report.suggestions[index] = suggestion.model_copy(update={"verification": result})


def _over_budget(run: AnalysisRun, cfg: Config) -> bool:
    cost = estimate_cost(cfg.model, run.usage)
    return cost is not None and cost >= cfg.max_cost_usd


def _suggest_all(run: AnalysisRun, cfg: Config, llm: LLMClient, progress: Progress) -> None:
    plans = [_plan(report) for report in run.reports if report.findings]
    total = sum(len(plan.groups) for plan in plans)
    step, ids = count(1), count(1)
    if estimate_cost(cfg.model, TokenUsage()) is None:
        run.warnings.append(
            f"'{cfg.model}' modelinin fiyatı bilinmiyor; harcama sınırı uygulanamadı."
        )

    def before_group(group: _Group) -> bool:
        current = next(step)
        if _over_budget(run, cfg):
            spent = estimate_cost(cfg.model, run.usage) or 0.0
            run.warnings.append(
                f"Harcama sınırına ulaşıldı (tahmini ${spent:.2f} / sınır "
                f"${cfg.max_cost_usd:.2f}); kalan {total - current + 1} kod parçası "
                "için öneri istenmedi."
            )
            return False
        rules = ", ".join(sorted({f.rule for f in group.findings}))
        where = group.unit_name or f"satır {group.start}-{group.end}"
        progress.emit(Stage.LLM, f"{where}: {rules} için öneri isteniyor", current, total)
        return True

    for plan in plans:
        if not _suggest_for_report(run, plan, llm, ids, before_group):
            break


def analyze(
    target: Path,
    cfg: Config,
    llm: LLMClient | None,
    analyzers: Sequence[Analyzer] | None = None,
    *,
    on_progress: Callable[[ProgressEvent], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> AnalysisRun:
    """Static analysis, then (with `llm`) suggestions and verification.

    `on_progress` receives ProgressEvents; `should_cancel` is polled between units of
    work and makes the call raise `Cancelled`.
    """
    progress = Progress(on_progress, should_cancel)
    run = analyze_static(target, cfg, analyzers, progress)
    if llm is not None:
        _suggest_all(run, cfg, llm, progress)
        _verify_suggestions(run, cfg, progress)
    progress.emit(Stage.DONE, "analiz tamamlandı")
    return run


def top_level(units: list[CodeUnit]) -> list[CodeUnit]:
    return [
        u
        for u in units
        if not any(
            o is not u and o.lines.start <= u.lines.start and u.lines.end <= o.lines.end
            for o in units
        )
    ]


def unit_code(text: str, unit: CodeUnit) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(lines[unit.lines.start - 1 : unit.lines.end])


def _explain_units(
    result: ExplainResult, llm: LLMClient, plugin: LanguagePlugin, text: str
) -> list[UnitExplanation]:
    name = result.file.name
    explained: list[UnitExplanation] = []
    for unit in top_level(plugin.extract_units(text)):
        code = number_lines(unit_code(text, unit), unit.lines.start)
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
    if MAIN_GUARD.search(file.read_text(encoding="utf-8", errors="replace")):
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
    code = unit_code(source, unit)
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


def _inside(inner: CodeUnit, outer: CodeUnit) -> bool:
    return outer.lines.start <= inner.lines.start and inner.lines.end <= outer.lines.end


def _shrink_units(units: list[CodeUnit], limit: int) -> list[CodeUnit]:
    """Outermost functions/methods with at least 8 lines, longest first."""
    funcs = [u for u in units if u.kind != UnitKind.CLASS]
    outer = [u for u in funcs if not any(o is not u and _inside(u, o) for o in funcs)]

    def size(unit: CodeUnit) -> int:
        return unit.lines.end - unit.lines.start + 1

    long_units = [u for u in outer if size(u) >= SHRINK_MIN_LINES]
    return sorted(long_units, key=lambda u: (-size(u), u.lines.start))[:limit]


def _shrink_problem(patch: Patch) -> str | None:
    if patch.line_delta >= 0:
        return "daha kısa değil"
    if any(len(line) > SHRINK_MAX_LINE for line in patch.new.splitlines()):
        return f"{SHRINK_MAX_LINE} karakterden uzun satır var"
    if def_line(patch.original) != def_line(patch.new):
        return "imza değişti"
    return None


def _suggest_shrink(
    run: AnalysisRun,
    report: Report,
    unit: CodeUnit,
    source: str,
    llm: LLMClient,
    ids: Iterator[int],
) -> bool:
    """Returns False after a fatal LLM error."""
    name = report.file.name
    code = unit_code(source, unit)
    numbered = number_lines(code, unit.lines.start)
    prompt = build_shrink_prompt(name, "python", unit.name, unit.lines.start, numbered)
    try:
        response, usage = llm.structured(SHRINK_SYSTEM, prompt, LLMUnitResponse)
    except LLMError as exc:
        (run.errors if exc.fatal else run.warnings).append(f"{name}: {unit.name}: {exc}")
        return not exc.fatal
    report.usage = report.usage.add(usage)
    fix = next((f for f in response.fixes if f.original), None)
    if fix is None:
        return True
    fix = fix.model_copy(update={"category": Category.SHRINK, "finding_ids": []})
    group = _Group(unit.name, unit.lines.start, unit.lines.end, [])
    suggestion, error = _suggestion(ids, report.file, group, code, fix)
    problem = error or (_shrink_problem(suggestion.patch) if suggestion.patch else None)
    if problem:
        run.warnings.append(f"{name}: {unit.name}: öneri atıldı ({problem})")
    else:
        report.suggestions.append(suggestion)
    return True


def shrink(file: Path, cfg: Config, llm: LLMClient) -> AnalysisRun:
    """Ask the LLM for shorter equivalent versions of the longest functions, then verify."""
    run = AnalysisRun()
    plugin = plugin_for(file)
    if is_denied(file, cfg.deny_patterns):
        run.errors.append(f"{file.name}: deny-list, dosya işlenmedi")
    elif plugin is None:
        run.errors.append(f"{file.name}: desteklenmeyen dil")
    else:
        source = file.read_text(encoding="utf-8", errors="replace")
        report = Report(file=file, content_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        run.reports.append(report)
        ids = count(1)
        for unit in _shrink_units(plugin.extract_units(source), cfg.max_findings):
            if not _suggest_shrink(run, report, unit, source, llm, ids):
                break
        _verify_suggestions(run, cfg)
    return run
