from pathlib import Path

import pytest
from pydantic import ValidationError

from mytool.core.models import (
    Category,
    Finding,
    LineRange,
    Patch,
    Report,
    Severity,
    Suggestion,
    TokenUsage,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)


def _finding() -> Finding:
    return Finding(
        id="f1",
        tool="ruff",
        file=Path("a.py"),
        lines=LineRange(start=1, end=2),
        severity=Severity.WARNING,
        rule="F401",
        message="unused import",
    )


def _suggestion(status: VerifyStatus | None) -> Suggestion:
    verification = VerificationResult(status=status, method=VerifyMethod.SYNTAX) if status else None
    return Suggestion(
        id="s",
        finding_ids=["f1"],
        category=Category.BUG,
        explanation="x",
        verification=verification,
    )


def test_line_range_valid() -> None:
    assert LineRange(start=2, end=2).end == 2


@pytest.mark.parametrize(("start", "end"), [(0, 1), (1, 0), (5, 3)])
def test_line_range_invalid(start: int, end: int) -> None:
    with pytest.raises(ValidationError):
        LineRange(start=start, end=end)


def test_unified_diff() -> None:
    patch = Patch(file=Path("src/a.py"), original="a\nb\n", new="a\nc\n")
    diff = patch.unified_diff()
    assert "--- a/src/a.py" in diff
    assert "+++ b/src/a.py" in diff
    assert "-b" in diff
    assert "+c" in diff


def test_line_delta() -> None:
    assert Patch(file=Path("a"), original="a\n", new="a\nb\nc\n").line_delta == 2
    assert Patch(file=Path("a"), original="a\nb\n", new="a\n").line_delta == -1


def test_presentable() -> None:
    assert _suggestion(None).presentable
    assert _suggestion(VerifyStatus.PASSED).presentable
    assert _suggestion(VerifyStatus.SKIPPED).presentable
    assert not _suggestion(VerifyStatus.FAILED).presentable


def test_visible_suggestions() -> None:
    good, bad = _suggestion(VerifyStatus.PASSED), _suggestion(VerifyStatus.FAILED)
    report = Report(file=Path("a.py"), suggestions=[good, bad])
    assert report.visible_suggestions() == [good]


def test_token_usage_add() -> None:
    a, b = TokenUsage(input_tokens=1, output_tokens=2), TokenUsage(input_tokens=10)
    total = a.add(b)
    assert (total.input_tokens, total.output_tokens) == (11, 2)
    assert a.input_tokens == 1


def test_report_json_round_trip() -> None:
    report = Report(
        file=Path("a.py"),
        findings=[_finding()],
        suggestions=[_suggestion(VerifyStatus.PASSED)],
        usage=TokenUsage(input_tokens=3, output_tokens=4),
        errors=["boom"],
    )
    assert Report.model_validate_json(report.model_dump_json()) == report
