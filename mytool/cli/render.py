"""Rich rendering of reports. Core returns data; this module only formats it."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from mytool.core.models import AnalysisRun, Category, Finding, Report, Severity, Suggestion

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
    if suggestion.verification is None:
        return "[yellow]⚠ doğrulanmadı[/]"
    return f"[dim]doğrulama: {suggestion.verification.status.value}[/]"


def _render_suggestion(console: Console, suggestion: Suggestion, diff_only: bool) -> None:
    if diff_only:
        _render_diff(console, suggestion, "  ")
        return
    console.print(f"    [bold]Öneri:[/] {escape(suggestion.explanation)}")
    _render_diff(console, suggestion, "    ")
    if suggestion.patch is not None:
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


def _totals(reports: Sequence[Report]) -> str:
    findings = [f for r in reports for f in r.findings]
    count = {s: sum(1 for f in findings if f.severity == s) for s in Severity}
    return (
        f"Toplam: {len(reports)} dosya, {len(findings)} bulgu "
        f"({count[Severity.ERROR]} hata, {count[Severity.WARNING]} uyarı, "
        f"{count[Severity.INFO]} bilgi)"
    )


def render_reports(
    console: Console,
    run: AnalysisRun,
    cwd: Path,
    *,
    diff_only: bool = False,
    verbose: bool = False,
) -> None:
    for report in run.reports:
        _render_report(console, report, cwd, diff_only)
    for error in run.errors:
        console.print(f"[red]{escape(error)}[/]")
    for skip in run.skipped:
        console.print(f"[dim]atlandı: {escape(skip)}[/]")
    if run.truncated:
        console.print(
            f"[yellow]{run.truncated} bulgu sınır nedeniyle gösterilmedi (--max-findings)[/]"
        )
    if not any(r.findings for r in run.reports):
        console.print("[green]Bulgu yok[/]")
    console.print(_totals(run.reports))
    if verbose:
        usage = run.usage
        console.print(f"Token: giriş {usage.input_tokens}, çıkış {usage.output_tokens}")
