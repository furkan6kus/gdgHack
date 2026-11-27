"""Language plugin registry."""

from __future__ import annotations

from pathlib import Path

from mytool.core.languages.base import LanguagePlugin
from mytool.core.languages.python import PythonPlugin

_PLUGINS: tuple[LanguagePlugin, ...] = (PythonPlugin(),)


def plugin_for(path: Path) -> LanguagePlugin | None:
    suffix = path.suffix.lower()
    return next((p for p in _PLUGINS if suffix in p.extensions), None)


__all__ = ["LanguagePlugin", "plugin_for"]
