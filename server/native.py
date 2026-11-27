"""Things the local server does on the user's own machine: the OS file dialog and git clone.

The server only listens on 127.0.0.1, so the "native" file dialog opens on the same
computer the browser runs on.
"""

from __future__ import annotations

import re
import subprocess
import threading
from pathlib import Path
from typing import Literal

from server.errors import UserFacingError

PickKind = Literal["files", "folder"]

_dialog_lock = threading.Lock()  # one OS dialog at a time

GITHUB_URL = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9-]{1,39})/(?P<repo>[A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$"
)
CLONE_TIMEOUT_S = 180


def pick_paths(kind: PickKind, initial_dir: str | None = None) -> list[str]:
    """Open the OS file dialog; return the chosen paths ([] when cancelled)."""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as exc:  # Python without Tk
        raise UserFacingError(
            "dialog_unavailable", "Bu Python kurulumunda dosya penceresi açılamıyor."
        ) from exc
    if not _dialog_lock.acquire(blocking=False):
        raise UserFacingError("dialog_busy", "Dosya penceresi zaten açık.", 409)
    try:
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # in front of the browser
        start = initial_dir if initial_dir and Path(initial_dir).is_dir() else str(Path.home())
        if kind == "folder":
            chosen = filedialog.askdirectory(parent=root, initialdir=start, title="Klasör seç")
            paths = [chosen] if chosen else []
        else:
            chosen_files = filedialog.askopenfilenames(
                parent=root,
                initialdir=start,
                title="Analiz edilecek dosyaları seç",
                filetypes=[("Python dosyaları", "*.py"), ("Tüm dosyalar", "*.*")],
            )
            paths = list(chosen_files)
        root.destroy()
        return [str(Path(p)) for p in paths]
    finally:
        _dialog_lock.release()


def repos_dir() -> Path:
    return Path.home() / ".mytool" / "repos"


def clone_github(url: str) -> Path:
    """Shallow-clone (or update) a public GitHub repository; return its local folder."""
    match = GITHUB_URL.match(url.strip())
    if match is None:
        raise UserFacingError(
            "invalid_repo_url",
            "Geçerli bir GitHub adresi girin, örneğin https://github.com/kullanici/proje",
        )
    owner, repo = match["owner"], match["repo"]
    target = repos_dir() / f"{owner}__{repo}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").is_dir():
        cmd = ["git", "-C", str(target), "pull", "--ff-only", "--depth", "1"]
    else:
        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            f"https://github.com/{owner}/{repo}.git",
            str(target),
        ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CLONE_TIMEOUT_S,
            env=_git_env(),
        )
    except FileNotFoundError as exc:
        raise UserFacingError("git_missing", "git bulunamadı; Git for Windows kurun.") from exc
    except subprocess.TimeoutExpired as exc:
        raise UserFacingError("clone_timeout", "Repo indirilemedi: zaman aşımı.", 504) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["bilinmeyen hata"]
        raise UserFacingError("clone_failed", f"Repo indirilemedi: {detail[0]}", 502)
    return target


def _git_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"  # never hang on a password prompt for private repos
    return env
