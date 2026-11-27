import json
from pathlib import Path

import pytest
from fakes import FakeLLM, ParsedRequest
from typer.testing import CliRunner

from mytool.cli import main as cli_main
from mytool.cli.main import app
from mytool.core.apply import fix_eligible
from mytool.core.config import Config
from mytool.core.llm import LLMFix, LLMUnitResponse
from mytool.core.models import AnalysisRun, Category, Suggestion, VerifyMethod, VerifyStatus
from mytool.core.pipeline import shrink

runner = CliRunner()
LONG = """def total(items):
    result = 0
    for item in items:
        if item > 0:
            result = result + item
        else:
            result = result + 0
    return result
"""
BODY = LONG.split("\n", 1)[1]
SHORT = "    return sum(item for item in items if item > 0)\n"
TEST = "from calc import total\n\n\ndef test_total():\n    assert total([1, -2, 3]) == 4\n"


def make_project(root: Path, source: str = LONG, tests: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0"\n')
    calc = root / "calc.py"
    calc.write_text(source)
    if tests:
        (root / "tests").mkdir()
        (root / "tests" / "test_calc.py").write_text(TEST)
    return calc


def _llm(replacement: str, original: str = BODY) -> FakeLLM:
    def handler(req: ParsedRequest) -> LLMUnitResponse:
        fix = LLMFix(
            finding_ids=[],
            category=Category.STYLE,
            explanation="dongu sum ile kisaltildi",
            original=original,
            replacement=replacement,
        )
        return LLMUnitResponse(fixes=[fix])

    return FakeLLM(handler)


def _only(run: AnalysisRun) -> Suggestion:
    (report,) = run.reports
    (suggestion,) = report.suggestions
    return suggestion


def test_shorter_equivalent_passes_with_tests(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    run = shrink(calc, Config(), _llm(SHORT))
    suggestion = _only(run)
    assert run.errors == []
    assert suggestion.category == Category.SHRINK
    assert suggestion.patch is not None
    assert suggestion.patch.line_delta == -6
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.PASSED
    assert suggestion.verification.method == VerifyMethod.PYTEST
    assert fix_eligible(suggestion)
    assert calc.read_text() == LONG


@pytest.mark.parametrize(
    ("replacement", "reason"),
    [
        (BODY, "daha kısa değil"),
        (SHORT.rstrip("\n") + "  # " + "x" * 100 + "\n", "karakterden uzun"),
    ],
)
def test_guards_drop_suggestion_with_warning(tmp_path: Path, replacement: str, reason: str) -> None:
    calc = make_project(tmp_path)
    run = shrink(calc, Config(), _llm(replacement))
    assert run.reports[0].suggestions == []
    assert any(reason in w for w in run.warnings)


def test_signature_change_dropped(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    run = shrink(calc, Config(), _llm("def total(values):\n" + SHORT, original=LONG))
    assert run.reports[0].suggestions == []
    assert any("imza değişti" in w for w in run.warnings)


def test_test_breaking_version_failed_and_hidden(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    run = shrink(calc, Config(), _llm("    return sum(items)\n"))
    suggestion = _only(run)
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.FAILED
    assert run.reports[0].visible_suggestions() == []


def test_no_tests_is_syntax_only_not_fix_eligible(tmp_path: Path) -> None:
    calc = make_project(tmp_path, tests=False)
    suggestion = _only(shrink(calc, Config(), _llm(SHORT)))
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.PASSED
    assert suggestion.verification.method == VerifyMethod.SYNTAX
    assert not fix_eligible(suggestion)


def test_candidates_longest_first_min_lines_and_limit(tmp_path: Path) -> None:
    longer = LONG.replace("def total", "def longer").replace(
        "    return result\n", "    extra = 1\n    return result\n"
    )
    tiny = "def tiny():\n    return 1\n"
    calc = make_project(tmp_path, LONG + "\n\n" + longer + "\n\n" + tiny)
    llm = FakeLLM(lambda req: LLMUnitResponse(fixes=[]))
    run = shrink(calc, Config(), llm)
    assert [r.unit_name for r in llm.requests] == ["longer", "total"]
    assert run.errors == []
    limited = FakeLLM(lambda req: LLMUnitResponse(fixes=[]))
    shrink(calc, Config(max_findings=1), limited)
    assert [r.unit_name for r in limited.requests] == ["longer"]


@pytest.fixture(autouse=True)
def _fake_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path_factory.mktemp("home"))
    monkeypatch.setattr(cli_main, "has_api_key", lambda: True)


def test_cli_shows_savings_and_total(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calc = make_project(tmp_path)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: _llm(SHORT))
    result = runner.invoke(app, ["shrink", str(calc)])
    assert result.exit_code == 0
    assert "−6 satır" in result.output
    assert "Toplam: −6 satır (8 → 2)" in result.output
    assert "✓ testler geçti" in result.output


def test_cli_fix_applies_and_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calc = make_project(tmp_path)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: _llm(SHORT))
    result = runner.invoke(app, ["shrink", str(calc), "--fix", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert set(data) == {"run", "apply"}
    assert data["apply"]["outcomes"][0]["applied"] is True
    assert calc.read_text() == "def total(items):\n" + SHORT


def test_cli_unverified_not_auto_applied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calc = make_project(tmp_path, tests=False)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: _llm(SHORT))
    result = runner.invoke(app, ["shrink", str(calc), "--fix"])
    assert "doğrulanamadı" in result.output
    assert "0 öneri uygulandı" in result.output
    assert calc.read_text() == LONG


def test_cli_rejects_directory(tmp_path: Path) -> None:
    assert runner.invoke(app, ["shrink", str(tmp_path)]).exit_code == 2
