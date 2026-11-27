import json
from pathlib import Path

import pytest
from fakes import FakeLLM, Result
from typer.testing import CliRunner

from mytool.cli import main as cli_main
from mytool.cli.main import app
from mytool.core.config import Config
from mytool.core.llm import LLMError
from mytool.core.models import FileExplanation, UnitExplanation
from mytool.core.pipeline import explain

runner = CliRunner()
SMALL = "def add(a, b):\n    return a + b\n"


def _whole(prompt: str) -> Result:
    return FileExplanation(
        summary="Toplama yapar",
        units=[UnitExplanation(name="add", purpose="iki sayiyi toplar", notes=["tam sayi"])],
    )


def _unit(prompt: str) -> Result:
    name = next(line for line in prompt.splitlines() if line.startswith("Birim: "))[7:]
    return UnitExplanation(name="yanlis", purpose=f"{name} ne yapar", notes=[])


def _summary(prompt: str) -> Result:
    return FileExplanation(summary="Birlesik ozet", units=[])


def _large_file(tmp_path: Path, functions: int = 30) -> Path:
    body = "".join(
        f"def f{i}(x):\n" + "".join(f"    x += {k}\n" for k in range(12)) + "    return x\n\n\n"
        for i in range(functions)
    )
    path = tmp_path / "big.py"
    path.write_text(body + "class K:\n    def m(self):\n        return 1\n")
    assert len(path.read_text().splitlines()) > 400
    return path


def test_small_file_single_call(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text(SMALL)
    llm = FakeLLM(by_schema={FileExplanation: _whole})
    result = explain(src, Config(), llm)
    assert len(llm.calls) == 1
    assert "1 | def add" in llm.calls[0][2]
    assert result.explanation is not None
    assert result.explanation.units[0].name == "add"
    assert result.usage.input_tokens == 10
    assert result.errors == []


def test_large_file_per_unit_and_summary(tmp_path: Path) -> None:
    src = _large_file(tmp_path)
    llm = FakeLLM(by_schema={UnitExplanation: _unit, FileExplanation: _summary})
    result = explain(src, Config(), llm)
    assert llm.count(UnitExplanation) == 31  # 30 functions + class K (its method is inside)
    assert llm.count(FileExplanation) == 1
    assert "Birimler:" in llm.calls[-1][2]
    assert "f0: f0 ne yapar" in llm.calls[-1][2]
    assert result.explanation is not None
    names = [u.name for u in result.explanation.units]
    assert names[0] == "f0"
    assert names[-1] == "K"
    assert result.explanation.summary == "Birlesik ozet"
    assert result.usage.input_tokens == 320


def test_large_file_nonfatal_unit_error_is_warning(tmp_path: Path) -> None:
    src = _large_file(tmp_path)

    def unit(prompt: str) -> Result:
        if "Birim: f3\n" in prompt:
            return LLMError("model isteği reddetti")
        return _unit(prompt)

    llm = FakeLLM(by_schema={UnitExplanation: unit, FileExplanation: _summary})
    result = explain(src, Config(), llm)
    assert result.errors == []
    assert len(result.warnings) == 1
    assert result.explanation is not None
    assert "f3" not in [u.name for u in result.explanation.units]


def test_denied_file_no_llm_call(tmp_path: Path) -> None:
    src = tmp_path / "my_secret.py"
    src.write_text(SMALL)
    llm = FakeLLM(by_schema={FileExplanation: _whole})
    result = explain(src, Config(), llm)
    assert llm.calls == []
    assert result.explanation is None
    assert "deny-list" in result.errors[0]


def test_fatal_error_recorded(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text(SMALL)
    llm = FakeLLM(by_schema={FileExplanation: lambda p: LLMError("hız sınırı", fatal=True)})
    result = explain(src, Config(), llm)
    assert result.explanation is None
    assert result.errors == ["a.py: hız sınırı"]


@pytest.fixture
def llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeLLM(by_schema={FileExplanation: _whole})
    monkeypatch.setattr(cli_main, "has_api_key", lambda: True)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: llm)


@pytest.mark.usefixtures("llm_env")
def test_cli_render(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text(SMALL)
    result = runner.invoke(app, ["explain", str(src), "--verbose"])
    assert result.exit_code == 0
    assert "Toplama yapar" in result.output
    assert "iki sayiyi toplar" in result.output
    assert "• tam sayi" in result.output
    assert "Token: giriş 10" in result.output


@pytest.mark.usefixtures("llm_env")
def test_cli_json(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text(SMALL)
    result = runner.invoke(app, ["explain", str(src), "--json"])
    data = json.loads(result.stdout)
    assert data["explanation"]["summary"] == "Toplama yapar"
    assert data["errors"] == []


def test_cli_missing_key_exit_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli_main, "has_api_key", lambda: False)
    src = tmp_path / "a.py"
    src.write_text(SMALL)
    result = runner.invoke(app, ["explain", str(src)])
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in result.output


@pytest.mark.usefixtures("llm_env")
def test_cli_directory_exit_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["explain", str(tmp_path)])
    assert result.exit_code == 2
    assert "dosya ver" in result.output


@pytest.mark.usefixtures("llm_env")
def test_cli_errors_exit_3(tmp_path: Path) -> None:
    src = tmp_path / "my_secret.py"
    src.write_text(SMALL)
    result = runner.invoke(app, ["explain", str(src)])
    assert result.exit_code == 3
    assert "deny-list" in result.output
