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
from mytool.core.models import AnalysisRun, Category, Finding, TokenUsage
from mytool.core.pipeline import analyze

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"
runner = CliRunner()
COMMANDS = ["analyze", "optimize", "shrink", "translate", "explain"]


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
    assert data["reports"][0]["findings"]
    assert {f["rule"] for f in data["reports"][0]["findings"]} >= {"F401"}


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
    result = runner.invoke(app, ["analyze", str(FIXTURE)])
    assert result.exit_code == 0
    assert "Anthropic API'ye gönderilir" in result.output
    assert "kullanilmayan import kaldirilmali" in result.output
    assert "⚠ doğrulanmadı" in result.output
    assert any(line.strip() == "-import os" for line in result.output.splitlines())
    assert "Token:" not in result.output


@pytest.mark.usefixtures("llm_env")
def test_diff_hides_explanations() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--diff"])
    assert result.exit_code == 0
    assert "-import os" in result.output
    assert "kullanilmayan" not in result.output
    assert "F401" not in result.output


@pytest.mark.usefixtures("llm_env")
def test_verbose_shows_tokens() -> None:
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--verbose"])
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
    result = runner.invoke(app, ["analyze", str(FIXTURE), "--json"])
    data = json.loads(result.stdout)
    assert data["reports"][0]["suggestions"][0]["verification"] is None
