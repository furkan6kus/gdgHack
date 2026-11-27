"""Shared test doubles for the LLM client protocol."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel

from mytool.core.llm import LLMUnitResponse, T
from mytool.core.models import TokenUsage

Result = BaseModel | Exception


@dataclass(frozen=True)
class ParsedFinding:
    id: str
    rule: str
    line: int


@dataclass(frozen=True)
class ParsedRequest:
    """The fix prompt, parsed back into fields so tests can assert on them."""

    file_name: str
    unit_name: str | None
    start_line: int
    code: str
    findings: list[ParsedFinding]


def parse_prompt(prompt: str) -> ParsedRequest:
    def field(label: str) -> str:
        match = re.search(rf"^{label}: (.*)$", prompt, re.MULTILINE)
        return match.group(1) if match else ""

    unit = field("Birim")
    findings = [
        ParsedFinding(m.group(1), m.group(2), int(m.group(3)))
        for m in re.finditer(r"^- id=(\S+) kural=(\S+) satır=(\d+):", prompt, re.MULTILINE)
    ]
    return ParsedRequest(
        file_name=field("Dosya"),
        unit_name=None if unit == "(modül düzeyi)" else unit,
        start_line=int(field("İlk satır numarası") or 0),
        code=prompt.split("Kod:\n", 1)[-1],
        findings=findings,
    )


class FakeLLM:
    """`fix` answers LLMUnitResponse calls; `by_schema` maps other schemas to prompt handlers.

    A handler returning an Exception makes the call raise it.
    """

    def __init__(
        self,
        fix: Callable[[ParsedRequest], LLMUnitResponse | Exception] | None = None,
        by_schema: dict[type[BaseModel], Callable[[str], Result]] | None = None,
    ) -> None:
        self.fix = fix
        self.by_schema = by_schema or {}
        self.calls: list[tuple[type[BaseModel], str, str]] = []

    @property
    def requests(self) -> list[ParsedRequest]:
        return [parse_prompt(p) for schema, _, p in self.calls if schema is LLMUnitResponse]

    def structured(self, system: str, prompt: str, schema: type[T]) -> tuple[T, TokenUsage]:
        self.calls.append((schema, system, prompt))
        if schema is LLMUnitResponse and self.fix is not None:
            result: Result = self.fix(parse_prompt(prompt))
        else:
            result = self.by_schema[schema](prompt)
        if isinstance(result, Exception):
            raise result
        return cast(T, result), TokenUsage(input_tokens=10, output_tokens=2)

    def count(self, schema: type[BaseModel]) -> int:
        return sum(1 for s, _, _ in self.calls if s is schema)
