"""Quick-access locations for the folder picker (home, Desktop, Documents, Downloads, drives).

The real locations are asked from the OS, because users often move these folders
(Windows "Location" tab, OneDrive backup, a localized XDG config on Linux).
Name-based guesses under the home folder are only a fallback.
"""

from __future__ import annotations

import os
import shlex
import string
import sys
from pathlib import Path
from typing import Literal

from server.schemas import Place

PlaceKey = Literal["desktop", "documents", "downloads"]

LABELS: dict[PlaceKey, str] = {
    "desktop": "Masaüstü",
    "documents": "Belgeler",
    "downloads": "İndirilenler",
}

# Fallback names under home, including OneDrive-redirected and Turkish variants.
_FALLBACK_NAMES: dict[PlaceKey, tuple[str, ...]] = {
    "desktop": ("Desktop", "OneDrive/Desktop", "OneDrive/Masaüstü", "Masaüstü"),
    "documents": ("Documents", "OneDrive/Documents", "OneDrive/Belgeler", "Belgeler"),
    "downloads": ("Downloads", "OneDrive/Downloads", "İndirilenler"),
}

_XDG_KEYS: dict[PlaceKey, str] = {
    "desktop": "XDG_DESKTOP_DIR",
    "documents": "XDG_DOCUMENTS_DIR",
    "downloads": "XDG_DOWNLOAD_DIR",
}


def places() -> list[Place]:
    home = Path.home()
    result = [Place(name="Ev", path=str(home), kind="home")]
    for key, label in LABELS.items():
        found = _os_folder(key) or _fallback_folder(home, key)
        if found is not None:
            result.append(Place(name=label, path=str(found), kind="folder"))
    result.extend(Place(name=name, path=path, kind="drive") for name, path in _drives())
    return result


def _fallback_folder(home: Path, key: PlaceKey) -> Path | None:
    return next((home / n for n in _FALLBACK_NAMES[key] if (home / n).is_dir()), None)


def _os_folder(key: PlaceKey) -> Path | None:
    """Ask the OS where the folder really is; None if unknown or missing."""
    if sys.platform == "win32":
        path = _windows_known_folder(key)
    elif sys.platform == "darwin":
        path = None  # macOS does not let users move these; the fallback is exact
    else:
        path = _xdg_user_dir(key)
    return path if path is not None and path.is_dir() else None


def _xdg_user_dir(key: PlaceKey) -> Path | None:
    """Read ~/.config/user-dirs.dirs (e.g. XDG_DOWNLOAD_DIR="$HOME/İndirilenler")."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        lines = (config_home / "user-dirs.dirs").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    prefix = f"{_XDG_KEYS[key]}="
    for line in lines:
        if line.startswith(prefix):
            value = shlex.split(line[len(prefix) :])[0] if line[len(prefix) :] else ""
            return Path(value.replace("$HOME", str(Path.home()))) if value else None
    return None


if sys.platform == "win32":
    import ctypes
    import uuid
    from ctypes import wintypes

    _KNOWN_FOLDER_IDS: dict[PlaceKey, str] = {
        "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
        "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
        "downloads": "374DE290-123F-4565-9164-39C4925E467B",
    }

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    def _windows_known_folder(key: PlaceKey) -> Path | None:
        """SHGetKnownFolderPath: follows "Location" moves and OneDrive redirection."""
        u = uuid.UUID(_KNOWN_FOLDER_IDS[key])
        guid = _GUID(
            u.time_low,
            u.time_mid,
            u.time_hi_version,
            (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]),
        )
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(out)
        ):
            return None
        try:
            return Path(out.value) if out.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)

else:

    def _windows_known_folder(key: PlaceKey) -> Path | None:
        return None


def _drives() -> list[tuple[str, str]]:
    if sys.platform == "win32":
        letters = [c for c in string.ascii_uppercase if c not in "AB"]  # skip floppy probes
        return [(f"{c}:", f"{c}:\\") for c in letters if os.path.isdir(f"{c}:\\")]
    if sys.platform == "darwin":
        volumes = Path("/Volumes")
        children = sorted(volumes.iterdir()) if volumes.is_dir() else []
        return [(v.name, str(v)) for v in children if v.is_dir()]
    return [("Bilgisayar", "/")]
