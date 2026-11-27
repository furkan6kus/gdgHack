"""Phase 7: top-level error handling, pricing, cost line, per-command smoke, README sanity."""

import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from fakes import FakeLLM
from test_explain import SMALL, _whole
from test_optimize import FAST, _llm
from test_optimize import make_project as make_slow_project
from test_shrink import LONG, SHORT
from test_shrink import _llm as shrink_llm
from test_shrink import make_project as make_shrink_project
from test_translate import _fake as translate_fake
from test_translate import make_project as make_translate_project
from typer.testing import CliRunner

from mytool.cli import main as cli_main
from mytool.cli.main import app, main
from mytool.core.llm import LLMUnitResponse
from mytool.core.models import FileExplanation, TokenUsage, TranslatedSegment
from mytool.core.pricing import PRICES_PER_MTOK, estimate_cost
from mytool.core.verify import Workspace

runner = CliRunner()
FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"
README = Path(__file__).parent.parent / "README.md"
COMMANDS = ("analyze", "undo", "optimize", "shrink", "translate", "explain")


@pytest.fixture(autouse=True)
def _fake_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path_factory.mktemp("home"))
    monkeypatch.delenv("MYTOOL_DEBUG", raising=False)


def _raising(exc: BaseException) -> Callable[..., None]:
    def run(*args: object, **kwargs: object) -> None:
        raise exc

    return run


def _exit_code() -> int:
    with pytest.raises(SystemExit) as info:
        main()
    assert isinstance(info.value.code, int)
    return info.value.code


def _argv(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["mytool", *args])


def test_unexpected_exception_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli_main, "app", _raising(RuntimeError("patladı")))
    assert _exit_code() == 1
    err = capsys.readouterr().err
    assert "Beklenmeyen hata: RuntimeError: patladı" in err
    assert "MYTOOL_DEBUG=1" in err
    assert "Traceback" not in err


def test_debug_env_reraises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "app", _raising(RuntimeError("patladı")))
    monkeypatch.setenv("MYTOOL_DEBUG", "1")
    with pytest.raises(RuntimeError, match="patladı"):
        main()


def test_keyboard_interrupt_exit_130(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli_main, "app", _raising(KeyboardInterrupt()))
    assert _exit_code() == 130
    err = capsys.readouterr().err
    assert "İptal edildi." in err
    assert "Traceback" not in err


def test_interrupt_inside_real_command_exit_130(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli_main, "analyze", _raising(KeyboardInterrupt()))
    _argv(monkeypatch, "analyze", str(FIXTURE))
    assert _exit_code() == 130
    assert "İptal edildi." in capsys.readouterr().err


def test_os_error_is_input_error_exit_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    error = PermissionError(13, "Erişim engellendi", "x.py")
    monkeypatch.setattr(cli_main, "analyze", _raising(error))
    _argv(monkeypatch, "analyze", str(FIXTURE))
    assert _exit_code() == 2
    err = capsys.readouterr().err
    assert "Erişim engellendi" in err
    assert "x.py" in err
    assert "Traceback" not in err


def test_usage_error_and_success_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    _argv(monkeypatch, "analyze")
    assert _exit_code() == 2
    _argv(monkeypatch, "analyze", str(FIXTURE), "--static")
    assert _exit_code() == 0


def test_workspace_cleans_up_on_keyboard_interrupt(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    seen: list[Path] = []
    with pytest.raises(KeyboardInterrupt), Workspace(tmp_path) as ws:
        seen.append(ws.root)
        assert ws.root.exists()
        raise KeyboardInterrupt
    assert not seen[0].exists()


def test_pricing_known_model() -> None:
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)
    assert estimate_cost("claude-sonnet-5-5", usage) == pytest.approx(2.00 + 5.00)
    assert estimate_cost("claude-fable-5-2", TokenUsage(input_tokens=1000)) == pytest.approx(0.008)
    assert set(PRICES_PER_MTOK) == {
        "claude-sonnet-5-5",
        "claude-opus-5-5",
        "claude-haiku-5-5",
        "claude-fable-5-2",
    }


def test_pricing_unknown_model() -> None:
    assert estimate_cost("gpt-yok", TokenUsage(input_tokens=5)) is None


def _use(monkeypatch: pytest.MonkeyPatch, llm: FakeLLM) -> None:
    monkeypatch.setattr(cli_main, "has_api_key", lambda: True)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: llm)


def _no_fixes() -> FakeLLM:
    return FakeLLM(lambda req: LLMUnitResponse(fixes=[]))


def test_verbose_shows_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _no_fixes())
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--verbose", "--no-verify"])
    assert result.exit_code == 0
    assert re.search(r"Token: giriş \d+, çıkış \d+ — tahmini maliyet \$\d\.\d{4}", result.output)


def test_verbose_unknown_model_no_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _no_fixes())
    args = ["analyze", str(FIXTURE), "--verbose", "--no-verify", "--model", "yok-model"]
    result = runner.invoke(app, args)
    assert "bilinmeyen model, maliyet hesaplanmadı" in result.output
    assert "tahmini maliyet" not in result.output


def test_smoke_analyze(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _no_fixes())
    result = runner.invoke(app, ["analyze", str(FIXTURE)])
    assert result.exit_code == 0
    assert "F401" in result.output
    assert "Toplam: 1 dosya" in result.output


def test_smoke_optimize_with_bench(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = make_slow_project(tmp_path)
    _use(monkeypatch, _llm(FAST))
    result = runner.invoke(app, ["optimize", str(calc), "--bench", str(tmp_path / "bench.py")])
    assert result.exit_code == 0
    assert "Profil" in result.output
    assert "✓ çıktı aynı, hızlanma ölçüldü" in result.output


def test_optimize_bench_outside_project_exit_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calc = make_slow_project(tmp_path / "proj")
    outside = tmp_path / "bench.py"
    outside.write_text("print(1)\n")
    _use(monkeypatch, _llm(FAST))
    result = runner.invoke(app, ["optimize", str(calc), "--bench", str(outside)])
    assert result.exit_code == 2
    assert "proje dışında" in result.output


def test_smoke_shrink(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = make_shrink_project(tmp_path)
    _use(monkeypatch, shrink_llm(SHORT))
    result = runner.invoke(app, ["shrink", str(calc)])
    assert result.exit_code == 0
    assert "Toplam: −6 satır" in result.output
    assert calc.read_text() == LONG


def test_smoke_translate_unknown_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = make_translate_project(tmp_path)
    llm = translate_fake()
    _use(monkeypatch, llm)
    result = runner.invoke(app, ["translate", str(src), "--to", "kotlin"])
    assert result.exit_code == 0
    assert "bilinmeyen hedef (kotlin), doğrulama yok" in result.output
    assert llm.count(TranslatedSegment) == 4


def test_smoke_explain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text(SMALL)
    _use(monkeypatch, FakeLLM(by_schema={FileExplanation: _whole}))
    result = runner.invoke(app, ["explain", str(src)])
    assert result.exit_code == 0
    assert "Toplama yapar" in result.output
    assert "iki sayiyi toplar" in result.output


def test_readme_commands_exist() -> None:
    text = README.read_text(encoding="utf-8")
    mentioned = set(re.findall(r"(?<!mypy )mytool (\w+)", text))
    assert mentioned == set(COMMANDS)
    helped = runner.invoke(app, ["--help"]).output
    for command in mentioned:
        assert re.search(rf"^\W*{command}\b", helped, re.MULTILINE)


def test_readme_flags_exist() -> None:
    text = README.read_text(encoding="utf-8")
    helps = "".join(runner.invoke(app, [name, "--help"]).output for name in COMMANDS)
    flags = set(re.findall(r"`(--[a-z-]+)", text)) - {"--help", "--version"}
    assert {f for f in flags if f not in helps} == set()
