"""Rich rendering of reports. Core returns data; this module only formats it."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from mytool.core.apply import selectable
from mytool.core.models import (
    AnalysisRun,
    Benchmark,
    Category,
    ExplainResult,
    Finding,
    Report,
    Severity,
    Suggestion,
    TokenUsage,
    TranslateResult,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.pricing import estimate_cost

_LABELS: dict[Category, tuple[str, str]] = {
    Category.BUG: ("HATA", "red"),
    Category.SECURITY: ("GÜVENLİK", "magenta"),
    Category.PERF: ("PERF", "yellow"),
    Category.STYLE: ("STİL", "cyan"),
}


def _display_path(path: Path, cwd: Path) -> str:
    try:
        return path.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return str(path)


def _finding_line(finding: Finding) -> str:
    label, color = _LABELS.get(finding.category, ("STİL", "cyan"))
    symbol = f" ({escape(finding.symbol)})" if finding.symbol else ""
    return (
        f"  [{color}]\\[{label}][/] satır {finding.lines.start} "
        f"[dim]{escape(finding.rule)}[/] {escape(finding.message)}{symbol}"
    )


def _diff_line(line: str) -> str:
    text = escape(line)
    if line.startswith(("+++", "---")):
        return f"[bold]{text}[/]"
    if line.startswith("+"):
        return f"[green]{text}[/]"
    if line.startswith("-"):
        return f"[red]{text}[/]"
    return f"[cyan]{text}[/]" if line.startswith("@@") else f"[dim]{text}[/]"


def _render_diff(console: Console, suggestion: Suggestion, indent: str) -> None:
    if suggestion.patch is None:
        return
    for line in suggestion.patch.unified_diff().splitlines():
        console.print(f"{indent}{_diff_line(line)}", highlight=False)


def _status(suggestion: Suggestion) -> str:
    result = suggestion.verification
    if result is None or suggestion.patch is None:
        return "[yellow]⚠ yalnız açıklama[/]"
    detail = escape(result.detail)
    if result.status == VerifyStatus.PASSED and result.method == VerifyMethod.PYTEST:
        return "[green]✓ testler geçti[/]"
    if result.status == VerifyStatus.PASSED and result.method == VerifyMethod.BENCHMARK:
        return "[green]✓ çıktı aynı, hızlanma ölçüldü[/]"
    if result.status == VerifyStatus.PASSED:
        return f"[yellow]⚠ doğrulanamadı (yalnız sözdizimi: {detail})[/]"
    return f"[yellow]⚠ doğrulanmadı ({detail})[/]"


def _benchmark_line(bench: Benchmark) -> str:
    return f"önce {bench.before_s:.3f}s → sonra {bench.after_s:.3f}s ({bench.speedup:.1f}x)"


def _render_suggestion(console: Console, suggestion: Suggestion, diff_only: bool) -> None:
    if diff_only:
        _render_diff(console, suggestion, "  ")
        return
    console.print(f"    [bold]Öneri:[/] {escape(suggestion.explanation)}")
    if suggestion.category == Category.SHRINK and suggestion.patch is not None:
        console.print(f"    [bold green]−{-suggestion.patch.line_delta} satır[/]")
    _render_diff(console, suggestion, "    ")
    if suggestion.benchmark is not None:
        console.print(f"    [bold green]{_benchmark_line(suggestion.benchmark)}[/]")
    console.print(f"    {_status(suggestion)}")


def _render_report(console: Console, report: Report, cwd: Path, diff_only: bool) -> None:
    name = escape(_display_path(report.file, cwd))
    console.print(f"[bold]{name}[/] — {len(report.findings)} bulgu")
    shown: set[str] = set()
    suggestions = report.visible_suggestions()
    for finding in report.findings:
        if not diff_only:
            console.print(_finding_line(finding))
        for suggestion in suggestions:
            if suggestion.id not in shown and finding.id in suggestion.finding_ids:
                shown.add(suggestion.id)
                _render_suggestion(console, suggestion, diff_only)
    for suggestion in suggestions:
        if suggestion.id not in shown:
            _render_suggestion(console, suggestion, diff_only)


def _render_hidden(console: Console, run: AnalysisRun, verbose: bool) -> None:
    failed = [s for r in run.reports for s in r.suggestions if not s.presentable]
    if not failed:
        return
    console.print(f"[dim]{len(failed)} öneri doğrulamada başarısız olduğu için gizlendi[/]")
    if not verbose:
        return
    for suggestion in failed:
        detail = suggestion.verification.detail if suggestion.verification else ""
        console.print(f"[dim]  {escape(suggestion.id)}:[/]")
        for line in detail.splitlines()[:5]:
            console.print(f"[dim]    {escape(line)}[/]")


def _totals(reports: Sequence[Report]) -> str:
    findings = [f for r in reports for f in r.findings]
    count = {s: sum(1 for f in findings if f.severity == s) for s in Severity}
    return (
        f"Toplam: {len(reports)} dosya, {len(findings)} bulgu "
        f"({count[Severity.ERROR]} hata, {count[Severity.WARNING]} uyarı, "
        f"{count[Severity.INFO]} bilgi)"
    )


def _render_messages(console: Console, run: AnalysisRun, verbose: bool) -> None:
    for error in run.errors:
        console.print(f"[red]{escape(error)}[/]")
    for warning in run.warnings:
        console.print(f"[yellow]{escape(warning)}[/]")
    _render_hidden(console, run, verbose)
    for skip in run.skipped:
        console.print(f"[dim]atlandı: {escape(skip)}[/]")


def _render_tokens(console: Console, usage: TokenUsage, model: str) -> None:
    cost = estimate_cost(model, usage)
    tail = (
        "bilinmeyen model, maliyet hesaplanmadı" if cost is None else f"tahmini maliyet ${cost:.4f}"
    )
    console.print(f"Token: giriş {usage.input_tokens}, çıkış {usage.output_tokens} — {tail}")


def render_reports(
    console: Console,
    run: AnalysisRun,
    cwd: Path,
    *,
    model: str,
    diff_only: bool = False,
    verbose: bool = False,
) -> None:
    for report in run.reports:
        _render_report(console, report, cwd, diff_only)
    _render_messages(console, run, verbose)
    if run.truncated:
        console.print(
            f"[yellow]{run.truncated} bulgu sınır nedeniyle gösterilmedi (--max-findings)[/]"
        )
    if not any(r.findings for r in run.reports):
        console.print("[green]Bulgu yok[/]")
    console.print(_totals(run.reports))
    if verbose:
        _render_tokens(console, run.usage, model)


def _profile_table(run: AnalysisRun) -> Table:
    table = Table(title="Profil (en çok süre alan 10 işlev)")
    table.add_column("işlev")
    for name in ("satır", "çağrı", "tottime (s)", "cumtime (s)"):
        table.add_column(name, justify="right")
    for entry in run.profile[:10]:
        table.add_row(
            escape(entry.function),
            str(entry.line),
            str(entry.calls),
            f"{entry.tottime:.4f}",
            f"{entry.cumtime:.4f}",
        )
    return table


def _render_suggestion_lists(
    console: Console, run: AnalysisRun, cwd: Path, diff_only: bool
) -> None:
    for report in run.reports:
        name = escape(_display_path(report.file, cwd))
        visible = report.visible_suggestions()
        console.print(f"[bold]{name}[/] — {len(visible)} öneri")
        for suggestion in visible:
            _render_suggestion(console, suggestion, diff_only)


def render_optimize(
    console: Console,
    run: AnalysisRun,
    cwd: Path,
    *,
    diff_only: bool = False,
    verbose: bool = False,
    model: str,
) -> None:
    if run.profile:
        console.print(_profile_table(run))
    _render_suggestion_lists(console, run, cwd, diff_only)
    _render_messages(console, run, verbose)
    if verbose:
        _render_tokens(console, run.usage, model)


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def _shrink_total(run: AnalysisRun) -> str | None:
    applicable = [s for r in run.reports for s in r.suggestions if selectable(s) and s.patch]
    if not applicable:
        return None
    saved = -sum(s.patch.line_delta for s in applicable if s.patch)
    before = sum(_line_count(r.file) for r in run.reports)
    return f"Toplam: −{saved} satır ({before} → {before - saved})"


def render_shrink(
    console: Console,
    run: AnalysisRun,
    cwd: Path,
    *,
    diff_only: bool = False,
    verbose: bool = False,
    model: str,
) -> None:
    _render_suggestion_lists(console, run, cwd, diff_only)
    _render_messages(console, run, verbose)
    total = _shrink_total(run)
    console.print(total or "[green]Kısaltma önerisi yok[/]")
    if verbose:
        _render_tokens(console, run.usage, model)


def _translate_status(result: TranslateResult) -> str:
    check = result.verification
    if check is None:
        return "[yellow]⚠ doğrulanamadı[/]"
    detail = escape(check.detail.splitlines()[0] if check.detail else "")
    if check.status == VerifyStatus.PASSED:
        return f"[green]✓ {detail}[/]"
    if check.status == VerifyStatus.FAILED:
        return f"[red]✗ çeviri doğrulamada başarısız: {detail}[/]"
    return f"[yellow]⚠ doğrulanamadı ({detail})[/]"


def render_translate(
    console: Console, result: TranslateResult, lexer: str, *, verbose: bool = False, model: str
) -> None:
    """Failed verification never shows code: only the reason (details with verbose)."""
    if result.presentable and result.output:
        console.print(Syntax(result.output, lexer, word_wrap=True))
        for segment in result.segments:
            for note in segment.notes:
                console.print(f"[dim]  • {escape(note)}[/]")
    if result.verification is not None:
        console.print(_translate_status(result))
        if verbose and not result.presentable:
            for line in result.verification.detail.splitlines()[1:]:
                console.print(f"[dim]    {escape(line)}[/]")
    for error in result.errors:
        console.print(f"[red]{escape(error)}[/]")
    for warning in result.warnings:
        console.print(f"[yellow]{escape(warning)}[/]")
    if verbose:
        _render_tokens(console, result.usage, model)


def render_explain(
    console: Console, result: ExplainResult, *, verbose: bool = False, model: str
) -> None:
    explanation = result.explanation
    if explanation is not None:
        title = escape(result.file.name)
        console.print(Panel(escape(explanation.summary), title=title, title_align="left"))
        for unit in explanation.units:
            console.print(f"[bold]{escape(unit.name)}[/]")
            console.print(f"  {escape(unit.purpose)}")
            for note in unit.notes:
                console.print(f"    • {escape(note)}")
    for error in result.errors:
        console.print(f"[red]{escape(error)}[/]")
    for warning in result.warnings:
        console.print(f"[yellow]{escape(warning)}[/]")
    if verbose:
        _render_tokens(console, result.usage, model)
