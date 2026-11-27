"""Verify patches on a temporary copy of the project. Never touches the user's files."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

from mytool.core.analyzers.base import AnalyzerError
from mytool.core.analyzers.ruff import RuffAnalyzer
from mytool.core.config import Config
from mytool.core.languages.base import LanguagePlugin
from mytool.core.models import (
    Finding,
    Patch,
    Severity,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.patching import PatchError, apply_patch

IGNORED_DIRS = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mytool",
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)
MAX_FILES = 5000
MAX_BYTES = 200 * 1024 * 1024
_ROOT_MARKERS = ("pyproject.toml", "setup.cfg", "setup.py", ".git")
_SECRET_WORDS = ("SECRET", "TOKEN", "PASSWORD", "API_KEY")
_TAIL_LINES = 20
_NO_TESTS_EXIT = 5


def find_project_root(file: Path) -> Path:
    start = file.resolve().parent
    for directory in (start, *start.parents):
        if any((directory / marker).exists() for marker in _ROOT_MARKERS):
            return directory
    return start


def _too_large(root: Path) -> bool:
    files = size = 0
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for name in names:
            files += 1
            try:
                size += (Path(current) / name).stat().st_size
            except OSError:
                continue
            if files > MAX_FILES or size > MAX_BYTES:
                return True
    return False


def _has_tests(root: Path) -> bool:
    if (root / "tests").is_dir():
        return True
    return any(root.rglob("test_*.py")) or any(root.rglob("*_test.py"))


def _python_for(project_root: Path) -> str:
    for relative in (".venv/Scripts/python.exe", ".venv/bin/python"):
        candidate = project_root / relative
        if candidate.is_file():
            return str(candidate)
    return sys.executable


class Workspace:
    """Temporary copy of one project. Use as a context manager; removed on exit."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self._tmp = tempfile.TemporaryDirectory(prefix="mytool-", ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.python = _python_for(self.project_root)
        self.tests_reason: str | None = None
        self.baseline_checked = False
        self.ruff_before: dict[Path, list[Finding] | None] = {}

    @property
    def tests_available(self) -> bool:
        return self.tests_reason is None

    def __enter__(self) -> Self:
        try:
            self._populate()
        except BaseException:
            self._tmp.cleanup()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._tmp.cleanup()

    def _populate(self) -> None:
        if _too_large(self.project_root):
            self.tests_reason = "proje çok büyük"
            return
        shutil.copytree(
            self.project_root,
            self.root,
            symlinks=True,
            ignore=shutil.ignore_patterns(*IGNORED_DIRS),
            dirs_exist_ok=True,
        )
        if not _has_tests(self.root):
            self.tests_reason = "test yok"

    def path_for(self, original: Path) -> Path:
        copy = self.root / original.resolve().relative_to(self.project_root)
        if not copy.exists():
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, copy)
        return copy


def _clean_env() -> dict[str, str]:
    kept = {
        key: value
        for key, value in os.environ.items()
        if not any(word in key.upper() for word in _SECRET_WORDS)
    }
    kept.pop("ANTHROPIC_API_KEY", None)
    kept.pop("ANTHROPIC_AUTH_TOKEN", None)
    kept["PYTHONDONTWRITEBYTECODE"] = "1"
    return kept


@dataclass(frozen=True)
class _TestRun:
    outcome: Literal["pass", "fail", "none"]
    detail: str


def _run_pytest(ws: Workspace, cfg: Config) -> _TestRun:
    """Raises subprocess.TimeoutExpired when tests exceed the timeout."""
    cmd = [ws.python, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider"]
    proc = subprocess.run(
        cmd,
        cwd=ws.root,
        env=_clean_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=cfg.subprocess_timeout_s,
    )
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-_TAIL_LINES:])
    if proc.returncode == 0:
        return _TestRun("pass", tail)
    return _TestRun("none" if proc.returncode == _NO_TESTS_EXIT else "fail", tail)


def _ensure_baseline(ws: Workspace, cfg: Config) -> None:
    """Run the tests once on the unpatched copy; mark tests unusable if they cannot pass."""
    if ws.baseline_checked or not ws.tests_available:
        return
    ws.baseline_checked = True
    try:
        run = _run_pytest(ws, cfg)
    except subprocess.TimeoutExpired:
        ws.tests_reason = (
            f"testler patch öncesi de zaman aşımına uğradı ({cfg.subprocess_timeout_s}s)"
        )
        return
    except OSError as exc:
        ws.tests_reason = f"testler başlatılamadı ({exc})"
        return
    if run.outcome == "none":
        ws.tests_reason = "test yok"
    elif run.outcome == "fail":
        ws.tests_reason = "testler patch öncesi de başarısız"


def _ruff_errors(path: Path, cfg: Config) -> list[Finding] | None:
    try:
        findings = RuffAnalyzer().run([path], float(cfg.subprocess_timeout_s))
    except AnalyzerError:
        return None
    return [f for f in findings if f.severity == Severity.ERROR]


def _new_ruff_errors(before: list[Finding] | None, after: list[Finding] | None) -> str | None:
    if before is None or after is None or len(after) <= len(before):
        return None
    known = {(f.rule, f.message) for f in before}
    fresh = [f for f in after if (f.rule, f.message) not in known] or after
    lines = [f"satır {f.lines.start}: {f.rule} {f.message}" for f in fresh[:5]]
    return "ruff yeni hata buldu:\n" + "\n".join(lines)


def _result(status: VerifyStatus, method: VerifyMethod, detail: str = "") -> VerificationResult:
    return VerificationResult(status=status, method=method, detail=detail)


def _failed(method: VerifyMethod, detail: str) -> VerificationResult:
    return _result(VerifyStatus.FAILED, method, detail)


def _test_step(ws: Workspace, cfg: Config) -> VerificationResult:
    try:
        run = _run_pytest(ws, cfg)
    except subprocess.TimeoutExpired:
        return _failed(VerifyMethod.PYTEST, f"zaman aşımı ({cfg.subprocess_timeout_s}s)")
    except OSError as exc:
        return _failed(VerifyMethod.PYTEST, f"testler başlatılamadı: {exc}")
    if run.outcome == "pass":
        return _result(VerifyStatus.PASSED, VerifyMethod.PYTEST, run.detail)
    if run.outcome == "fail":
        return _failed(VerifyMethod.PYTEST, run.detail)
    return _result(VerifyStatus.PASSED, VerifyMethod.SYNTAX, "test bulunamadı")


def _check_patched(ws: Workspace, target: Path, patched: str, cfg: Config) -> VerificationResult:
    target.write_text(patched, encoding="utf-8")
    problem = _new_ruff_errors(ws.ruff_before.get(target), _ruff_errors(target, cfg))
    if problem:
        return _failed(VerifyMethod.SYNTAX, problem)
    if ws.tests_available:
        return _test_step(ws, cfg)
    return _result(VerifyStatus.PASSED, VerifyMethod.SYNTAX, ws.tests_reason or "")


def _verify(
    ws: Workspace, target: Path, patch: Patch, plugin: LanguagePlugin, cfg: Config
) -> VerificationResult:
    text = target.read_text(encoding="utf-8", errors="replace")
    try:
        patched = apply_patch(text, patch)
    except PatchError as exc:
        return _failed(VerifyMethod.NONE, str(exc))
    message = plugin.check_syntax(patched, patch.file.name)
    if message:
        return _failed(VerifyMethod.SYNTAX, message)
    if target not in ws.ruff_before:
        ws.ruff_before[target] = _ruff_errors(target, cfg)
    _ensure_baseline(ws, cfg)
    return _check_patched(ws, target, patched, cfg)


def verify_patch(
    ws: Workspace, patch: Patch, plugin: LanguagePlugin, cfg: Config
) -> VerificationResult:
    started = time.perf_counter()
    target = ws.path_for(patch.file)
    original = target.read_bytes()
    try:
        result = _verify(ws, target, patch, plugin, cfg)
    finally:
        target.write_bytes(original)
    return result.model_copy(update={"duration_s": time.perf_counter() - started})
