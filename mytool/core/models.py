"""Pydantic data models shared by core, CLI and future frontends."""

from __future__ import annotations

import difflib
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


class Patch(BaseModel):
    model_config = ConfigDict(frozen=True)

    file: Path
    original: str
    new: str
    lines: LineRange | None = None

    def unified_diff(self, context: int = 3) -> str:
        name = self.file.as_posix()
        diff = difflib.unified_diff(
            self.original.splitlines(keepends=True),
            self.new.splitlines(keepends=True),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
            n=context,
        )
        return "".join(diff)

    @property
    def line_delta(self) -> int:
        return len(self.new.splitlines()) - len(self.original.splitlines())


class VerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: VerifyStatus
    method: VerifyMethod
    detail: str = ""
    duration_s: float = Field(default=0.0, ge=0)


class Suggestion(BaseModel):
    id: str
    finding_ids: list[str]
    category: Category
    explanation: str
    patch: Patch | None = None
    verification: VerificationResult | None = None

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
    errors: list[str] = Field(default_factory=list)

    def visible_suggestions(self) -> list[Suggestion]:
        return [s for s in self.suggestions if s.presentable]
