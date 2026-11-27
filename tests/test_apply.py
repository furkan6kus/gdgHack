import hashlib
from datetime import datetime
from pathlib import Path

from mytool.core.apply import (
    apply_suggestions,
    fix_eligible,
    latest_backup,
    restore_backup,
    selectable,
)
from mytool.core.models import (
    Category,
    LineRange,
    Patch,
    Report,
    Suggestion,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)

NOW = datetime(2026, 1, 2, 3, 4, 5)


def verification(status: VerifyStatus, method: VerifyMethod) -> VerificationResult:
    return VerificationResult(status=status, method=method)


def sug(
    sid: str,
    file: Path,
    original: str,
    new: str,
    line: int,
    ver: VerificationResult | None = None,
) -> Suggestion:
    patch = Patch(
        file=file,
        original=original,
        new=new,
        lines=LineRange(start=line, end=line + max(original.count(chr(10)) - 1, 0)),
    )
    return Suggestion(
        id=sid,
        finding_ids=[],
        category=Category.STYLE,
        explanation="x",
        patch=patch,
        verification=ver,
    )


def project(tmp_path: Path, data: bytes) -> tuple[Path, Path]:
    (tmp_path / "pyproject.toml").write_text("")
    f = tmp_path / "m.py"
    f.write_bytes(data)
    return f, tmp_path / ".mytool" / "backup"


def report(f: Path, *suggestions: Suggestion, sha: bytes | None = None) -> Report:
    digest = hashlib.sha256(f.read_bytes() if sha is None else sha).hexdigest()
    return Report(file=f, suggestions=list(suggestions), content_sha256=digest)


def test_single_patch_and_backup(tmp_path: Path) -> None:
    original = b"import os\nx = 1\n"
    f, root = project(tmp_path, original)
    r = report(f, sug("s1", f, "import os\n", "", 1))
    result = apply_suggestions([r], {"s1"}, root, NOW)
    assert result.applied_count == 1
    assert f.read_bytes() == b"x = 1\n"
    assert result.backup_dir == root / "20260102-030405"
    assert result.backup_dir is not None
    assert (result.backup_dir / "m.py").read_bytes() == original
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_two_patches_descending(tmp_path: Path) -> None:
    f, root = project(tmp_path, b"a = 1\nb = 2\nc = 3\n")
    r = report(f, sug("s1", f, "a = 1\n", "a = 1\nz = 0\n", 1), sug("s2", f, "c = 3\n", "", 3))
    result = apply_suggestions([r], {"s1", "s2"}, root, NOW)
    assert result.applied_count == 2
    assert f.read_bytes() == b"a = 1\nz = 0\nb = 2\n"


def test_overlap_skipped(tmp_path: Path) -> None:
    f, root = project(tmp_path, b"a = 1\nb = 2\n")
    r = report(f, sug("s1", f, "a = 1\nb = 2\n", "q\n", 1), sug("s2", f, "b = 2\n", "w\n", 2))
    result = apply_suggestions([r], {"s1", "s2"}, root, NOW)
    assert result.applied_count == 1
    assert len(result.skipped) == 1
    assert "çakışma veya eşleşmedi" in result.skipped[0].reason


def test_stale_sha_skipped(tmp_path: Path) -> None:
    f, root = project(tmp_path, b"import os\n")
    r = report(f, sug("s1", f, "import os\n", "", 1), sha=b"old")
    result = apply_suggestions([r], {"s1"}, root, NOW)
    assert result.skipped[0].reason == "dosya analizden sonra değişti"
    assert f.read_bytes() == b"import os\n"
    assert result.backup_dir is None
    assert not root.exists()


def test_crlf_preserved(tmp_path: Path) -> None:
    f, root = project(tmp_path, b"import os\r\nx = 1\r\n")
    r = report(f, sug("s1", f, "import os\n", "", 1))
    apply_suggestions([r], {"s1"}, root, NOW)
    assert f.read_bytes() == b"x = 1\r\n"


def test_non_utf8_skipped(tmp_path: Path) -> None:
    f, root = project(tmp_path, b"x = '\xff'\n")
    r = report(f, sug("s1", f, "x", "y", 1))
    result = apply_suggestions([r], {"s1"}, root, NOW)
    assert result.skipped[0].reason == "utf-8 değil"
    assert not root.exists()


def test_eligibility() -> None:
    f = Path("m.py")
    passed = verification(VerifyStatus.PASSED, VerifyMethod.PYTEST)
    syntax = verification(VerifyStatus.PASSED, VerifyMethod.SYNTAX)
    failed = verification(VerifyStatus.FAILED, VerifyMethod.PYTEST)
    a = sug("a", f, "a\n", "b\n", 1, passed)
    b = sug("b", f, "a\n", "b\n", 1, syntax)
    c = sug("c", f, "a\n", "b\n", 1, failed)
    assert fix_eligible(a) and selectable(a)
    assert not fix_eligible(b) and selectable(b)
    assert not fix_eligible(c) and not selectable(c)
    nopatch = Suggestion(id="n", finding_ids=[], category=Category.STYLE, explanation="x")
    assert not fix_eligible(nopatch) and not selectable(nopatch)


def test_latest_and_restore(tmp_path: Path) -> None:
    f, root = project(tmp_path, b"import os\n")
    r = report(f, sug("s1", f, "import os\n", "", 1))
    apply_suggestions([r], {"s1"}, root, datetime(2026, 1, 1))
    f.write_bytes(b"import os\n")
    r2 = report(f, sug("s1", f, "import os\n", "", 1))
    second = apply_suggestions([r2], {"s1"}, root, datetime(2026, 1, 2))
    assert second.backup_dir is not None
    assert latest_backup(root) == second.backup_dir
    assert f.read_bytes() == b""
    assert restore_backup(second.backup_dir, tmp_path) == [f]
    assert f.read_bytes() == b"import os\n"
    assert latest_backup(tmp_path / "nope") is None
