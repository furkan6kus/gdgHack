from collections.abc import Callable
from pathlib import Path

from mytool.core.analyzers.base import AnalyzerError
from mytool.core.config import Config
from mytool.core.llm import LLMError, LLMFix, LLMRequest, LLMUnitResponse
from mytool.core.models import Category, Finding, LineRange, Severity, TokenUsage
from mytool.core.pipeline import analyze, analyze_static, collect_files

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"


def _finding(
    file: Path, line: int, severity: Severity = Severity.INFO, rule: str = "X1"
) -> Finding:
    return Finding(
        id=f"f-{rule}-{line}",
        tool="fake",
        file=file,
        lines=LineRange(start=line, end=line),
        severity=severity,
        rule=rule,
        message="m",
        category=Category.BUG,
    )


class FakeAnalyzer:
    name = "fake"
    languages: tuple[str, ...] = ("python",)

    def __init__(self, findings: list[Finding]) -> None:
        self._findings = findings

    def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
        return self._findings


class FailingAnalyzer:
    name = "failing"
    languages: tuple[str, ...] = ("python",)

    def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
        raise AnalyzerError("boom")


def test_collect_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / ".env").write_text("A=1")
    (tmp_path / "secret_keys.py").write_text("k = 1\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("y = 1\n")
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "b.py").write_text("z = 1\n")
    files, skipped = collect_files(tmp_path, Config())
    assert files == [tmp_path / "a.py", sub / "b.py"]
    assert skipped == [f"{tmp_path / 'secret_keys.py'}: deny-list"]


def test_collect_single_file() -> None:
    files, skipped = collect_files(FIXTURE, Config())
    assert files == [FIXTURE]
    assert skipped == []


def test_symbol_assignment() -> None:
    fake = FakeAnalyzer([_finding(FIXTURE, 16), _finding(FIXTURE, 1, rule="X2")])
    (report,) = analyze_static(FIXTURE, Config(), [fake]).reports
    by_rule = {f.rule: f.symbol for f in report.findings}
    assert by_rule == {"X1": "Greeter.hello.inner", "X2": None}


def test_truncation_orders_by_severity(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("x = 1\n")
    findings = [
        _finding(a, 1, Severity.INFO, "I"),
        _finding(a, 1, Severity.ERROR, "E"),
        _finding(a, 1, Severity.WARNING, "W"),
    ]
    run = analyze_static(a, Config(max_findings=2), [FakeAnalyzer(findings)])
    (report,) = run.reports
    assert {f.rule for f in report.findings} == {"E", "W"}
    assert run.truncated == 1
    assert run.errors == []


def test_analyzer_error_captured_and_clean_files_reported(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("x = 1\n")
    run = analyze_static(a, Config(), [FailingAnalyzer()])
    assert run.reports[0].findings == []
    assert run.errors == ["failing: boom"]


class FakeLLM:
    """Calls handler(req); an Exception result is raised."""

    def __init__(self, handler: Callable[[LLMRequest], LLMUnitResponse | Exception]) -> None:
        self.handler = handler
        self.requests: list[LLMRequest] = []

    def suggest(self, req: LLMRequest) -> tuple[LLMUnitResponse, TokenUsage]:
        self.requests.append(req)
        result = self.handler(req)
        if isinstance(result, Exception):
            raise result
        return result, TokenUsage(input_tokens=10, output_tokens=2)


def _fix(ids: list[str], original: str = "", replacement: str = "") -> LLMFix:
    return LLMFix(
        finding_ids=ids,
        category=Category.BUG,
        explanation="açıklama",
        original=original,
        replacement=replacement,
    )


def _two_files(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("import os\n\n\ndef f():\n    return 1\n")
    b.write_text("import sys\n")
    return a, b


def test_suggestions_attached_with_absolute_patch_lines(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("x = 1\n\n\ndef f():\n    y = 1\n    return 2\n")
    analyzer = FakeAnalyzer([_finding(a, 5)])
    llm = FakeLLM(lambda r: LLMUnitResponse(fixes=[_fix([r.findings[0].id], "    y = 1\n", "")]))
    run = analyze(a, Config(), llm, [analyzer])
    (report,) = run.reports
    (sug,) = report.suggestions
    assert sug.id == "sug-1"
    assert sug.verification is None
    assert sug.patch is not None
    assert sug.patch.lines is not None
    assert sug.patch.lines.start == 5
    assert llm.requests[0].unit_name == "f"
    assert llm.requests[0].file_name == "a.py"
    assert "5 |     y = 1" in llm.requests[0].code
    assert run.errors == []
    assert report.usage.input_tokens == 10


def test_module_level_windows_merge_and_split(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("".join(f"v{i} = {i}\n" for i in range(1, 101)))
    analyzer = FakeAnalyzer([_finding(a, 10), _finding(a, 20), _finding(a, 80)])
    llm = FakeLLM(lambda r: LLMUnitResponse(fixes=[]))
    analyze(a, Config(), llm, [analyzer])
    assert [(r.start_line, len(r.findings)) for r in llm.requests] == [(1, 2), (65, 1)]
    assert llm.requests[0].unit_name is None
    assert llm.requests[0].code.splitlines()[-1].startswith("35 |")


def test_unknown_finding_id_dropped(tmp_path: Path) -> None:
    a, _ = _two_files(tmp_path)
    llm = FakeLLM(lambda r: LLMUnitResponse(fixes=[_fix(["nope"])]))
    run = analyze(a, Config(), llm, [FakeAnalyzer([_finding(a, 1)])])
    assert run.reports[0].suggestions == []
    assert len(run.errors) == 1


def test_patch_mismatch_recorded_and_run_continues(tmp_path: Path) -> None:
    a, b = _two_files(tmp_path)
    analyzer = FakeAnalyzer([_finding(a, 1), _finding(b, 1)])

    def handler(r: LLMRequest) -> LLMUnitResponse:
        original = "zzz" if r.file_name == "a.py" else "import sys\n"
        return LLMUnitResponse(fixes=[_fix([r.findings[0].id], original, "")])

    run = analyze(tmp_path, Config(), FakeLLM(handler), [analyzer])
    assert len(run.errors) == 1
    assert "patch eşleşmedi" in run.errors[0]
    by_name = {r.file.name: r for r in run.reports}
    assert by_name["a.py"].suggestions[0].patch is None
    assert by_name["b.py"].suggestions[0].patch is not None
    assert [s.id for r in run.reports for s in r.suggestions] == ["sug-1", "sug-2"]
    assert run.usage.input_tokens == 20


def test_fatal_error_stops_further_calls(tmp_path: Path) -> None:
    a, b = _two_files(tmp_path)
    llm = FakeLLM(lambda r: LLMError("API anahtarı geçersiz", fatal=True))
    run = analyze(tmp_path, Config(), llm, [FakeAnalyzer([_finding(a, 1), _finding(b, 1)])])
    assert len(llm.requests) == 1
    assert len(run.errors) == 1


def test_non_fatal_error_continues(tmp_path: Path) -> None:
    a, b = _two_files(tmp_path)
    llm = FakeLLM(lambda r: LLMError("model isteği reddetti"))
    run = analyze(tmp_path, Config(), llm, [FakeAnalyzer([_finding(a, 1), _finding(b, 1)])])
    assert len(llm.requests) == 2
    assert len(run.errors) == 2


def test_no_llm_is_static() -> None:
    run = analyze(FIXTURE, Config(), None, [FakeAnalyzer([_finding(FIXTURE, 1)])])
    assert run.reports[0].suggestions == []
