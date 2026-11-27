"""Turn an LLM fix into a Patch with absolute file line numbers. Pure, no LLM calls."""

from __future__ import annotations

from pathlib import Path

from mytool.core.llm import LLMFix
from mytool.core.models import LineRange, Patch


class PatchError(ValueError):
    """The fix cannot be located in the unit source; message is for the user."""


def _match_ignoring_indent(source: str, original: str) -> str | None:
    """The source text whose lines equal `original`'s apart from surrounding whitespace.

    Models often re-type tabs as spaces (or the reverse), which is exactly what
    indentation errors are about. The match must be unique; the returned text is
    the verbatim source, so the patch still replaces what is really in the file.
    """
    want = [line.strip() for line in original.rstrip("\r\n").split("\n")]
    if not any(want):
        return None
    lines = source.splitlines(keepends=True)
    hits = [
        i
        for i in range(len(lines) - len(want) + 1)
        if all(lines[i + k].strip() == want[k] for k in range(len(want)))
    ]
    if len(hits) != 1:
        return None
    block = "".join(lines[hits[0] : hits[0] + len(want)])
    return block if original.endswith("\n") else block.rstrip("\r\n")


def build_patch(unit_source: str, file: Path, unit_start_line: int, fix: LLMFix) -> Patch | None:
    if not fix.original:
        return None
    original = fix.original
    count = unit_source.count(original)
    if count == 0:
        loose = _match_ignoring_indent(unit_source, original)
        if loose is not None:
            original, count = loose, 1
    if count != 1:
        raise PatchError("bulunamadı" if count == 0 else f"{count} yerde eşleşti")
    start = unit_start_line + unit_source[: unit_source.index(original)].count("\n")
    end = start + original.rstrip("\r\n").count("\n")
    return Patch(
        file=file,
        original=original,
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
