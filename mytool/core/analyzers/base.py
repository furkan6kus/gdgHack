"""Analyzer interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from mytool.core.models import Finding


class AnalyzerError(Exception):
    """Analyzer failed; the message is meant for the user."""


class Analyzer(Protocol):
    name: str
    languages: tuple[str, ...]

    def run(self, files: list[Path], timeout_s: float) -> list[Finding]: ...
