"""Helpers over extracted code units."""

from __future__ import annotations

from collections.abc import Sequence

from mytool.core.models import CodeUnit


def unit_for_line(units: Sequence[CodeUnit], line: int) -> CodeUnit | None:
    """Return the innermost (smallest span) unit containing the 1-based line."""
    inside = [u for u in units if u.lines.start <= line <= u.lines.end]
    return min(inside, key=lambda u: u.lines.end - u.lines.start, default=None)
