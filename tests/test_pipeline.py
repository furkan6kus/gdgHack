from pathlib import Path

from mytool.core.analyzers.base import AnalyzerError
from mytool.core.config import Config
from mytool.core.models import Category, Finding, LineRange, Severity
from mytool.core.pipeline import analyze_static, collect_files

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
