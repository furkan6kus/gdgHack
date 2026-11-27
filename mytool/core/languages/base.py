"""Language plugin interface."""

from __future__ import annotations

from typing import Protocol

from mytool.core.models import CodeUnit


class LanguagePlugin(Protocol):
    name: str
    extensions: tuple[str, ...]

    def extract_units(self, source: str) -> list[CodeUnit]: ...
