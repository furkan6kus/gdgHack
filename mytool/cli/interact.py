"""Prompts and summaries for applying suggestions."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, Prompt

from mytool.cli.render import _display_path
from mytool.core.apply import fix_eligible, selectable
from mytool.core.models import AnalysisRun, ApplyResult, Report, Suggestion


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def eligible_ids(run: AnalysisRun) -> set[str]:
    return {s.id for r in run.reports for s in r.suggestions if fix_eligible(s)}


def selectable_pairs(run: AnalysisRun) -> list[tuple[Report, Suggestion]]:
    return [(r, s) for r in run.reports for s in r.suggestions if selectable(s)]


def _describe(report: Report, s: Suggestion, cwd: Path) -> str:
    line = s.patch.lines.start if s.patch and s.patch.lines else 1
    where = f"{_display_path(report.file, cwd)}:{line}"
    return f"{s.id} ({where}) {s.explanation[:60]} uygulansın mı?"


def choose_ids(console: Console, run: AnalysisRun, cwd: Path) -> set[str]:
    pairs = selectable_pairs(run)
    answer = Prompt.ask(
        "Uygula? [a]ll / [s]eç / [h]iç", choices=["a", "s", "h"], default="h", console=console
    )
    if answer == "a":
        return {s.id for _, s in pairs}
    if answer == "s":
        return {
            s.id
            for r, s in pairs
            if Confirm.ask(escape(_describe(r, s, cwd)), default=False, console=console)
        }
    return set()


def print_apply_summary(console: Console, result: ApplyResult) -> None:
    backup = f" Yedek: {result.backup_dir}" if result.backup_dir else ""
    console.print(f"{result.applied_count} öneri uygulandı.{backup}")
    for outcome in result.skipped:
        console.print(
            f"[yellow]{escape(outcome.suggestion_id)} atlandı: {escape(outcome.reason)}[/]"
        )


def print_not_fixed(console: Console, run: AnalysisRun) -> None:
    left = [s for _, s in selectable_pairs(run) if not fix_eligible(s)]
    if left:
        console.print(
            f"[dim]{len(left)} öneri yalnız sözdizimiyle doğrulandığı için --fix ile "
            "uygulanmadı (etkileşimli seçimle uygulanabilir)[/]"
        )
