"""LLM client: structured explanations and patch proposals for static findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from mytool.core.config import Config
from mytool.core.models import Category, TokenUsage

FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
You are a careful code reviewer helping fix static analysis findings.

You receive one code unit (or a window of lines) with line-number prefixes of the form \
"  12 | code", plus the findings reported for it. Answer with the requested JSON only.

Rules:
- Write every explanation in Turkish, short and concrete: what is wrong and why the fix helps.
- Propose minimal, behavior-preserving fixes. Do not refactor, rename or reformat unrelated code.
- Only address the given findings. Never invent findings that were not listed.
- Each fix lists the ids of the findings it resolves in finding_ids (copy the ids exactly).
- `original` must be an exact, verbatim, contiguous substring of the given code, WITHOUT the \
line-number prefixes, keeping the original indentation and newlines. Include enough lines to \
make it unique within the code.
- `replacement` is the text that replaces `original`.
- If you are unsure, or no safe fix exists, give an explanation only: set both `original` and \
`replacement` to "".
- To delete code, set `replacement` to "".
"""


class LLMError(Exception):
    """User-readable failure. `fatal` means further calls would fail the same way."""

    def __init__(self, message: str, *, fatal: bool = False) -> None:
        super().__init__(message)
        self.fatal = fatal


class LLMFix(BaseModel):
    finding_ids: list[str]
    category: Category
    explanation: str
    original: str
    replacement: str


class LLMUnitResponse(BaseModel):
    fixes: list[LLMFix]


@dataclass(frozen=True)
class LLMFindingRef:
    id: str
    rule: str
    line: int
    message: str


@dataclass(frozen=True)
class LLMRequest:
    file_name: str
    language: str
    unit_name: str | None
    start_line: int
    code: str
    findings: list[LLMFindingRef]


class LLMClient(Protocol):
    def suggest(self, req: LLMRequest) -> tuple[LLMUnitResponse, TokenUsage]: ...


def number_lines(source: str, start_line: int) -> str:
    lines = source.splitlines()
    width = len(str(start_line + len(lines)))
    return "\n".join(f"{start_line + i:>{width}} | {line}" for i, line in enumerate(lines))


def render_request(req: LLMRequest) -> str:
    unit = req.unit_name or "(modül düzeyi)"
    findings = "\n".join(
        f"- id={f.id} kural={f.rule} satır={f.line}: {f.message}" for f in req.findings
    )
    return (
        f"Dosya: {req.file_name}\nDil: {req.language}\nBirim: {unit}\n"
        f"İlk satır numarası: {req.start_line}\n\nBulgular:\n{findings}\n\n"
        f"Kod:\n{req.code}\n"
    )


# (exception class, message, fatal) - most specific first.
_ERROR_MAP: tuple[tuple[type[anthropic.APIError], str, bool], ...] = (
    (anthropic.AuthenticationError, "API anahtarı geçersiz (ANTHROPIC_API_KEY)", True),
    (anthropic.PermissionDeniedError, "API anahtarının bu işlem için izni yok", True),
    (anthropic.NotFoundError, "model bulunamadı, model adını kontrol et (--model)", True),
    (anthropic.RateLimitError, "hız sınırı, biraz sonra tekrar dene", True),
    (anthropic.APITimeoutError, "ağ hatası: istek zaman aşımına uğradı", True),
    (anthropic.APIConnectionError, "ağ hatası: API'ye bağlanılamadı", True),
)


def _map_error(exc: anthropic.APIError) -> LLMError:
    for cls, message, fatal in _ERROR_MAP:
        if isinstance(exc, cls):
            return LLMError(message, fatal=fatal)
    if isinstance(exc, anthropic.APIStatusError):
        return LLMError(f"API hatası {exc.status_code}")
    return LLMError("API hatası")


class AnthropicLLM:
    def __init__(self, cfg: Config, client: Any = None) -> None:
        self._cfg = cfg
        self._client: Any = client

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def _call(self, req: LLMRequest) -> Any:
        try:
            return self._get_client().beta.messages.parse(
                model=self._cfg.model,
                max_tokens=self._cfg.max_tokens_per_request,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": render_request(req)}],
                output_format=LLMUnitResponse,
                output_config={"effort": self._cfg.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            raise _map_error(exc) from exc

    def suggest(self, req: LLMRequest) -> tuple[LLMUnitResponse, TokenUsage]:
        usage = TokenUsage()
        for _ in range(2):
            try:
                response = self._call(req)
            except ValidationError:
                continue
            usage = usage.add(_usage_of(response))
            _check_stop(response)
            if response.parsed_output is not None:
                return response.parsed_output, usage
        raise LLMError("model geçersiz JSON döndürdü (2 deneme)")


def _usage_of(response: Any) -> TokenUsage:
    return TokenUsage(
        input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
    )


def _check_stop(response: Any) -> None:
    if response.stop_reason == "refusal":
        raise LLMError("model isteği reddetti")
    if response.stop_reason == "max_tokens":
        raise LLMError("yanıt token sınırına takıldı; --max-tokens ile sınırı artır")
