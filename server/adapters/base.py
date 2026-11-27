"""Adapter protocol: the only boundary between the UI server and the core.

Adapters may be implemented synchronously (the core is plain Python) and are
always run in a worker thread by ``server.jobs``. ``on_progress`` is therefore
thread-safe and ``cancel`` is a ``threading.Event``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from server.contracts import AnalyzeResult, LLMChoice, ProgressEvent, Suggestion

ProgressCallback = Callable[[ProgressEvent], None]


class ApplyOutcome(BaseModel):
    applied_ids: list[str]
    changed_files: list[str]
    backup_path: str


class Adapter(Protocol):
    name: str

    def api_key_configured(self) -> bool:
        """Whether an LLM API key is available. Must never expose the value."""
        ...

    def analyze(
        self,
        root: Path,
        *,
        verify: bool,
        on_progress: ProgressCallback,
        cancel: threading.Event,
        llm: LLMChoice | None = None,
    ) -> AnalyzeResult:
        """Run the analysis. Raise ``AdapterError`` for expected failures."""
        ...

    def apply(self, root: Path, suggestions: list[Suggestion]) -> ApplyOutcome:
        """Apply already-validated (passed) suggestions, taking a backup first."""
        ...
