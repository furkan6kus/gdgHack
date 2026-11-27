from pathlib import Path

import pytest

from mytool.core import verify
from mytool.core.config import Config
from mytool.core.languages.python import PythonPlugin
from mytool.core.models import (
    LineRange,
    Patch,
    VerificationResult,
    VerifyMethod,
    VerifyStatus,
)
from mytool.core.verify import Workspace, find_project_root, verify_patch

CALC = "def add(a, b):\n    return a + b\n"
TEST_CALC = "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
PLUGIN = PythonPlugin()


def _project(root: Path, test_source: str | None = TEST_CALC) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0"\n')
    calc = root / "calc.py"
    calc.write_text(CALC)
    if test_source is not None:
        (root / "tests").mkdir()
        (root / "tests" / "test_calc.py").write_text(test_source)
    return calc


def _patch(calc: Path, new: str, original: str = "    return a + b\n") -> Patch:
    return Patch(file=calc, original=original, new=new, lines=LineRange(start=2, end=2))


def _verify(calc: Path, patch: Patch, timeout: int = 60) -> VerificationResult:
    with Workspace(find_project_root(calc)) as ws:
        result = verify_patch(ws, patch, PLUGIN, Config(subprocess_timeout_s=timeout))
        assert ws.path_for(calc).read_text() == CALC
    assert calc.read_text() == CALC
    return result


def test_find_project_root(tmp_path: Path) -> None:
    calc = _project(tmp_path / "proj")
    sub = tmp_path / "proj" / "pkg"
    sub.mkdir()
    (sub / "m.py").write_text("x = 1\n")
    assert find_project_root(sub / "m.py") == calc.parent.resolve()


def test_syntax_error_fails(tmp_path: Path) -> None:
    calc = _project(tmp_path)
    result = _verify(calc, _patch(calc, "    return a +\n"))
    assert result.status == VerifyStatus.FAILED
    assert result.method == VerifyMethod.SYNTAX
    assert "satır 2" in result.detail


def test_unmatched_patch_fails_with_method_none(tmp_path: Path) -> None:
    calc = _project(tmp_path)
    result = _verify(calc, _patch(calc, "x\n", original="zzz\n"))
    assert (result.status, result.method) == (VerifyStatus.FAILED, VerifyMethod.NONE)


def test_no_tests_passes_with_syntax_only(tmp_path: Path) -> None:
    calc = _project(tmp_path, test_source=None)
    result = _verify(calc, _patch(calc, "    return b + a\n"))
    assert (result.status, result.method) == (VerifyStatus.PASSED, VerifyMethod.SYNTAX)
    assert "test yok" in result.detail
    assert result.duration_s > 0


def test_passing_tests(tmp_path: Path) -> None:
    calc = _project(tmp_path)
    result = _verify(calc, _patch(calc, "    return b + a\n"))
    assert (result.status, result.method) == (VerifyStatus.PASSED, VerifyMethod.PYTEST)


def test_patch_breaking_tests_fails(tmp_path: Path) -> None:
    calc = _project(tmp_path)
    result = _verify(calc, _patch(calc, "    return a - b\n"))
    assert (result.status, result.method) == (VerifyStatus.FAILED, VerifyMethod.PYTEST)
    assert "assert" in result.detail


def test_failing_baseline_falls_back_to_syntax(tmp_path: Path) -> None:
    calc = _project(tmp_path, TEST_CALC.replace("== 3", "== 99"))
    result = _verify(calc, _patch(calc, "    return b + a\n"))
    assert (result.status, result.method) == (VerifyStatus.PASSED, VerifyMethod.SYNTAX)
    assert "patch öncesi de başarısız" in result.detail


def test_timeout_fails(tmp_path: Path) -> None:
    calc = _project(tmp_path)
    slow = "    import time\n\n    time.sleep(60)\n    return a + b\n"
    result = _verify(calc, _patch(calc, slow), timeout=5)
    assert (result.status, result.method) == (VerifyStatus.FAILED, VerifyMethod.PYTEST)
    assert "zaman aşımı (5s)" in result.detail


def test_new_ruff_error_fails(tmp_path: Path) -> None:
    calc = _project(tmp_path)
    result = _verify(calc, _patch(calc, "    return a + missing_name\n"))
    assert (result.status, result.method) == (VerifyStatus.FAILED, VerifyMethod.SYNTAX)
    assert "F821" in result.detail


def test_workspace_ignores_venv_and_caches(tmp_path: Path) -> None:
    calc = _project(tmp_path)
    for name in (".venv", "node_modules", "__pycache__", ".git"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "x.py").write_text("x = 1\n")
    with Workspace(calc.parent) as ws:
        copied = {p.name for p in ws.root.iterdir()}
        root = ws.root
    assert {"calc.py", "tests", "pyproject.toml"} <= copied
    assert not copied & {".venv", "node_modules", "__pycache__", ".git"}
    assert not root.exists()


def test_subprocess_env_has_no_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_env = (
        "import os\n\n\ndef test_env():\n"
        "    bad = ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'MY_SECRET_THING')\n"
        "    assert not [k for k in bad if k in os.environ]\n"
    )
    calc = _project(tmp_path, test_env)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("MY_SECRET_THING", "x")
    result = _verify(calc, _patch(calc, "    return b + a\n"))
    assert (result.status, result.method) == (VerifyStatus.PASSED, VerifyMethod.PYTEST)


def test_clean_env_filters_names(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ANTHROPIC_AUTH_TOKEN", "DB_PASSWORD", "STRIPE_API_KEY"):
        monkeypatch.setenv(name, "v")
    env = verify._clean_env()
    assert not {"ANTHROPIC_AUTH_TOKEN", "DB_PASSWORD", "STRIPE_API_KEY"} & set(env)
    assert "PATH" in env or "Path" in env


def test_too_large_project_copies_only_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verify, "MAX_FILES", 1)
    calc = _project(tmp_path)
    with Workspace(calc.parent) as ws:
        assert not ws.tests_available
        assert not (ws.root / "tests").exists()
    result = _verify(calc, _patch(calc, "    return b + a\n"))
    assert (result.status, result.method) == (VerifyStatus.PASSED, VerifyMethod.SYNTAX)
    assert "proje çok büyük" in result.detail
