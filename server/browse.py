"""Directory listing for the in-app folder picker, with a secrets deny-list."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from server.errors import UserFacingError
from server.schemas import BrowseEntry, BrowseResponse

# Names that are never listed, browsed into, or analyzed. Matched case-insensitively.
DENY_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.keystore",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    ".netrc",
    ".pgpass",
    ".npmrc",
    ".pypirc",
    "credentials*",
    "secrets*",
    ".ssh",
    ".gnupg",
    ".aws",
    ".docker",
    ".kube",
)


def is_denied(name: str) -> bool:
    lowered = name.lower()
    return any(fnmatch.fnmatchcase(lowered, pattern) for pattern in DENY_PATTERNS)


def path_is_denied(path: Path) -> bool:
    """True if any component of *path* matches the deny-list."""
    return any(is_denied(part) for part in path.parts)


def resolve_target(raw: str | None) -> Path:
    """Resolve *raw* (default: home) to an existing, allowed file or directory."""
    path = Path(raw).expanduser() if raw else Path.home()
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as err:
        raise UserFacingError("path_not_found", "Bu yol bulunamadı.", 404) from err
    if path_is_denied(path):
        raise UserFacingError("path_denied", "Bu yol güvenlik nedeniyle gösterilmiyor.", 403)
    return path


def resolve_dir(raw: str | None) -> Path:
    """Resolve *raw* to a directory; a file resolves to the folder containing it."""
    path = resolve_target(raw)
    return path if path.is_dir() else path.parent


def list_dir(path: Path, *, show_hidden: bool = False) -> BrowseResponse:
    try:
        children = list(path.iterdir())
    except PermissionError as err:
        raise UserFacingError("permission_denied", "Bu klasörü okuma izniniz yok.", 403) from err
    entries = [_entry(child) for child in children if _visible(child.name, show_hidden=show_hidden)]
    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
    parent = None if path.parent == path else str(path.parent)
    return BrowseResponse(path=str(path), parent=parent, entries=entries)


def _visible(name: str, *, show_hidden: bool) -> bool:
    if is_denied(name):
        return False
    return show_hidden or not name.startswith(".")


def _entry(child: Path) -> BrowseEntry:
    try:
        is_dir = child.is_dir()
    except OSError:
        is_dir = False
    return BrowseEntry(name=child.name, path=str(child), is_dir=is_dir)
