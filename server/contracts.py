"""Data contract between the UI server and the browser (the JSON the UI reads).

These are deliberately separate from ``mytool.core.models``: the UI wants
flat, JSON-friendly shapes (relative paths, ``rule_code``, millisecond
durations). ``server.adapters.core_adapter`` converts core models into these.
"""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["error", "warning", "info"]
Category = Literal["bug", "security", "perf", "style", "shrink", "translate"]
VerificationStatus = Literal["passed", "failed", "skipped"]
Stage = Literal["parsing", "static_analysis", "llm", "verify", "done", "error"]


class Finding(BaseModel):
    """A real finding produced by a static analyzer (e.g. ruff)."""

    id: str
    tool: str
    file: str
    line_start: int
    line_end: int
    severity: Severity
    rule_code: str
    message: str


class Patch(BaseModel):
    """A text replacement proposed for a single file."""

    file: str
    original_text: str
    new_text: str

    def unified_diff(self, context: int = 3) -> str:
        """Return a unified diff between ``original_text`` and ``new_text``."""
        lines = difflib.unified_diff(
            self.original_text.splitlines(keepends=True),
            self.new_text.splitlines(keepends=True),
            fromfile=f"a/{self.file}",
            tofile=f"b/{self.file}",
            n=context,
        )
        return "".join(lines)


class VerificationResult(BaseModel):
    """Outcome of applying a patch to a temp copy and running checks."""

    status: VerificationStatus
    detail: str
    duration_ms: int
    # False when only syntax + ruff were checked (no tests ran). Still applicable from the UI,
    # which warns about it before applying.
    tested: bool = True


class Suggestion(BaseModel):
    """An LLM explanation plus a verified patch for one or more findings."""

    id: str
    finding_ids: list[str]
    category: Category
    explanation: str
    # UI addition (not in the spec yet, see docs/ui-core-requests.md §10): a short
    # human-readable title for list rows. The UI falls back to the finding message.
    title: str | None = None
    patch: Patch
    verification: VerificationResult


class SeverityCounts(BaseModel):
    error: int = 0
    warning: int = 0
    info: int = 0


class FileSummary(BaseModel):
    path: str
    line_count: int
    counts: SeverityCounts = Field(default_factory=SeverityCounts)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMChoice(BaseModel):
    """Model and effort the user picked in the UI for suggestions and chat."""

    model: str
    effort: Literal["low", "medium", "high"] = "medium"


class AnalyzeResult(BaseModel):
    """UI-level result of an ``analyze`` run."""

    root: str
    files: list[FileSummary]
    findings: list[Finding]
    suggestions: list[Suggestion]
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost_usd: float | None = None
    warnings: list[str] = Field(default_factory=list)
    # Text of every file that has findings, keyed like Finding.file, for the code pane.
    sources: dict[str, str] = Field(default_factory=dict)


class ProgressEvent(BaseModel):
    stage: Stage
    message: str
    current: int | None = None
    total: int | None = None
