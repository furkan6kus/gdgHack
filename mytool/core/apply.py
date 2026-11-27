"""Apply suggestions to user files with backups, and restore from them. No UI here."""

from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path

from mytool.core.models import (
    ApplyOutcome,
    ApplyResult,
    Report,
    Suggestion,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.patching import PatchError, apply_patch

_STAMP = "%Y%m%d-%H%M%S"


def selectable(s: Suggestion) -> bool:
    return s.patch is not None and s.presentable


def fix_eligible(s: Suggestion) -> bool:
    v = s.verification
    return (
        s.patch is not None
        and v is not None
        and v.status == VerifyStatus.PASSED
        and v.method in (VerifyMethod.PYTEST, VerifyMethod.BENCHMARK)
    )


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _backup_path(backup_dir: Path, backup_root: Path, file: Path) -> Path:
    try:
        rel = file.resolve().relative_to(backup_root.resolve().parent.parent)
    except ValueError:
        rel = Path(file.name)
    return backup_dir / rel


def write_output(
    path: Path, text: str, backup_root: Path, now: datetime | None = None
) -> Path | None:
    """Write `text` to `path` atomically; an existing file is backed up first (returned)."""
    backup: Path | None = None
    if path.exists():
        stamp = backup_root / (now or datetime.now()).strftime(_STAMP)
        backup = _backup_path(stamp, backup_root, path)
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, text.encode("utf-8"))
    return backup


def _fail(report: Report, ids: list[Suggestion], reason: str) -> list[ApplyOutcome]:
    return [
        ApplyOutcome(suggestion_id=s.id, file=report.file, applied=False, reason=reason)
        for s in ids
    ]


def _patch_text(
    text: str, report: Report, chosen: list[Suggestion]
) -> tuple[str, list[ApplyOutcome], bool]:
    outcomes: list[ApplyOutcome] = []
    changed = False
    for s in sorted(
        chosen, key=lambda s: s.patch.lines.start if s.patch and s.patch.lines else 0, reverse=True
    ):
        assert s.patch is not None
        try:
            text = apply_patch(text, s.patch)
        except PatchError as exc:
            outcomes.append(
                ApplyOutcome(
                    suggestion_id=s.id,
                    file=report.file,
                    applied=False,
                    reason=f"çakışma veya eşleşmedi: {exc}",
                )
            )
        else:
            changed = True
            outcomes.append(ApplyOutcome(suggestion_id=s.id, file=report.file, applied=True))
    return text, outcomes, changed


def _apply_file(
    report: Report, chosen: list[Suggestion], backup_dir: Path, backup_root: Path
) -> tuple[list[ApplyOutcome], bool]:
    try:
        raw = report.file.read_bytes()
    except OSError as exc:
        return _fail(report, chosen, f"dosya okunamadı: {exc}"), False
    if hashlib.sha256(raw).hexdigest() != report.content_sha256:
        return _fail(report, chosen, "dosya analizden sonra değişti"), False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _fail(report, chosen, "utf-8 değil"), False
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text, outcomes, changed = _patch_text(text.replace("\r\n", "\n"), report, chosen)
    if changed:
        backup = _backup_path(backup_dir, backup_root, report.file)
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(raw)
        _atomic_write(report.file, text.replace("\n", newline).encode("utf-8"))
    return outcomes, changed


def apply_suggestions(
    reports: list[Report],
    suggestion_ids: set[str],
    backup_root: Path,
    now: datetime | None = None,
) -> ApplyResult:
    backup_dir = backup_root / (now or datetime.now()).strftime(_STAMP)
    result = ApplyResult(outcomes=[], backup_dir=None)
    for report in reports:
        chosen = [s for s in report.suggestions if s.id in suggestion_ids and s.patch is not None]
        if not chosen:
            continue
        outcomes, changed = _apply_file(report, chosen, backup_dir, backup_root)
        result.outcomes.extend(outcomes)
        if changed:
            result.backup_dir = backup_dir
    return result


def latest_backup(backup_root: Path) -> Path | None:
    if not backup_root.is_dir():
        return None
    dirs = sorted(d for d in backup_root.iterdir() if d.is_dir())
    return dirs[-1] if dirs else None


def restore_backup(backup_dir: Path, project_root: Path) -> list[Path]:
    restored: list[Path] = []
    for source in sorted(p for p in backup_dir.rglob("*") if p.is_file()):
        target = project_root / source.relative_to(backup_dir)
        _atomic_write(target, source.read_bytes())
        restored.append(target)
    return restored
