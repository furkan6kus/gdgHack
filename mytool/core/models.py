"""Pydantic data models shared by core, CLI and future frontends."""

from __future__ import annotations

import difflib
import re
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Category(StrEnum):
    BUG = "bug"
    PERF = "perf"
    STYLE = "style"
    SECURITY = "security"
    SHRINK = "shrink"
    TRANSLATE = "translate"


class VerifyStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerifyMethod(StrEnum):
    PYTEST = "pytest"
    SYNTAX = "syntax"
    BENCHMARK = "benchmark"
    COMPARE = "compare"
    NONE = "none"


class Stage(StrEnum):
    PARSING = "parsing"
    STATIC_ANALYSIS = "static_analysis"
    LLM = "llm"
    VERIFY = "verify"
    DONE = "done"


class ProgressEvent(BaseModel):
    """Progress reported by long-running pipeline calls (frontends render it)."""

    model_config = ConfigDict(frozen=True)

    stage: Stage
    message: str
    current: int | None = None
    total: int | None = None


class LineRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @field_validator("end")
    @classmethod
    def _end_not_before_start(cls, end: int, info: ValidationInfo) -> int:
        start = info.data.get("start")
        if start is not None and end < start:
            raise ValueError("end must be >= start")
        return end


class UnitKind(StrEnum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"


class CodeUnit(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    kind: UnitKind
    lines: LineRange
    source: str


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    tool: str
    file: Path
    lines: LineRange
    column: int | None = None
    severity: Severity
    rule: str
    message: str
    fix_available: bool = False
    category: Category = Category.STYLE
    symbol: str | None = None


def _lines_with_eol(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += "\n"
    return lines


_HUNK = re.compile(r"^@@ -(\d+)((?:,\d+)?) \+(\d+)((?:,\d+)?) @@", re.MULTILINE)


def _shift_hunks(diff: str, offset: int) -> str:
    def shift(match: re.Match[str]) -> str:
        old, old_n, new, new_n = match.groups()
        return f"@@ -{int(old) + offset}{old_n} +{int(new) + offset}{new_n} @@"

    return _HUNK.sub(shift, diff) if offset else diff


class Patch(BaseModel):
    model_config = ConfigDict(frozen=True)

    file: Path
    original: str
    new: str
    lines: LineRange | None = None

    def unified_diff(self, context: int = 3) -> str:
        name = self.file.as_posix()
        diff = difflib.unified_diff(
            _lines_with_eol(self.original),
            _lines_with_eol(self.new),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
            n=context,
        )
        text = "".join(diff)
        return _shift_hunks(text, self.lines.start - 1) if self.lines else text

    @property
    def line_delta(self) -> int:
        return len(self.new.splitlines()) - len(self.original.splitlines())


class VerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: VerifyStatus
    method: VerifyMethod
    detail: str = ""
    duration_s: float = Field(default=0.0, ge=0)


class ProfileEntry(BaseModel):
    function: str
    line: int
    calls: int
    tottime: float
    cumtime: float


class Benchmark(BaseModel):
    before_s: float
    after_s: float
    runs: int

    @property
    def speedup(self) -> float:
        return self.before_s / max(self.after_s, 1e-9)


class Suggestion(BaseModel):
    id: str
    finding_ids: list[str]
    category: Category
    explanation: str
    patch: Patch | None = None
    verification: VerificationResult | None = None
    benchmark: Benchmark | None = None

    @property
    def presentable(self) -> bool:
        return not (self.verification and self.verification.status == VerifyStatus.FAILED)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: TokenUsage) -> Self:
        return self.__class__(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


class Report(BaseModel):
    file: Path
    findings: list[Finding] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    content_sha256: str = ""

    def visible_suggestions(self) -> list[Suggestion]:
        return [s for s in self.suggestions if s.presentable]


class AnalysisRun(BaseModel):
    reports: list[Report] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    truncated: int = 0
    profile: list[ProfileEntry] = Field(default_factory=list)

    @property
    def usage(self) -> TokenUsage:
        total = TokenUsage()
        for report in self.reports:
            total = total.add(report.usage)
        return total


class ApplyOutcome(BaseModel):
    suggestion_id: str
    file: Path
    applied: bool
    reason: str = ""


class ApplyResult(BaseModel):
    outcomes: list[ApplyOutcome] = Field(default_factory=list)
    backup_dir: Path | None = None

    @property
    def applied_count(self) -> int:
        return sum(1 for o in self.outcomes if o.applied)

    @property
    def skipped(self) -> list[ApplyOutcome]:
        return [o for o in self.outcomes if not o.applied]


class UnitExplanation(BaseModel):
    name: str
    purpose: str
    notes: list[str]


class FileExplanation(BaseModel):
    summary: str
    units: list[UnitExplanation]


class ExplainResult(BaseModel):
    file: Path
    explanation: FileExplanation | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TranslatedSegment(BaseModel):
    code: str
    notes: list[str] = Field(default_factory=list)


class TranslateResult(BaseModel):
    file: Path
    target: str
    extension: str
    segments: list[TranslatedSegment] = Field(default_factory=list)
    output: str = ""
    verification: VerificationResult | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def presentable(self) -> bool:
        return not (self.verification and self.verification.status == VerifyStatus.FAILED)
