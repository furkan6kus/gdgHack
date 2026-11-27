"""Change history: every apply from the UI, with the before/after text, and undo.

Entries are kept in a JSON file (``~/.mytool/history.json`` by default, or
``MYTOOL_HISTORY_FILE``) so the history survives a server restart. Undo writes
the "before" text back only when the file still holds exactly the "after"
text, so a later manual edit is never overwritten.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from server.errors import UserFacingError

log = logging.getLogger(__name__)

MAX_ENTRIES = 200
MAX_FILE_BYTES = 1_000_000  # larger files are applied but not kept in the history


class FileChange(BaseModel):
    path: str  # absolute
    name: str
    before: str
    after: str


class HistoryEntry(BaseModel):
    id: str
    time: str  # ISO 8601, local time
    root: str
    explanations: list[str] = Field(default_factory=list)
    files: list[FileChange]
    undone: bool = False


def default_history_file() -> Path:
    env = os.environ.get("MYTOOL_HISTORY_FILE")
    return Path(env) if env else Path.home() / ".mytool" / "history.json"


def read_text(path: Path) -> str | None:
    """Current text of *path*, or None when it is missing, unreadable or too large."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


class HistoryStore:
    def __init__(self, file: Path | None = None) -> None:
        self.file = file or default_history_file()
        self._lock = threading.Lock()
        self._entries: list[HistoryEntry] = self._load()

    def _load(self) -> list[HistoryEntry]:
        try:
            raw = json.loads(self.file.read_text(encoding="utf-8"))
            return [HistoryEntry.model_validate(item) for item in raw]
        except FileNotFoundError:
            return []
        except (OSError, ValueError) as exc:
            log.warning("history file %s unreadable, starting empty: %s", self.file, exc)
            return []

    def _save(self) -> None:
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps([e.model_dump() for e in self._entries], ensure_ascii=False)
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(self.file)
        except OSError as exc:
            log.warning("could not write history file %s: %s", self.file, exc)

    def entries(self) -> list[HistoryEntry]:
        """Newest first."""
        with self._lock:
            return list(reversed(self._entries))

    def record(
        self, root: Path, before: dict[Path, str], explanations: list[str]
    ) -> HistoryEntry | None:
        """Store what changed since *before* was read; None when nothing changed."""
        files = []
        for path, old in before.items():
            new = read_text(path)
            if new is not None and new != old:
                files.append(FileChange(path=str(path), name=path.name, before=old, after=new))
        if not files:
            return None
        entry = HistoryEntry(
            id=uuid.uuid4().hex[:12],
            time=datetime.now().isoformat(timespec="seconds"),
            root=str(root),
            explanations=explanations,
            files=files,
        )
        with self._lock:
            self._entries.append(entry)
            del self._entries[:-MAX_ENTRIES]
            self._save()
        return entry

    def undo(self, entry_id: str) -> HistoryEntry:
        with self._lock:
            entry = next((e for e in self._entries if e.id == entry_id), None)
            if entry is None:
                raise UserFacingError("history_not_found", "Geçmiş kaydı bulunamadı.", 404)
            if entry.undone:
                raise UserFacingError("already_undone", "Bu değişiklik zaten geri alındı.", 409)
            changed = [f.name for f in entry.files if read_text(Path(f.path)) != f.after]
            if changed:
                raise UserFacingError(
                    "file_changed",
                    "Dosya bu değişiklikten sonra yeniden düzenlenmiş, geri alınamadı: "
                    + ", ".join(changed),
                    409,
                )
            for change in entry.files:
                Path(change.path).write_text(change.before, encoding="utf-8")
            entry.undone = True
            self._save()
            return entry
