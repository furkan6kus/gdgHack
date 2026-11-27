"""Thin Typer + Rich command layer. All logic lives in mytool.core."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm

from mytool import __version__
from mytool.cli import interact
from mytool.cli.interact import _is_interactive
from mytool.cli.render import render_reports
from mytool.core.apply import apply_suggestions, latest_backup, restore_backup
from mytool.core.config import Config, has_api_key, load_config
from mytool.core.llm import AnthropicLLM, LLMClient
from mytool.core.models import AnalysisRun, ApplyResult
from mytool.core.pipeline import analyze
from mytool.core.verify import find_project_root

app = typer.Typer(
    name="mytool",
    help="Static analysis with LLM-suggested, verified patches.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True)

PathArg = Annotated[Path, typer.Argument(help="File or directory to process.")]
DiffOpt = Annotated[bool, typer.Option("--diff", help="Show patches as unified diffs.")]
FixOpt = Annotated[bool, typer.Option("--fix", help="Apply verified patches.")]
JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")]
NoVerifyOpt = Annotated[bool, typer.Option("--no-verify", help="Skip patch verification.")]
ModelOpt = Annotated[str | None, typer.Option("--model", help="LLM model name.")]
MaxFindingsOpt = Annotated[
    int | None, typer.Option("--max-findings", min=1, help="Max findings sent to the LLM.")
]
MaxTokensOpt = Annotated[
    int | None, typer.Option("--max-tokens", min=1, help="Max output tokens per LLM request.")
]
StaticOpt = Annotated[bool, typer.Option("--static", help="Skip the LLM, static findings only.")]
TimeoutOpt = Annotated[
    int | None, typer.Option("--timeout", min=1, help="Subprocess timeout in seconds.")
]
VerboseOpt = Annotated[bool, typer.Option("--verbose", help="Verbose output.")]


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"mytool {__version__}")
        raise typer.Exit


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """mytool command line."""
    _force_utf8()


def _prepare(
    command: str,
    path: Path,
    phase: int,
    *,
    json_out: bool,
    no_verify: bool,
    model: str | None,
    max_findings: int | None,
) -> Config:
    if not path.exists():
        err_console.print(f"[red]Error:[/] path not found: {path}")
        raise typer.Exit(2)
    config = load_config(model=model, max_findings=max_findings, verify=not no_verify)
    if json_out:
        typer.echo(json.dumps({"status": "not_implemented", "command": command}))
    else:
        console.print(f"[yellow]{command}: Faz {phase}'de gelecek[/]")
    return config


def _make_llm(config: Config) -> LLMClient:
    return AnthropicLLM(config)


def _choose_llm(config: Config, static: bool, out: Console) -> LLMClient | None:
    if static:
        return None
    if not has_api_key():
        out.print("[yellow]ANTHROPIC_API_KEY tanımlı değil, yalnız statik bulgular gösteriliyor[/]")
        return None
    out.print("[dim]Not: ilgili kod parçaları Anthropic API'ye gönderilir.[/]")
    return _make_llm(config)


NOTICE_TEXT = (
    "Doğrulama sırasında projenin testleri bu makinede (sandbox yok) geçici bir kopyada "
    "çalıştırılır. İstemiyorsan --no-verify kullan."
)


def _show_verify_notice(out: Console) -> None:
    marker = Path.home() / ".mytool" / "verify-notice"
    if marker.exists():
        return
    out.print(Panel(NOTICE_TEXT, title="Uyarı", border_style="yellow"))
    with contextlib.suppress(OSError):
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()


@app.command(name="analyze")
def analyze_command(
    path: PathArg,
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_findings: MaxFindingsOpt = None,
    max_tokens: MaxTokensOpt = None,
    static: StaticOpt = False,
    timeout: TimeoutOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Run static analysis and suggest verified patches."""
    if not path.exists():
        err_console.print(f"[red]Error:[/] path not found: {path}")
        raise typer.Exit(2)
    config = load_config(
        model=model,
        max_findings=max_findings,
        max_tokens_per_request=max_tokens,
        verify=not no_verify,
        subprocess_timeout_s=timeout,
    )
    llm = _choose_llm(config, static, err_console if json_out else console)
    if llm is not None and config.verify:
        _show_verify_notice(err_console)
    run = analyze(path, config, llm)
    result: ApplyResult | None = None
    if json_out:
        result = _apply_fix(run, path, err_console, no_verify) if fix else None
        payload = {
            "run": run.model_dump(mode="json"),
            "apply": result and result.model_dump(mode="json"),
        }
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        render_reports(console, run, Path.cwd(), diff_only=diff, verbose=verbose)
        if fix:
            _apply_fix(run, path, console, no_verify)
        elif interact.selectable_pairs(run) and _is_interactive():
            _apply_interactive(run, path)
    if run.errors:
        raise typer.Exit(3)


def _root_for(path: Path) -> Path:
    return find_project_root(path / "x" if path.is_dir() else path)


def _backup_root(path: Path) -> Path:
    return _root_for(path) / ".mytool" / "backup"


def _apply_fix(run: AnalysisRun, path: Path, out: Console, no_verify: bool) -> ApplyResult:
    if no_verify:
        out.print("[yellow]--fix doğrulama gerektirir; --no-verify ile hiçbir öneri uygulanmaz[/]")
    ids = set() if no_verify else interact.eligible_ids(run)
    result = apply_suggestions(run.reports, ids, _backup_root(path))
    if not no_verify:
        interact.print_apply_summary(out, result)
        interact.print_not_fixed(out, run)
    return result


def _apply_interactive(run: AnalysisRun, path: Path) -> None:
    ids = interact.choose_ids(console, run, Path.cwd())
    if ids:
        result = apply_suggestions(run.reports, ids, _backup_root(path))
        interact.print_apply_summary(console, result)


@app.command()
def undo(
    path: Annotated[Path, typer.Argument(help="Project path.")] = Path("."),
    yes: Annotated[bool, typer.Option("--yes", help="Do not ask for confirmation.")] = False,
) -> None:
    """Restore files from the latest backup."""
    root = _root_for(path.resolve())
    backup = latest_backup(root / ".mytool" / "backup")
    if backup is None:
        console.print("[yellow]Geri alınacak yedek yok[/]")
        raise typer.Exit(1)
    if not yes:
        if not _is_interactive():
            err_console.print("[red]Onay gerekli: etkileşimsiz ortamda --yes kullan[/]")
            raise typer.Exit(2)
        if not Confirm.ask(
            f"{backup.name} yedeği geri yüklensin mi?", default=False, console=console
        ):
            raise typer.Exit(1)
    for restored in restore_backup(backup, root):
        console.print(f"geri yüklendi: {escape(str(restored))}")


@app.command()
def optimize(
    path: PathArg,
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_findings: MaxFindingsOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Suggest performance optimizations."""
    _prepare(
        "optimize",
        path,
        6,
        json_out=json_out,
        no_verify=no_verify,
        model=model,
        max_findings=max_findings,
    )


@app.command()
def shrink(
    path: PathArg,
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_findings: MaxFindingsOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Suggest shorter equivalent code."""
    _prepare(
        "shrink",
        path,
        6,
        json_out=json_out,
        no_verify=no_verify,
        model=model,
        max_findings=max_findings,
    )


@app.command()
def translate(
    path: PathArg,
    to: Annotated[str, typer.Option("--to", help="Target language.")],
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_findings: MaxFindingsOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Translate code to another language."""
    _prepare(
        "translate",
        path,
        6,
        json_out=json_out,
        no_verify=no_verify,
        model=model,
        max_findings=max_findings,
    )


@app.command()
def explain(
    path: PathArg,
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_findings: MaxFindingsOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Explain what the code does."""
    _prepare(
        "explain",
        path,
        6,
        json_out=json_out,
        no_verify=no_verify,
        model=model,
        max_findings=max_findings,
    )
