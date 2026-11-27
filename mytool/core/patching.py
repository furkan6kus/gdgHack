"""Turn an LLM fix into a Patch with absolute file line numbers. Pure, no LLM calls."""

from __future__ import annotations

from pathlib import Path

from mytool.core.llm import LLMFix
from mytool.core.models import LineRange, Patch


class PatchError(ValueError):
    """The fix cannot be located in the unit source; message is for the user."""


def build_patch(unit_source: str, file: Path, unit_start_line: int, fix: LLMFix) -> Patch | None:
    if not fix.original:
        return None
    count = unit_source.count(fix.original)
    if count != 1:
        raise PatchError("bulunamadı" if count == 0 else f"{count} yerde eşleşti")
    start = unit_start_line + unit_source[: unit_source.index(fix.original)].count("\n")
    end = start + fix.original.rstrip("\r\n").count("\n")
    return Patch(
        file=file,
        original=fix.original,
        new=fix.replacement,
        lines=LineRange(start=start, end=end),
    )


def _starts(text: str, needle: str) -> list[int]:
    found: list[int] = []
    index = text.find(needle)
    while index != -1:
        found.append(index)
        index = text.find(needle, index + 1)
    return found


def _choose_start(text: str, starts: list[int], lines: LineRange | None) -> int:
    if len(starts) == 1:
        return starts[0]
    if lines is not None:
        at_line = [i for i in starts if text.count("\n", 0, i) + 1 == lines.start]
        if len(at_line) == 1:
            return at_line[0]
    raise PatchError(f"original metin {len(starts)} yerde eşleşti")


def apply_patch(text: str, patch: Patch) -> str:
    """Replace patch.original with patch.new; original must be locatable unambiguously."""
    if not patch.original:
        raise PatchError("patch'in original metni boş")
    starts = _starts(text, patch.original)
    if not starts:
        raise PatchError("original metin dosyada bulunamadı")
    start = _choose_start(text, starts, patch.lines)
    return text[:start] + patch.new + text[start + len(patch.original) :]
