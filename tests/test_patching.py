from pathlib import Path

import pytest

from mytool.core.llm import LLMFix
from mytool.core.models import Category, LineRange, Patch
from mytool.core.patching import PatchError, apply_patch, build_patch

SOURCE = "def f(x):\n    y = x\n    return y\n"
FILE = Path("a.py")


def _fix(original: str, replacement: str) -> LLMFix:
    return LLMFix(
        finding_ids=["f1"],
        category=Category.STYLE,
        explanation="e",
        original=original,
        replacement=replacement,
    )


def test_exact_match_with_absolute_lines() -> None:
    patch = build_patch(SOURCE, FILE, 10, _fix("    y = x\n    return y\n", "    return x\n"))
    assert patch is not None
    assert patch.lines is not None
    assert (patch.lines.start, patch.lines.end) == (11, 12)
    assert patch.new == "    return x\n"
    assert patch.file == FILE


def test_single_line_without_newline() -> None:
    patch = build_patch(SOURCE, FILE, 1, _fix("return y", "return x"))
    assert patch is not None
    assert patch.lines is not None
    assert (patch.lines.start, patch.lines.end) == (3, 3)


def test_diff_has_plus_and_minus() -> None:
    patch = build_patch(SOURCE, FILE, 1, _fix("return y", "return x"))
    assert patch is not None
    lines = patch.unified_diff().splitlines()
    assert "-return y" in lines
    assert "+return x" in lines


def test_empty_original_is_explanation_only() -> None:
    assert build_patch(SOURCE, FILE, 1, _fix("", "")) is None


def test_deletion_allowed() -> None:
    patch = build_patch(SOURCE, FILE, 1, _fix("    y = x\n", ""))
    assert patch is not None
    assert patch.new == ""


def test_not_found() -> None:
    with pytest.raises(PatchError, match="bulunamadı"):
        build_patch(SOURCE, FILE, 1, _fix("nope", "x"))


def test_multiple_matches() -> None:
    with pytest.raises(PatchError, match="2 yerde"):
        build_patch("a = 1\na = 1\n", FILE, 1, _fix("a = 1", "a = 2"))


def _patch(original: str, new: str, line: int | None = None) -> Patch:
    lines = LineRange(start=line, end=line) if line else None
    return Patch(file=FILE, original=original, new=new, lines=lines)


def test_apply_once() -> None:
    assert apply_patch(SOURCE, _patch("    y = x\n", "")) == "def f(x):\n    return y\n"


def test_apply_missing() -> None:
    with pytest.raises(PatchError, match="bulunamadı"):
        apply_patch(SOURCE, _patch("nope", "x"))


def test_apply_multiple_without_lines_is_error() -> None:
    with pytest.raises(PatchError, match="2 yerde"):
        apply_patch("a = 1\na = 1\n", _patch("a = 1", "a = 2"))


def test_apply_multiple_prefers_line() -> None:
    text = "a = 1\nb = 0\na = 1\n"
    assert apply_patch(text, _patch("a = 1", "a = 2", line=3)) == "a = 1\nb = 0\na = 2\n"
    with pytest.raises(PatchError):
        apply_patch(text, _patch("a = 1", "a = 2", line=2))


def test_patch_error_is_value_error() -> None:
    assert issubclass(PatchError, ValueError)
