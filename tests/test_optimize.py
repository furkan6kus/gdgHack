import json
from pathlib import Path

import pytest
from fakes import FakeLLM, ParsedRequest
from test_profiling import SLOW, make_project
from typer.testing import CliRunner

from mytool.cli import main as cli_main
from mytool.cli.main import app
from mytool.core.config import Config
from mytool.core.llm import LLMError, LLMFix, LLMUnitResponse
from mytool.core.models import AnalysisRun, Category, Suggestion, VerifyMethod, VerifyStatus
from mytool.core.pipeline import NO_PROFILE_DATA, optimize

runner = CliRunner()
BODY = (
    "    total = 0\n    for i in range(n):\n        for j in range(n):\n"
    "            total += i * j\n    return total\n"
)
FAST = "    return (n * (n - 1) // 2) ** 2\n"
WRONG = "    return (n * (n - 1) // 2) ** 2 + 1\n"
SLOWER = (
    "    total = 0\n    for _ in range(3):\n        for i in range(n):\n"
    "            for j in range(n):\n                total += i * j\n    return total // 3\n"
)


def _llm(replacement: str, original: str = BODY) -> FakeLLM:
    def handler(req: ParsedRequest) -> LLMUnitResponse:
        fix = LLMFix(
            finding_ids=[],
            category=Category.STYLE,
            explanation="ic ice dongu kapali formule cevrildi",
            original=original,
            replacement=replacement,
        )
        return LLMUnitResponse(fixes=[fix])

    return FakeLLM(handler)


def _only(run: AnalysisRun) -> Suggestion:
    (report,) = run.reports
    (suggestion,) = report.suggestions
    return suggestion


def test_fast_equivalent_patch_passes_with_benchmark(tmp_path: Path) -> None:
    calc = make_project(tmp_path)  # workload: the file itself (main guard)
    llm = _llm(FAST)
    run = optimize(calc, Config(), llm)
    suggestion = _only(run)
    assert run.errors == []
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.PASSED
    assert suggestion.verification.method == VerifyMethod.BENCHMARK
    assert suggestion.category == Category.PERF
    assert suggestion.benchmark is not None
    assert suggestion.benchmark.speedup > 1.05
    assert run.profile[0].function == "work"
    assert len(llm.requests) == 1
    assert "tottime=" in llm.calls[0][2]
    assert calc.read_text() == SLOW


def test_bench_script_workload(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    calc.write_text(SLOW.split("\n\nif __name__")[0] + "\n")  # no main guard
    run = optimize(calc, Config(), _llm(FAST), tmp_path / "bench.py")
    suggestion = _only(run)
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.PASSED
    assert suggestion.benchmark is not None


def test_changed_output_rejected(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    run = optimize(calc, Config(), _llm(WRONG))
    suggestion = _only(run)
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.FAILED
    assert "çıktı değişti" in suggestion.verification.detail
    assert run.reports[0].visible_suggestions() == []


def test_not_faster_rejected(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    run = optimize(calc, Config(), _llm(SLOWER))
    suggestion = _only(run)
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.FAILED
    assert "ölçülebilir hızlanma yok" in suggestion.verification.detail
    assert suggestion.benchmark is not None
    assert suggestion.benchmark.speedup < 1.05


def test_no_workload_no_llm_call(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    calc.write_text(SLOW.split("\n\nif __name__")[0] + "\n")
    llm = _llm(FAST)
    run = optimize(calc, Config(), llm)
    assert run.errors == [NO_PROFILE_DATA]
    assert llm.calls == []


def test_bench_outside_project_is_error(tmp_path: Path) -> None:
    calc = make_project(tmp_path / "proj")
    outside = tmp_path / "bench_out.py"
    outside.write_text("print(1)\n")
    llm = _llm(FAST)
    run = optimize(calc, Config(), llm, outside)
    assert "proje dışında" in run.errors[0]
    assert llm.calls == []


def test_denied_file_no_llm_call(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    secret = tmp_path / "my_secret.py"
    secret.write_text(calc.read_text())
    llm = _llm(FAST)
    run = optimize(secret, Config(), llm)
    assert "deny-list" in run.errors[0]
    assert llm.calls == []


def test_no_verify_skips_measurement(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    run = optimize(calc, Config(verify=False), _llm(FAST))
    suggestion = _only(run)
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.SKIPPED
    assert suggestion.benchmark is None
    assert run.profile


def test_fatal_llm_error_recorded(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    llm = FakeLLM(lambda req: LLMError("API anahtarı geçersiz", fatal=True))
    run = optimize(calc, Config(verify=False), llm)
    assert run.errors == ["calc.py: API anahtarı geçersiz"]


def test_project_tests_are_the_workload(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    calc.write_text("import time\n\n\ndef work(n):\n    time.sleep(0.4)\n    return n * 2\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(
        "from calc import work\n\n\ndef test_work():\n    assert work(5) == 10\n"
    )
    run = optimize(calc, Config(), _llm("", original="    time.sleep(0.4)\n"))
    suggestion = _only(run)
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.PASSED
    assert suggestion.verification.method == VerifyMethod.PYTEST
    assert suggestion.benchmark is not None
    assert suggestion.benchmark.speedup > 1.05


@pytest.fixture
def llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "has_api_key", lambda: True)
    monkeypatch.setattr(cli_main, "_make_llm", lambda cfg: _llm(FAST))


@pytest.fixture(autouse=True)
def _fake_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setattr(Path, "home", lambda: home)


@pytest.mark.usefixtures("llm_env")
def test_cli_fix_applies_benchmark_passed(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    result = runner.invoke(app, ["optimize", str(calc), "--fix"])
    assert result.exit_code == 0
    assert "Profil" in result.output
    assert "sonra" in result.output
    assert "önce" in result.output
    assert "1 öneri uygulandı" in result.output
    assert FAST in calc.read_text()


@pytest.mark.usefixtures("llm_env")
def test_cli_json_shape(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    result = runner.invoke(
        app, ["optimize", str(calc), "--json", "--bench", str(tmp_path / "bench.py")]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["apply"] is None
    assert data["run"]["profile"][0]["function"] == "work"
    suggestion = data["run"]["reports"][0]["suggestions"][0]
    assert suggestion["benchmark"]["runs"] == 3
    assert suggestion["verification"]["method"] == "benchmark"
    assert calc.read_text() == SLOW


@pytest.mark.usefixtures("llm_env")
def test_cli_no_workload_exit_3(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    calc.write_text(SLOW.split("\n\nif __name__")[0] + "\n")
    result = runner.invoke(app, ["optimize", str(calc)])
    assert result.exit_code == 3
    assert "profil verisi yok" in result.output


def test_cli_missing_key_exit_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli_main, "has_api_key", lambda: False)
    calc = make_project(tmp_path)
    result = runner.invoke(app, ["optimize", str(calc)])
    assert result.exit_code == 2


@pytest.mark.usefixtures("llm_env")
def test_cli_directory_and_missing_bench_exit_2(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    assert runner.invoke(app, ["optimize", str(tmp_path)]).exit_code == 2
    missing = runner.invoke(app, ["optimize", str(calc), "--bench", str(tmp_path / "yok.py")])
    assert missing.exit_code == 2
