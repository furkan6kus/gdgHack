"""Thin Typer + Rich command layer. All logic lives in mytool.core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mytool import __version__
from mytool.cli.render import render_reports
from mytool.core.config import Config, load_config
from mytool.core.pipeline import analyze_static

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
VerboseOpt = Annotated[bool, typer.Option("--verbose", help="Verbose output.")]


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"mytool {__version__}")
        raise typer.Exit


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """mytool command line."""


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


@app.command()
def analyze(
    path: PathArg,
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_findings: MaxFindingsOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Run static analysis and suggest verified patches."""
    if not path.exists():
        err_console.print(f"[red]Error:[/] path not found: {path}")
        raise typer.Exit(2)
    config = load_config(model=model, max_findings=max_findings, verify=not no_verify)
    reports = analyze_static(path, config)
    if json_out:
        typer.echo(
            json.dumps([r.model_dump(mode="json") for r in reports], ensure_ascii=False, indent=2)
        )
    else:
        render_reports(console, reports, Path.cwd())
    if any(r.errors for r in reports):
        raise typer.Exit(3)


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
