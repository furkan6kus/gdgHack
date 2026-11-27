"""Rich rendering of reports. Core returns data; this module only formats it."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from mytool.core.models import Category, Finding, Report, Severity

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


def _render_report(console: Console, report: Report, cwd: Path) -> None:
    name = escape(_display_path(report.file, cwd))
    console.print(f"[bold]{name}[/] — {len(report.findings)} bulgu")
    for finding in report.findings:
        console.print(_finding_line(finding))
    for error in report.errors:
        console.print(f"  [red]{escape(error)}[/]")
    for skip in report.skipped:
        console.print(f"  [dim]atlandı: {escape(skip)}[/]")


def _totals(reports: Sequence[Report]) -> str:
    findings = [f for r in reports for f in r.findings]
    count = {s: sum(1 for f in findings if f.severity == s) for s in Severity}
    return (
        f"Toplam: {len(reports)} dosya, {len(findings)} bulgu "
        f"({count[Severity.ERROR]} hata, {count[Severity.WARNING]} uyarı, "
        f"{count[Severity.INFO]} bilgi)"
    )


def render_reports(console: Console, reports: Sequence[Report], cwd: Path) -> None:
    for report in reports:
        _render_report(console, report, cwd)
    if not any(r.findings for r in reports):
        console.print("[green]Bulgu yok[/]")
    console.print(_totals(reports))
