import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fakes import FakeLLM
from typer.testing import CliRunner

from mytool.cli import main as cli_main
from mytool.cli.main import app
from mytool.core import translate as translate_mod
from mytool.core.config import Config
from mytool.core.languages.python import PythonPlugin
from mytool.core.llm import LLMError
from mytool.core.models import TranslatedSegment, TranslateResult, VerifyMethod, VerifyStatus
from mytool.core.translate import split_segments, translate

runner = CliRunner()
SRC = """import math

PI = 3.14


def alpha(x):
    return x + 1


def beta(y):
    return alpha(y) * 2


if __name__ == "__main__":
    print(beta(3))
"""
JS = {
    "(modül başı)": "const PI = 3.14;",
    "alpha": "function alpha(x) {\n  return x + 1;\n}",
    "beta": "function beta(y) {\n  return alpha(y) * 2;\n}",
    "(modül kodu)": "console.log(beta(3));",
}


def _label(prompt: str) -> str:
    return next(line for line in prompt.splitlines() if line.startswith("Bölüm: "))[7:]


def _fake(code_for: dict[str, str] | None = None) -> FakeLLM:
    table = code_for or JS
    return FakeLLM(
        by_schema={
            TranslatedSegment: lambda p: TranslatedSegment(code=table[_label(p)], notes=["not"])
        }
    )


def make_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0"\n')
    src = root / "app.py"
    src.write_text(SRC)
    return src


def _tool(monkeypatch: pytest.MonkeyPatch, stdout: str = "8\n") -> list[list[str]]:
    """Pretend node exists; python runs print '8', node runs return `stdout`."""
    calls: list[list[str]] = []

    def fake_run(argv: list[str], ws: object, timeout_s: float) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[0] == getattr(ws, "python", None):
            return subprocess.CompletedProcess(argv, 0, "8\n", "")
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    monkeypatch.setattr(shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(translate_mod, "_run_tool", fake_run)
    return calls


def test_split_segments_order() -> None:
    parts = split_segments(SRC, PythonPlugin().extract_units(SRC))
    assert [p.label for p in parts] == ["(modül başı)", "alpha", "beta", "(modül kodu)"]
    assert parts[0].code.startswith("import math")
    assert "PI = 3.14" in parts[0].code
    assert parts[1].code == "def alpha(x):\n    return x + 1\n"
    assert parts[3].code.startswith('if __name__ == "__main__":')
    assert "".join(p.code for p in parts).replace("\n", "") == SRC.replace("\n", "")


def test_one_call_per_segment_with_previous_names(tmp_path: Path) -> None:
    src = make_project(tmp_path)
    llm = _fake()
    result = translate(src, "kotlin", Config(), llm)
    assert len(llm.calls) == 4
    third = llm.calls[2][2]
    assert "def alpha(x):" in third
    assert "return x + 1" not in third
    assert "def alpha" not in llm.calls[1][2].split("Kod:")[0]
    assert [s.code for s in result.segments] == list(JS.values())
    assert result.output == "\n\n".join(JS.values()) + "\n"
    assert src.read_text() == SRC


def test_unknown_target_txt_skipped(tmp_path: Path) -> None:
    result = translate(make_project(tmp_path), "Kotlin", Config(), _fake())
    assert (result.target, result.extension) == ("kotlin", ".txt")
    assert result.verification is not None
    assert result.verification.status == VerifyStatus.SKIPPED


def test_typescript_has_no_checker(tmp_path: Path) -> None:
    result = translate(make_project(tmp_path), "TS", Config(), _fake())
    assert (result.target, result.extension) == ("typescript", ".ts")
    assert result.verification is not None
    assert result.verification.status == VerifyStatus.SKIPPED


def test_missing_toolchain_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = translate(make_project(tmp_path), "js", Config(), _fake())
    assert result.verification is not None
    assert result.verification.status == VerifyStatus.SKIPPED
    assert result.verification.detail == "node bulunamadı"
    assert result.output


def test_checker_failure_fails_and_drops_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_project(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        translate_mod,
        "_run_tool",
        lambda argv, ws, t: subprocess.CompletedProcess(argv, 1, "", "SyntaxError: bad"),
    )
    result = translate(src, "go", Config(), _fake())  # go: syntax check only
    assert result.verification is not None
    assert result.verification.status == VerifyStatus.FAILED
    assert result.verification.method == VerifyMethod.SYNTAX
    assert "SyntaxError: bad" in result.verification.detail
    assert result.output == ""
    assert result.segments == []
    assert not result.presentable


def test_compare_equal_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _tool(monkeypatch, stdout="8  \n\n")  # trailing whitespace is ignored
    result = translate(make_project(tmp_path), "javascript", Config(), _fake())
    assert result.verification is not None
    assert result.verification.status == VerifyStatus.PASSED
    assert result.verification.method == VerifyMethod.COMPARE
    assert len(calls) == 2


def test_compare_difference_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _tool(monkeypatch, stdout="9\n")
    result = translate(make_project(tmp_path), "js", Config(), _fake())
    assert result.verification is not None
    assert result.verification.status == VerifyStatus.FAILED
    assert result.verification.method == VerifyMethod.COMPARE
    assert "satır 1: beklenen '8', çıkan '9'" in result.verification.detail
    assert result.output == ""


def test_no_main_guard_uses_syntax_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = make_project(tmp_path)
    src.write_text(SRC.split("\n\nif __name__")[0] + "\n")
    calls = _tool(monkeypatch)
    table = {k: v for k, v in JS.items() if k != "(modül kodu)"}
    result = translate(src, "js", Config(), _fake(table))
    assert result.verification is not None
    assert result.verification.method == VerifyMethod.SYNTAX
    assert result.verification.status == VerifyStatus.PASSED
    assert calls[0][1] == "--check"


def test_no_verify_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _tool(monkeypatch)
    result = translate(make_project(tmp_path), "js", Config(verify=False), _fake())
    assert result.verification is not None
    assert result.verification.status == VerifyStatus.SKIPPED
    assert calls == []


def test_llm_error_recorded(tmp_path: Path) -> None:
    llm = FakeLLM(by_schema={TranslatedSegment: lambda p: LLMError("hız sınırı", fatal=True)})
    result = translate(make_project(tmp_path), "js", Config(), llm)
    assert result.errors == ["app.py: (modül başı): hız sınırı"]
    assert result.output == ""
    assert result.verification is None


@pytest.mark.skipif(not shutil.which("node"), reason="node yok")
def test_real_node_compare(tmp_path: Path) -> None:
    src = make_project(tmp_path)
    good = translate(src, "js", Config(), _fake())
    assert good.verification is not None
    assert good.verification.status == VerifyStatus.PASSED
    assert good.verification.method == VerifyMethod.COMPARE
    bad = translate(src, "js", Config(), _fake({**JS, "(modül kodu)": "console.log(beta(4));"}))
    assert bad.verification is not None
    assert bad.verification.status == VerifyStatus.FAILED
    broken = translate(src, "js", Config(), _fake({**JS, "alpha": "function alpha( {"}))
    assert broken.verification is not None
    assert broken.verification.status == VerifyStatus.FAILED


@pytest.fixture
def cli_env(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    monkeypatch.setattr(Path, "home", lambda: tmp_path_factory.mktemp("home"))
    monkeypatch.setattr(cli_main, "has_api_key", lambda: True)
    llm = _fake()
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: llm)
    return llm


def test_cli_renders_code_status_and_notes(
    tmp_path: Path, cli_env: FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_project(tmp_path)
    _tool(monkeypatch)
    result = runner.invoke(app, ["translate", str(src), "--to", "js"])
    assert result.exit_code == 0
    assert "function alpha" in result.output
    assert "✓ çıktı orijinalle aynı" in result.output
    assert "• not" in result.output
    assert src.read_text() == SRC
    assert sorted(p.name for p in tmp_path.iterdir()) == ["app.py", "pyproject.toml"]


def test_cli_failed_hides_code_exit_3(
    tmp_path: Path, cli_env: FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_project(tmp_path)
    _tool(monkeypatch, stdout="9\n")
    out = tmp_path / "out.js"
    result = runner.invoke(app, ["translate", str(src), "--to", "js", "--out", str(out)])
    assert result.exit_code == 3
    assert "function alpha" not in result.output
    assert "çeviri doğrulamada başarısız: çıktı orijinalden farklı" in result.output
    assert "beklenen" not in result.output
    assert not out.exists()
    verbose = runner.invoke(app, ["translate", str(src), "--to", "js", "--verbose"])
    assert "beklenen '8'" in verbose.output
    assert "function alpha" not in verbose.output


def test_cli_json_failed_has_no_code(
    tmp_path: Path, cli_env: FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_project(tmp_path)
    _tool(monkeypatch, stdout="9\n")
    result = runner.invoke(app, ["translate", str(src), "--to", "js", "--json"])
    assert result.exit_code == 3
    data = TranslateResult.model_validate(json.loads(result.stdout))
    assert data.output == ""
    assert data.segments == []
    assert data.verification is not None
    assert data.verification.status == VerifyStatus.FAILED


def test_cli_out_writes_refuses_and_forces(
    tmp_path: Path, cli_env: FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_project(tmp_path)
    _tool(monkeypatch)
    out = tmp_path / "out.js"
    args = ["translate", str(src), "--to", "js", "--out", str(out)]
    assert runner.invoke(app, args).exit_code == 0
    first = out.read_text(encoding="utf-8")
    assert "function beta" in first

    calls_before = len(cli_env.calls)
    out.write_text("old\n")
    refused = runner.invoke(app, args)
    assert refused.exit_code == 2
    assert out.read_text() == "old\n"
    assert len(cli_env.calls) == calls_before

    forced = runner.invoke(app, [*args, "--force"])
    assert forced.exit_code == 0
    assert out.read_text(encoding="utf-8") == first
    (backup,) = (tmp_path / ".mytool" / "backup").glob("*/out.js")
    assert backup.read_text() == "old\n"
    assert src.read_text() == SRC


def test_cli_requirements(tmp_path: Path, cli_env: FakeLLM) -> None:
    src = make_project(tmp_path)
    assert runner.invoke(app, ["translate", str(tmp_path), "--to", "js"]).exit_code == 2
    same = runner.invoke(app, ["translate", str(src), "--to", "js", "--out", str(src)])
    assert same.exit_code == 2
    assert src.read_text() == SRC


def test_cli_missing_key_exit_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "has_api_key", lambda: False)
    result = runner.invoke(app, ["translate", str(make_project(tmp_path)), "--to", "js"])
    assert result.exit_code == 2
