import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mytool import __version__
from mytool.cli import main as cli_main
from mytool.cli.main import app
from mytool.core.analyzers.base import AnalyzerError
from mytool.core.config import Config
from mytool.core.models import Finding, Report
from mytool.core.pipeline import analyze_static

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
    data = json.loads(result.output)
    assert data[0]["findings"]
    assert {f["rule"] for f in data[0]["findings"]} >= {"F401"}


def test_analyzer_error_exit_3(monkeypatch: pytest.MonkeyPatch) -> None:
    class Failing:
        name = "failing"
        languages: tuple[str, ...] = ("python",)

        def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
            raise AnalyzerError("boom")

    def fake(target: Path, cfg: Config) -> list[Report]:
        return analyze_static(target, cfg, [Failing()])

    monkeypatch.setattr(cli_main, "analyze_static", fake)
    result = runner.invoke(app, ["analyze", str(FIXTURE)])
    assert result.exit_code == 3
    assert "failing: boom" in result.output
    assert "Traceback" not in result.output


def test_json_output(tmp_path: Path) -> None:
    result = runner.invoke(app, ["shrink", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"status": "not_implemented", "command": "shrink"}
