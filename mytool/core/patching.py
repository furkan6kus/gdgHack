"""Turn an LLM fix into a Patch with absolute file line numbers. Pure, no LLM calls."""

from __future__ import annotations

from pathlib import Path

from mytool.core.llm import LLMFix
from mytool.core.models import LineRange, Patch


class PatchError(Exception):
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
