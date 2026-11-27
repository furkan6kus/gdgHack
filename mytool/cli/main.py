"""Thin Typer + Rich command layer. All logic lives in mytool.core."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from typer import rich_utils

from mytool import __version__
from mytool.cli import interact
from mytool.cli.interact import _is_interactive
from mytool.cli.render import (
    render_explain,
    render_optimize,
    render_reports,
    render_shrink,
    render_translate,
)
from mytool.core.apply import apply_suggestions, latest_backup, restore_backup, write_output
from mytool.core.config import Config, has_api_key, load_config
from mytool.core.llm import AnthropicLLM, LLMClient
from mytool.core.models import AnalysisRun, ApplyResult, TranslateResult
from mytool.core.pipeline import analyze, explain, optimize
from mytool.core.pipeline import shrink as shrink_file
from mytool.core.translate import resolve_target
from mytool.core.translate import translate as translate_file
from mytool.core.verify import find_project_root

rich_utils.ARGUMENTS_PANEL_TITLE = "Argümanlar"
rich_utils.OPTIONS_PANEL_TITLE = "Seçenekler"
rich_utils.COMMANDS_PANEL_TITLE = "Komutlar"
rich_utils.ERRORS_PANEL_TITLE = "Hata"

EXIT_OK = 0
EXIT_ERROR = 1  # unexpected error; undo with no backup
EXIT_USAGE = 2  # usage or input error
EXIT_FAILED = 3  # tool or LLM failure
EXIT_INTERRUPTED = 130

app = typer.Typer(
    name="mytool",
    help="Statik analiz önce, LLM sonra, doğrulama en son: doğrulanmış yama önerileri.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
    pretty_exceptions_enable=False,
)
console = Console()
err_console = Console(stderr=True)

PathArg = Annotated[Path, typer.Argument(help="İşlenecek dosya veya dizin.")]
FileArg = Annotated[Path, typer.Argument(help="İşlenecek dosya.")]
DiffOpt = Annotated[bool, typer.Option("--diff", help="Yamaları birleşik diff olarak göster.")]
FixOpt = Annotated[bool, typer.Option("--fix", help="Doğrulanmış yamaları uygula.")]
JsonOpt = Annotated[bool, typer.Option("--json", help="Makine okunur JSON çıktısı.")]
NoVerifyOpt = Annotated[bool, typer.Option("--no-verify", help="Doğrulamayı atla.")]
ModelOpt = Annotated[str | None, typer.Option("--model", help="LLM model adı.")]
MaxFindingsOpt = Annotated[
    int | None, typer.Option("--max-findings", min=1, help="LLM'e gönderilecek en çok bulgu.")
]
MaxTokensOpt = Annotated[
    int | None, typer.Option("--max-tokens", min=1, help="İstek başına en çok çıkış tokeni.")
]
StaticOpt = Annotated[bool, typer.Option("--static", help="LLM kullanma, yalnız statik bulgular.")]
TimeoutOpt = Annotated[
    int | None, typer.Option("--timeout", min=1, help="Alt süreç zaman aşımı (saniye).")
]
VerboseOpt = Annotated[
    bool, typer.Option("--verbose", help="Ayrıntılı çıktı (token ve tahmini maliyet dahil).")
]


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
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Sürümü göster."),
    ] = False,
) -> None:
    """mytool komut satırı."""
    _force_utf8()


def _input_error(message: str) -> typer.Exit:
    err_console.print(f"[red]Hata:[/] {escape(message)}")
    return typer.Exit(EXIT_USAGE)


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


OPTIMIZE_NOTICE_TEXT = (
    "Profil ve ölçüm için benchmark betiği, projenin testleri veya dosyanın kendisi bu "
    "makinede (sandbox yok) geçici bir kopyada çalıştırılır; --no-verify bunu engellemez."
)


TRANSLATE_NOTICE_TEXT = (
    "Doğrulama için derleyici/denetleyici ve (JavaScript çıktı karşılaştırmasında) orijinal "
    "betik bu makinede (sandbox yok) geçici bir kopyada çalıştırılır. İstemiyorsan "
    "--no-verify kullan."
)


def _show_verify_notice(out: Console, text: str = NOTICE_TEXT) -> None:
    marker = Path.home() / ".mytool" / "verify-notice"
    if marker.exists():
        return
    out.print(Panel(text, title="Uyarı", border_style="yellow"))
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
    """Statik analiz yapar, doğrulanmış yama önerir."""
    if not path.exists():
        raise _input_error(f"yol bulunamadı: {path}")
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
    _present(
        run,
        path,
        json_out=json_out,
        fix=fix,
        no_verify=no_verify,
        render=lambda: render_reports(
            console, run, Path.cwd(), diff_only=diff, verbose=verbose, model=config.model
        ),
    )


def _present(
    run: AnalysisRun,
    path: Path,
    *,
    json_out: bool,
    fix: bool,
    no_verify: bool,
    render: Callable[[], None],
) -> None:
    """Print the run (or JSON), run the apply flow, exit 3 on errors."""
    if json_out:
        result = _apply_fix(run, path, err_console, no_verify) if fix else None
        payload = {
            "run": run.model_dump(mode="json"),
            "apply": result and result.model_dump(mode="json"),
        }
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        render()
        if fix:
            _apply_fix(run, path, console, no_verify)
        elif interact.selectable_pairs(run) and _is_interactive():
            _apply_interactive(run, path)
    if run.errors:
        raise typer.Exit(EXIT_FAILED)


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
    path: Annotated[Path, typer.Argument(help="Proje dizini.")] = Path("."),
    yes: Annotated[bool, typer.Option("--yes", help="Onay sorma.")] = False,
) -> None:
    """Son yedekten dosyaları geri yükler."""
    root = _root_for(path.resolve())
    backup = latest_backup(root / ".mytool" / "backup")
    if backup is None:
        console.print("[yellow]Geri alınacak yedek yok[/]")
        raise typer.Exit(EXIT_ERROR)
    if not yes:
        if not _is_interactive():
            raise _input_error("onay gerekli: etkileşimsiz ortamda --yes kullan")
        if not Confirm.ask(
            f"{backup.name} yedeği geri yüklensin mi?", default=False, console=console
        ):
            console.print("İptal edildi.")
            raise typer.Exit(EXIT_OK)
    for restored in restore_backup(backup, root):
        console.print(f"geri yüklendi: {escape(str(restored))}")


def _require_file(path: Path) -> None:
    if not path.exists():
        raise _input_error(f"yol bulunamadı: {path}")
    if not path.is_file():
        raise _input_error(f"bir dosya ver, dizin değil: {path}")


def _check_bench(path: Path, bench: Path | None) -> None:
    if bench is None:
        return
    if not bench.is_file():
        raise _input_error(f"benchmark betiği bulunamadı: {bench}")
    if not bench.resolve().is_relative_to(_root_for(path).resolve()):
        raise _input_error(f"benchmark betiği proje dışında: {bench}")


def _require_api_key(command: str) -> None:
    if not has_api_key():
        raise _input_error(f"{command} için ANTHROPIC_API_KEY tanımlı olmalı")


@app.command(name="optimize")
def optimize_command(
    path: FileArg,
    bench: Annotated[
        Path | None,
        typer.Option("--bench", help="Kodu çalıştıran Python betiği (iş yükü)."),
    ] = None,
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: Annotated[
        bool,
        typer.Option(
            "--no-verify",
            help="Yama doğrulamasını atla. Profil yine de iş yükünü (bench betiği, proje "
            "testleri veya dosyanın kendisi) bu makinede çalıştırır.",
        ),
    ] = False,
    model: ModelOpt = None,
    max_tokens: MaxTokensOpt = None,
    timeout: TimeoutOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """cProfile ile profil çıkarır, ölçülmüş hızlanmalar önerir."""
    _require_file(path)
    _check_bench(path, bench)
    _require_api_key("optimize")
    config = load_config(
        model=model,
        max_tokens_per_request=max_tokens,
        verify=not no_verify,
        subprocess_timeout_s=timeout,
    )
    out = err_console if json_out else console
    out.print("[dim]Not: ilgili kod parçaları Anthropic API'ye gönderilir.[/]")
    _show_verify_notice(err_console, OPTIMIZE_NOTICE_TEXT)
    run = optimize(path, config, _make_llm(config), bench)
    _present(
        run,
        path,
        json_out=json_out,
        fix=fix,
        no_verify=no_verify,
        render=lambda: render_optimize(
            console, run, Path.cwd(), diff_only=diff, verbose=verbose, model=config.model
        ),
    )


@app.command()
def shrink(
    path: FileArg,
    diff: DiffOpt = False,
    fix: FixOpt = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_findings: MaxFindingsOpt = None,
    max_tokens: MaxTokensOpt = None,
    timeout: TimeoutOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """En uzun işlevler için daha kısa, eşdeğer kod önerir."""
    _require_file(path)
    _require_api_key("shrink")
    config = load_config(
        model=model,
        max_findings=max_findings,
        max_tokens_per_request=max_tokens,
        verify=not no_verify,
        subprocess_timeout_s=timeout,
    )
    out = err_console if json_out else console
    out.print("[dim]Not: ilgili kod parçaları Anthropic API'ye gönderilir.[/]")
    if config.verify:
        _show_verify_notice(err_console)
    run = shrink_file(path, config, _make_llm(config))
    _present(
        run,
        path,
        json_out=json_out,
        fix=fix,
        no_verify=no_verify,
        render=lambda: render_shrink(
            console, run, Path.cwd(), diff_only=diff, verbose=verbose, model=config.model
        ),
    )


def _write_translation(result: TranslateResult, out_file: Path) -> None:
    """Write only a presentable, complete translation; never next to the source by default."""
    if not result.presentable or result.errors or not result.output:
        return
    backup = write_output(out_file, result.output, _backup_root(out_file))
    err_console.print(f"yazıldı: {escape(str(out_file))}")
    if backup is not None:
        err_console.print(f"eski dosya yedeklendi: {escape(str(backup))}")


@app.command()
def translate(
    path: FileArg,
    to: Annotated[str, typer.Option("--to", help="Hedef dil (örn. javascript, go, rust).")],
    out_file: Annotated[
        Path | None, typer.Option("--out", help="Çeviriyi bu yeni dosyaya yaz.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="--out dosyasının üzerine yaz (eskisi yedeklenir).")
    ] = False,
    json_out: JsonOpt = False,
    no_verify: NoVerifyOpt = False,
    model: ModelOpt = None,
    max_tokens: MaxTokensOpt = None,
    timeout: TimeoutOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Dosyayı işlev işlev başka bir dile çevirir."""
    _require_file(path)
    if not to.strip():
        raise _input_error("--to boş olamaz")
    if out_file is not None and out_file.exists() and not force:
        raise _input_error(f"{out_file} zaten var; üzerine yazmak için --force")
    if out_file is not None and out_file.resolve() == path.resolve():
        raise _input_error("--out kaynak dosya olamaz")
    _require_api_key("translate")
    config = load_config(
        model=model,
        max_tokens_per_request=max_tokens,
        verify=not no_verify,
        subprocess_timeout_s=timeout,
    )
    out = err_console if json_out else console
    out.print("[dim]Not: dosyanın kodu Anthropic API'ye gönderilir.[/]")
    if config.verify:
        _show_verify_notice(err_console, TRANSLATE_NOTICE_TEXT)
    result = translate_file(path, to, config, _make_llm(config))
    if json_out:
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    else:
        render_translate(
            console, result, resolve_target(to).lexer, verbose=verbose, model=config.model
        )
    if out_file is not None:
        _write_translation(result, out_file)
    if result.errors or not result.presentable:
        raise typer.Exit(EXIT_FAILED)


@app.command(name="explain")
def explain_command(
    path: FileArg,
    json_out: JsonOpt = False,
    model: ModelOpt = None,
    max_tokens: MaxTokensOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Dosyanın ne yaptığını Türkçe açıklar."""
    _require_file(path)
    _require_api_key("explain")
    config = load_config(model=model, max_tokens_per_request=max_tokens)
    out = err_console if json_out else console
    out.print("[dim]Not: dosyanın kodu Anthropic API'ye gönderilir.[/]")
    result = explain(path, config, _make_llm(config))
    if json_out:
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    else:
        render_explain(console, result, verbose=verbose, model=config.model)
    if result.errors:
        raise typer.Exit(EXIT_FAILED)


def _debug() -> bool:
    return os.environ.get("MYTOOL_DEBUG") == "1"


def _say(message: str) -> None:
    typer.echo(message, err=True)


def _os_error(exc: OSError) -> int:
    detail = exc.strerror or str(exc)
    where = f": {exc.filename}" if exc.filename else ""
    _say(f"Hata: dosya işlemi başarısız: {detail}{where}")
    return EXIT_USAGE


def _unexpected(exc: Exception) -> int:
    _say(f"Beklenmeyen hata: {type(exc).__name__}: {exc}")
    _say("Ayrıntı için MYTOOL_DEBUG=1 ile tekrar çalıştır.")
    return EXIT_ERROR


def _interrupted() -> int:
    _say("İptal edildi.")
    return EXIT_INTERRUPTED


def _exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return EXIT_OK
    if not isinstance(code, int):
        return EXIT_ERROR
    return _interrupted() if code == EXIT_INTERRUPTED else code


def _run() -> int:
    try:
        app()
    except SystemExit as exc:
        return _exit_code(exc)
    except KeyboardInterrupt:
        return _interrupted()
    except Exception as exc:
        if _debug():
            raise
        return _os_error(exc) if isinstance(exc, OSError) else _unexpected(exc)
    return EXIT_OK


def main() -> None:
    """Console entry point: clean messages and exit codes instead of tracebacks."""
    _force_utf8()
    sys.exit(_run())
