"""Chat with Claude about one analyzed file: questions, and code changes on request.

The model answers in Turkish and may propose edits as exact (original -> replacement)
pairs. Every edit is checked here before the UI may apply it: the original text must
be found in the file once, and a Python file must still compile afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from mytool.core.config import Config, load_config
from mytool.core.llm import AnthropicLLM, LLMClient, LLMError, LLMFix, number_lines
from mytool.core.models import Category
from mytool.core.patching import PatchError, apply_patch, build_patch
from mytool.core.pricing import estimate_cost
from pydantic import BaseModel, Field

from server import browse
from server.contracts import LLMChoice
from server.errors import UserFacingError

MAX_MESSAGES = 30
MAX_FILE_BYTES = 200_000

LLMFactory = Callable[[Config], LLMClient]

SYSTEM = """\
You are a senior developer pairing with the user inside a code tool. You see one source file \
(with line-number prefixes "  12 | code") and the conversation so far.

Rules:
- Always answer in Turkish, short and concrete. Explain like to a colleague, no filler.
- If the user asks a question, answer it in `reply` and leave `edits` empty.
- If the user asks for a change (add, remove, fix, rename, refactor), make the smallest change \
that does it and describe it in `reply`.
- Each edit replaces `original` with `replacement`. `original` must be an exact, verbatim, \
contiguous piece of the given file WITHOUT the line-number prefixes, keeping indentation and \
newlines, and long enough to be unique in the file.
- To add new code, choose a nearby existing line as `original` and repeat it inside \
`replacement` together with the new code. To delete code, set `replacement` to the remaining text.
- Keep the code valid and keep the file's style. Never invent files or APIs that do not exist.
- `explanation` says in one Turkish sentence what that edit does.
"""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    path: str  # the analyzed folder or file (what the tab shows)
    file: str  # file inside it, relative like Finding.file
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    llm: LLMChoice | None = None


class _ModelEdit(BaseModel):
    original: str
    replacement: str
    explanation: str


class _ModelAnswer(BaseModel):
    reply: str
    edits: list[_ModelEdit]


class ChatEdit(BaseModel):
    id: str
    file: str
    original: str
    replacement: str
    explanation: str
    applicable: bool
    problem: str | None = None


class ChatResponse(BaseModel):
    reply: str
    edits: list[ChatEdit]
    estimated_cost_usd: float | None = None


class ChatApplyRequest(BaseModel):
    path: str
    file: str
    original: str = Field(min_length=1)
    replacement: str
    explanation: str = ""


def resolve_file(path: str, file: str) -> tuple[Path, Path]:
    """(analyzed root, absolute file); the file must be inside the analyzed root."""
    root = browse.resolve_target(path)
    base = (root if root.is_dir() else root.parent).resolve()
    target = (base / file).resolve()
    if target != root.resolve() and base not in target.parents:
        raise UserFacingError("path_denied", "Dosya analiz edilen klasörün dışında.", 403)
    if browse.path_is_denied(target):
        raise UserFacingError("path_denied", "Bu dosya güvenlik nedeniyle açılmıyor.", 403)
    if not target.is_file():
        raise UserFacingError("path_not_found", f"Dosya bulunamadı: {file}", 404)
    if target.stat().st_size > MAX_FILE_BYTES:
        raise UserFacingError("file_too_large", "Dosya sohbet için çok büyük.")
    return root, target


def read_source(target: Path) -> str:
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UserFacingError("file_unreadable", f"Dosya okunamadı: {target.name}") from exc


def check_edit(text: str, target: Path, original: str, replacement: str) -> tuple[str, str | None]:
    """(new file text, problem). The problem is None when the edit can be applied safely."""
    fix = LLMFix(
        finding_ids=[],
        category=Category.STYLE,
        explanation="",
        original=original,
        replacement=replacement,
    )
    try:
        patch = build_patch(text, target, 1, fix)
        if patch is None:
            return text, "Değiştirilecek metin boş."
        new_text = apply_patch(text, patch)
    except PatchError as exc:
        return text, f"Değiştirilecek kod dosyada {exc}; dosya değişmiş olabilir."
    if target.suffix == ".py":
        try:
            compile(new_text, target.name, "exec")
        except SyntaxError as exc:
            return (
                new_text,
                f"Bu değişiklikten sonra kod derlenmiyor (satır {exc.lineno}: {exc.msg}).",
            )
    return new_text, None


def _prompt(file: str, text: str, messages: list[ChatMessage]) -> str:
    history = "\n\n".join(
        f"{'Kullanıcı' if m.role == 'user' else 'Asistan'}: {m.content}" for m in messages
    )
    return f"Dosya: {file}\n\nKod:\n{number_lines(text, 1)}\n\nSohbet:\n{history}\n"


def answer(request: ChatRequest, llm_factory: LLMFactory) -> ChatResponse:
    _, target = resolve_file(request.path, request.file)
    text = read_source(target)
    cfg = load_config(
        model=request.llm.model if request.llm else None,
        effort=request.llm.effort if request.llm else None,
    )
    try:
        result, usage = llm_factory(cfg).structured(
            SYSTEM, _prompt(request.file, text, request.messages), _ModelAnswer
        )
    except LLMError as exc:
        raise UserFacingError("chat_failed", f"Claude yanıt veremedi: {exc}", 502) from exc
    edits = []
    for edit in result.edits:
        _, problem = check_edit(text, target, edit.original, edit.replacement)
        edits.append(
            ChatEdit(
                id=uuid.uuid4().hex[:10],
                file=request.file,
                original=edit.original,
                replacement=edit.replacement,
                explanation=edit.explanation,
                applicable=problem is None,
                problem=problem,
            )
        )
    return ChatResponse(
        reply=result.reply, edits=edits, estimated_cost_usd=estimate_cost(cfg.model, usage)
    )


def default_llm(cfg: Config) -> LLMClient:
    return AnthropicLLM(cfg)
