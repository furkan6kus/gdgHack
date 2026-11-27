"""Adapter that will call the real core pipeline (UI Phase 2).

Intended wiring once ``core.pipeline`` exists (see docs/ui-core-requests.md)::

    from core.pipeline import analyze, apply_suggestions

    result = analyze(root, verify=verify, on_progress=on_progress,
                     should_cancel=cancel.is_set)
    return to_ui_result(result)   # only if core's shape differs from AnalyzeResult
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from server.adapters.base import ApplyOutcome, ProgressCallback
from server.contracts import AnalyzeResult, Suggestion
from server.errors import API_KEY_MISSING, AdapterError

_NOT_READY = AdapterError(
    "core_unavailable",
    "Core kütüphanesi henüz bağlanmadı. Şimdilik MYTOOL_UI_ADAPTER=mock kullanın.",
    status_code=503,
)


class CoreAdapter:
    name = "core"

    def api_key_configured(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    def analyze(
        self,
        root: Path,
        *,
        verify: bool,
        on_progress: ProgressCallback,
        cancel: threading.Event,
    ) -> AnalyzeResult:
        if not self.api_key_configured():
            raise AdapterError(API_KEY_MISSING, "ANTHROPIC_API_KEY tanımlı değil.")
        raise _NOT_READY

    def apply(self, root: Path, suggestions: list[Suggestion]) -> ApplyOutcome:
        raise _NOT_READY
