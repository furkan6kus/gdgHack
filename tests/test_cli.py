import json
import re
from pathlib import Path

from typer.testing import CliRunner

from mytool import __version__
from mytool.cli.main import app

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


def test_placeholder_message(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    assert "Faz 2" in result.output


def test_json_output(tmp_path: Path) -> None:
    result = runner.invoke(app, ["shrink", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"status": "not_implemented", "command": "shrink"}
