"""Translate a Python file into another language, segment by segment, and verify the result."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from mytool.core.config import Config, is_denied
from mytool.core.languages import plugin_for
from mytool.core.llm import LLMClient, LLMError
from mytool.core.models import (
    CodeUnit,
    TranslatedSegment,
    TranslateResult,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.parser import def_line
from mytool.core.pipeline import MAIN_GUARD, top_level, unit_code
from mytool.core.prompts import TRANSLATE_SYSTEM, build_translate_prompt
from mytool.core.verify import Workspace, find_project_root

_TAIL_LINES = 20
_DIFF_LINES = 3
_SCRATCH = ".mytool-translate"
_FENCE = re.compile(r"^```[\w+-]*\s*$")


@dataclass(frozen=True)
class Target:
    name: str
    extension: str
    lexer: str
    tool: str | None


_KNOWN = {
    t.name: t
    for t in (
        Target("javascript", ".js", "javascript", "node"),
        Target("typescript", ".ts", "typescript", None),
        Target("c", ".c", "c", "gcc"),
        Target("cpp", ".cpp", "cpp", "g++"),
        Target("go", ".go", "go", "gofmt"),
        Target("rust", ".rs", "rust", "rustc"),
        Target("java", ".java", "java", "javac"),
    )
}
_ALIASES = {"js": "javascript", "ts": "typescript", "c++": "cpp"}


def _syntax_args(*flags: str) -> Callable[[Path, Path], list[str]]:
    return lambda source, scratch: [*flags, str(source)]


_CHECK_ARGS: dict[str, Callable[[Path, Path], list[str]]] = {
    "javascript": _syntax_args("--check"),
    "c": _syntax_args("-fsyntax-only"),
    "cpp": _syntax_args("-fsyntax-only"),
    "go": _syntax_args("-e"),
    "rust": lambda source, scratch: [
        "--crate-type=lib",
        "--emit=metadata",
        "-o",
        str(scratch / "out.rmeta"),
        str(source),
    ],
    "java": lambda source, scratch: ["-d", str(scratch), str(source)],
}


def resolve_target(raw: str) -> Target:
    name = raw.strip().lower()
    name = _ALIASES.get(name, name)
    return _KNOWN.get(name) or Target(name, ".txt", "text", None)


@dataclass(frozen=True)
class Segment:
    label: str
    code: str
    signature: str | None = None


def _add_gap(parts: list[Segment], lines: list[str], first: int, last: int) -> None:
    code = "".join(lines[first - 1 : last])
    if code.strip():
        label = "(modül başı)" if not parts else "(modül kodu)"
        parts.append(Segment(label, code.strip("\n") + "\n"))


def split_segments(text: str, units: list[CodeUnit]) -> list[Segment]:
    """Module code between top-level units, and each top-level unit, in source order."""
    lines = text.splitlines(keepends=True)
    parts: list[Segment] = []
    cursor = 1
    for unit in sorted(top_level(units), key=lambda u: u.lines.start):
        _add_gap(parts, lines, cursor, unit.lines.start - 1)
        parts.append(Segment(unit.name, unit_code(text, unit), def_line(unit.source)))
        cursor = unit.lines.end + 1
    _add_gap(parts, lines, cursor, len(lines))
    return parts


def _strip_fence(code: str) -> str:
    lines = code.strip("\n").splitlines()
    if len(lines) >= 2 and _FENCE.match(lines[0].strip()) and lines[-1].strip() == "```":
        lines = lines[1:-1]
    return "\n".join(lines)


def _translate_parts(
    result: TranslateResult, llm: LLMClient, parts: list[Segment], target: Target
) -> bool:
    name = result.file.name
    previous: list[str] = []
    for part in parts:
        prompt = build_translate_prompt(name, target.name, part.label, part.code, previous)
        try:
            answer, usage = llm.structured(TRANSLATE_SYSTEM, prompt, TranslatedSegment)
        except LLMError as exc:
            result.errors.append(f"{name}: {part.label}: {exc}")
            return False
        result.usage = result.usage.add(usage)
        result.segments.append(answer.model_copy(update={"code": _strip_fence(answer.code)}))
        if part.signature:
            previous.append(part.signature)
    return True


def _skipped(detail: str) -> VerificationResult:
    return VerificationResult(status=VerifyStatus.SKIPPED, method=VerifyMethod.NONE, detail=detail)


def _tail(proc: subprocess.CompletedProcess[str]) -> str:
    return "\n".join((proc.stderr + proc.stdout).strip().splitlines()[-_TAIL_LINES:])


def _run_tool(argv: list[str], ws: Workspace, timeout_s: float) -> subprocess.CompletedProcess[str]:
    env = ws.env()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        argv,
        cwd=ws.root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )


def _scratch_file(ws: Workspace, name: str, code: str) -> tuple[Path, Path]:
    scratch = ws.root / _SCRATCH
    scratch.mkdir(exist_ok=True)
    path = scratch / name
    path.write_text(code, encoding="utf-8")
    return path, scratch


def _file_name(target: Target, source: Path) -> str:
    if target.name != "java":
        return f"translated{target.extension}"
    stem = re.sub(r"\W", "_", source.stem)
    return f"{stem[:1].upper()}{stem[1:]}.java"


def _check_syntax(
    ws: Workspace, target: Target, exe: str, source: Path, code: str, timeout_s: float
) -> VerificationResult:
    path, scratch = _scratch_file(ws, _file_name(target, source), code)
    argv = [exe, *_CHECK_ARGS[target.name](path, scratch)]
    try:
        proc = _run_tool(argv, ws, timeout_s)
    except subprocess.TimeoutExpired:
        return _failed(VerifyMethod.SYNTAX, f"{target.tool} zaman aşımı ({timeout_s:g}s)")
    if proc.returncode != 0:
        return _failed(
            VerifyMethod.SYNTAX, f"{target.tool} sözdizimi hatası bulundu\n{_tail(proc)}"
        )
    return VerificationResult(
        status=VerifyStatus.PASSED, method=VerifyMethod.SYNTAX, detail=f"{target.tool} geçti"
    )


def _failed(method: VerifyMethod, detail: str) -> VerificationResult:
    return VerificationResult(status=VerifyStatus.FAILED, method=method, detail=detail)


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).rstrip()


def _first_diff(expected: str, actual: str) -> str:
    rows = [
        f"satır {number}: beklenen {a!r}, çıkan {b!r}"
        for number, (a, b) in enumerate(zip_longest(expected.splitlines(), actual.splitlines()), 1)
        if a != b
    ]
    return "\n".join(rows[:_DIFF_LINES])


def _compare(
    ws: Workspace, node: str, source: Path, code: str, timeout_s: float
) -> VerificationResult:
    path, _ = _scratch_file(ws, "translated.js", code)
    try:
        original = _run_tool([ws.python, str(ws.path_for(source))], ws, timeout_s)
        translated = _run_tool([node, str(path)], ws, timeout_s)
    except subprocess.TimeoutExpired:
        return _failed(VerifyMethod.COMPARE, f"zaman aşımı ({timeout_s:g}s)")
    if original.returncode != 0:
        return _skipped(f"orijinal betik çalışmadı, çıktı karşılaştırılamadı\n{_tail(original)}")
    if translated.returncode != 0:
        return _failed(VerifyMethod.COMPARE, f"çeviri çalışmadı\n{_tail(translated)}")
    expected, actual = _normalize(original.stdout), _normalize(translated.stdout)
    if expected == actual:
        return VerificationResult(
            status=VerifyStatus.PASSED, method=VerifyMethod.COMPARE, detail="çıktı orijinalle aynı"
        )
    return _failed(
        VerifyMethod.COMPARE, f"çıktı orijinalden farklı\n{_first_diff(expected, actual)}"
    )


def _verify_in_workspace(
    exe: str, target: Target, source: Path, text: str, code: str, cfg: Config
) -> VerificationResult:
    timeout_s = float(cfg.subprocess_timeout_s)
    with Workspace(find_project_root(source)) as ws:
        if target.name == "javascript" and MAIN_GUARD.search(text):
            return _compare(ws, exe, source, code, timeout_s)
        return _check_syntax(ws, target, exe, source, code, timeout_s)


def _verify(target: Target, source: Path, text: str, code: str, cfg: Config) -> VerificationResult:
    if not cfg.verify:
        return _skipped("--no-verify")
    if target.name not in _KNOWN:
        return _skipped(f"bilinmeyen hedef ({target.name}), doğrulama yok")
    if target.tool is None:
        return _skipped(f"{target.name} için denetleyici yok")
    exe = shutil.which(target.tool)
    if exe is None:
        return _skipped(f"{target.tool} bulunamadı")
    try:
        return _verify_in_workspace(exe, target, source, text, code, cfg)
    except OSError as exc:
        return _skipped(f"doğrulama yapılamadı: {exc}")


def translate(file: Path, to: str, cfg: Config, llm: LLMClient) -> TranslateResult:
    """Translate `file` function by function. The source file is only read."""
    target = resolve_target(to)
    result = TranslateResult(file=file, target=target.name, extension=target.extension)
    plugin = plugin_for(file)
    if is_denied(file, cfg.deny_patterns):
        result.errors.append(f"{file.name}: deny-list, dosya LLM'e gönderilmez")
        return result
    if plugin is None:
        result.errors.append(f"{file.name}: desteklenmeyen dil")
        return result
    text = file.read_text(encoding="utf-8", errors="replace")
    parts = split_segments(text, plugin.extract_units(text))
    if not parts:
        result.errors.append(f"{file.name}: çevrilecek kod yok")
    elif _translate_parts(result, llm, parts, target):
        code = "\n\n".join(s.code.rstrip("\n") for s in result.segments) + "\n"
        result.output = code
        result.verification = _verify(target, file, text, code, cfg)
        if not result.presentable:
            result.output = ""
            result.segments = []
    return result
