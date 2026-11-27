import hashlib
import io
import json
import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mytool import __version__
from mytool.cli import main as cli_main
from mytool.cli.main import app
from mytool.core.analyzers.base import AnalyzerError
from mytool.core.config import Config
from mytool.core.llm import LLMClient, LLMFix, LLMRequest, LLMUnitResponse
from mytool.core.models import (
    AnalysisRun,
    Category,
    Finding,
    LineRange,
    Patch,
    Report,
    Suggestion,
    TokenUsage,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.pipeline import analyze

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"
runner = CliRunner()
COMMANDS = ["analyze", "optimize", "shrink", "translate", "explain"]


@pytest.fixture(autouse=True)
def _fake_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in COMMANDS:
        assert re.search(rf"^\W*{command}\b", result.output, re.MULTILINE)


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_missing_path_exits_2() -> None:
    result = runner.invoke(app, ["analyze", "no_such_file.py"])
    assert result.exit_code == 2
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_translate_requires_to(tmp_path: Path) -> None:
    result = runner.invoke(app, ["translate", str(tmp_path)])
    assert result.exit_code != 0


def test_analyze_fixture() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE)])
    assert result.exit_code == 0
    assert "[HATA]" in result.output
    assert "F401" in result.output
    assert "Toplam: 1 dosya" in result.output


def test_analyze_empty_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    assert "Bulgu yok" in result.output


def test_analyze_json() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["apply"] is None
    assert data["run"]["reports"][0]["findings"]
    assert {f["rule"] for f in data["run"]["reports"][0]["findings"]} >= {"F401"}


def test_analyzer_error_exit_3(monkeypatch: pytest.MonkeyPatch) -> None:
    class Failing:
        name = "failing"
        languages: tuple[str, ...] = ("python",)

        def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
            raise AnalyzerError("boom")

    def fake(target: Path, cfg: Config, llm: LLMClient | None) -> AnalysisRun:
        return analyze(target, cfg, llm, [Failing()])

    monkeypatch.setattr(cli_main, "analyze", fake)
    result = runner.invoke(app, ["analyze", str(FIXTURE)])
    assert result.exit_code == 3
    assert "failing: boom" in result.output
    assert "Traceback" not in result.output


def test_json_output(tmp_path: Path) -> None:
    result = runner.invoke(app, ["shrink", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"status": "not_implemented", "command": "shrink"}


def test_truncation_exit_0() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--max-findings", "1"])
    assert result.exit_code == 0
    assert "sınır nedeniyle gösterilmedi" in result.output


def test_force_utf8_reconfigures(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", buf)
    cli_main._force_utf8()
    assert buf.encoding == "utf-8"


class FakeLLM:
    calls = 0

    def suggest(self, req: LLMRequest) -> tuple[LLMUnitResponse, TokenUsage]:
        FakeLLM.calls += 1
        fixes = [
            LLMFix(
                finding_ids=[f.id],
                category=Category.STYLE,
                explanation="kullanilmayan import kaldirilmali",
                original="import os\n",
                replacement="",
            )
            for f in req.findings
            if f.rule == "F401"
        ]
        return LLMUnitResponse(fixes=fixes), TokenUsage(input_tokens=123, output_tokens=45)


@pytest.fixture
def llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeLLM.calls = 0
    monkeypatch.setattr(cli_main, "has_api_key", lambda: True)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: FakeLLM())


def test_no_api_key_falls_back_to_static(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "has_api_key", lambda: False)
    result = runner.invoke(app, ["analyze", str(FIXTURE)])
    assert result.exit_code == 0
    assert "ANTHROPIC_API_KEY tanımlı değil" in result.output
    assert "F401" in result.output


@pytest.mark.usefixtures("llm_env")
def test_llm_suggestions_rendered() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--no-verify"])
    assert result.exit_code == 0
    assert "Anthropic API'ye gönderilir" in result.output
    assert "kullanilmayan import kaldirilmali" in result.output
    assert "⚠ doğrulanmadı (--no-verify)" in result.output
    assert any(line.strip() == "-import os" for line in result.output.splitlines())
    assert "Token:" not in result.output


@pytest.mark.usefixtures("llm_env")
def test_diff_hides_explanations() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--diff", "--no-verify"])
    assert result.exit_code == 0
    assert "-import os" in result.output
    assert "kullanilmayan" not in result.output
    assert "F401" not in result.output


@pytest.mark.usefixtures("llm_env")
def test_verbose_shows_tokens() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--verbose", "--no-verify"])
    assert "Token: giriş" in result.output
    assert "çıkış" in result.output


@pytest.mark.usefixtures("llm_env")
def test_static_flag_never_calls_llm() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--static"])
    assert result.exit_code == 0
    assert FakeLLM.calls == 0
    assert "kullanilmayan" not in result.output
    assert "Anthropic API" not in result.output


@pytest.mark.usefixtures("llm_env")
def test_json_includes_suggestions() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--json", "--no-verify"])
    data = json.loads(result.stdout)
    assert data["run"]["reports"][0]["suggestions"][0]["verification"]["status"] == "skipped"


class ScriptedLLM:
    """Fix for the first finding of every request: replace original with replacement."""

    def __init__(self, original: str, replacement: str) -> None:
        self.original, self.replacement = original, replacement

    def suggest(self, req: LLMRequest) -> tuple[LLMUnitResponse, TokenUsage]:
        fix = LLMFix(
            finding_ids=[req.findings[0].id],
            category=Category.STYLE,
            explanation="açıklama",
            original=self.original,
            replacement=self.replacement,
        )
        return LLMUnitResponse(fixes=[fix]), TokenUsage()


def _scripted(monkeypatch: pytest.MonkeyPatch, original: str, replacement: str) -> None:
    monkeypatch.setattr(cli_main, "has_api_key", lambda: True)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: ScriptedLLM(original, replacement))


def _tmp_project(root: Path) -> Path:
    (root / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0"\n')
    calc = root / "calc.py"
    calc.write_text("import os\n\n\ndef add(a, b):\n    return a + b\n")
    return calc


def test_verify_notice_printed_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _scripted(monkeypatch, "import os\n", "")
    first = runner.invoke(app, ["analyze", str(calc)])
    second = runner.invoke(app, ["analyze", str(calc)])
    assert "sandbox yok" in first.output
    assert "sandbox yok" not in second.output
    assert (Path.home() / ".mytool" / "verify-notice").exists()
    assert "yalnız sözdizimi: test yok" in first.output


def test_no_notice_with_no_verify(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _scripted(monkeypatch, "import os\n", "")
    result = runner.invoke(app, ["analyze", str(calc), "--no-verify"])
    assert "sandbox yok" not in result.output
    assert not (Path.home() / ".mytool" / "verify-notice").exists()


def test_failed_suggestions_hidden_with_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calc = _tmp_project(tmp_path)
    _scripted(monkeypatch, "import os\n", "import os(\n")
    result = runner.invoke(app, ["analyze", str(calc)])
    assert result.exit_code == 0
    assert "1 öneri doğrulamada başarısız olduğu için gizlendi" in result.output
    assert "Öneri:" not in result.output
    verbose = runner.invoke(app, ["analyze", str(calc), "--verbose"])
    assert "satır 1" in verbose.output.split("gizlendi", 1)[1]


def test_warnings_do_not_cause_exit_3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _scripted(monkeypatch, "yok böyle bir satır\n", "")
    result = runner.invoke(app, ["analyze", str(calc)])
    assert result.exit_code == 0
    assert "patch eşleşmedi" in result.output
    assert "yalnız açıklama" in result.output


def test_timeout_option_accepted() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--timeout", "30"])
    assert result.exit_code == 0


ORIGINAL = "import os\n\n\ndef add(a, b):\n    return a + b\n"


def _patch_analyze(
    monkeypatch: pytest.MonkeyPatch, calc: Path, method: VerifyMethod = VerifyMethod.PYTEST
) -> None:
    patch = Patch(file=calc, original="import os\n", new="", lines=LineRange(start=1, end=1))
    suggestion = Suggestion(
        id="s1",
        finding_ids=[],
        category=Category.STYLE,
        explanation="kullanilmayan import",
        patch=patch,
        verification=VerificationResult(status=VerifyStatus.PASSED, method=method),
    )
    report = Report(
        file=calc,
        suggestions=[suggestion],
        content_sha256=hashlib.sha256(calc.read_bytes()).hexdigest(),
    )
    run = AnalysisRun(reports=[report])
    monkeypatch.setattr(cli_main, "analyze", lambda target, cfg, llm: run.model_copy(deep=True))


def _interactive(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: value)


def test_fix_applies_eligible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    result = runner.invoke(app, ["analyze", str(calc), "--fix", "--static"])
    assert "1 öneri uygulandı. Yedek:" in result.output
    assert not calc.read_text().startswith("import os")


def test_fix_skips_syntax_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc, VerifyMethod.SYNTAX)
    result = runner.invoke(app, ["analyze", str(calc), "--fix", "--static"])
    assert "0 öneri uygulandı" in result.output
    assert "yalnız sözdizimiyle doğrulandığı için" in result.output
    assert calc.read_text() == ORIGINAL


def test_fix_no_verify_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    result = runner.invoke(app, ["analyze", str(calc), "--fix", "--no-verify", "--static"])
    assert "doğrulama gerektirir" in result.output
    assert calc.read_text() == ORIGINAL


def test_interactive_all(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    _interactive(monkeypatch, True)
    result = runner.invoke(app, ["analyze", str(calc), "--static"], input="a\n")
    assert "1 öneri uygulandı" in result.output
    assert not calc.read_text().startswith("import os")


def test_interactive_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    _interactive(monkeypatch, True)
    result = runner.invoke(app, ["analyze", str(calc), "--static"], input="h\n")
    assert "uygulandı" not in result.output
    assert calc.read_text() == ORIGINAL


def test_interactive_select(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    _interactive(monkeypatch, True)
    no = runner.invoke(app, ["analyze", str(calc), "--static"], input="s\nn\n")
    assert "uygulansın mı?" in no.output
    assert calc.read_text() == ORIGINAL
    yes = runner.invoke(app, ["analyze", str(calc), "--static"], input="s\ny\n")
    assert "1 öneri uygulandı" in yes.output


def test_non_interactive_no_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    _interactive(monkeypatch, False)
    result = runner.invoke(app, ["analyze", str(calc), "--static"])
    assert "Uygula?" not in result.output
    assert calc.read_text() == ORIGINAL


def test_json_fix_has_apply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    result = runner.invoke(app, ["analyze", str(calc), "--json", "--fix", "--static"])
    data = json.loads(result.stdout)
    assert data["apply"]["outcomes"][0]["applied"] is True


def test_undo_yes_restores(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    runner.invoke(app, ["analyze", str(calc), "--fix", "--static"])
    result = runner.invoke(app, ["undo", str(tmp_path), "--yes"])
    assert result.exit_code == 0
    assert calc.read_text() == ORIGINAL


def test_undo_non_tty_needs_yes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calc = _tmp_project(tmp_path)
    _patch_analyze(monkeypatch, calc)
    runner.invoke(app, ["analyze", str(calc), "--fix", "--static"])
    _interactive(monkeypatch, False)
    result = runner.invoke(app, ["undo", str(tmp_path)])
    assert result.exit_code == 2
    assert not calc.read_text().startswith("import os")


def test_undo_no_backup(tmp_path: Path) -> None:
    _tmp_project(tmp_path)
    result = runner.invoke(app, ["undo", str(tmp_path), "--yes"])
    assert result.exit_code == 1
