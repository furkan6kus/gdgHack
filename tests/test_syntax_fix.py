"""Files with syntax errors: one LLM call with the whole file, one fix, real verification."""

from pathlib import Path

from fakes import FakeLLM, ParsedRequest

from mytool.core.config import Config
from mytool.core.llm import LLMFix, LLMUnitResponse
from mytool.core.models import Category, VerifyMethod, VerifyStatus
from mytool.core.pipeline import analyze

BROKEN = (
    "def total(items):\n"
    "    s = 0\n"
    "    for x in items:\n"
    "\ts += x\n"
    "    return s\n"
    "\n"
    "\n"
    "def half(n)\n"
    "    return n / 2\n"
)


def _fix_all(req: ParsedRequest) -> LLMUnitResponse:
    # The model re-types the tab as spaces; the patch must still find the lines.
    fix = LLMFix(
        finding_ids=[f.id for f in req.findings],
        category=Category.BUG,
        explanation="Girinti ve eksik iki nokta düzeltildi.",
        original="    for x in items:\n        s += x\n    return s\n\n\ndef half(n)\n",
        replacement="    for x in items:\n        s += x\n    return s\n\n\ndef half(n):\n",
    )
    return LLMUnitResponse(fixes=[fix])


def test_syntax_errors_become_one_verified_fix(tmp_path: Path) -> None:
    target = tmp_path / "broken.py"
    target.write_text(BROKEN)
    llm = FakeLLM(_fix_all)
    run = analyze(target, Config(), llm)

    (request,) = llm.requests  # one call for every syntax error
    assert request.start_line == 1
    assert len(request.findings) >= 2
    assert "def half(n)" in request.code

    (report,) = run.reports
    (suggestion,) = report.suggestions
    assert suggestion.patch is not None
    assert "\ts += x" in suggestion.patch.original
    assert suggestion.verification is not None
    assert suggestion.verification.status == VerifyStatus.PASSED
    assert suggestion.verification.method == VerifyMethod.SYNTAX
