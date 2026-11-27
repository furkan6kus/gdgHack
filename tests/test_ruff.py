import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from mytool.core.analyzers.base import AnalyzerError
from mytool.core.analyzers.ruff import RuffAnalyzer, category_for, parse_ruff_json, severity_for
from mytool.core.models import Category, Severity

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"


def _item(code: str | None, row: int = 3) -> dict[str, Any]:
    return {
        "code": code,
        "message": "msg",
        "filename": "a.py",
        "location": {"row": row, "column": 2},
        "end_location": {"row": row + 1, "column": 5},
        "fix": None if code != "F401" else {"applicability": "safe"},
    }


def test_parse_ruff_json() -> None:
    findings = parse_ruff_json(json.dumps([_item("F401"), _item(None, 7)]))
    assert [f.rule for f in findings] == ["F401", "syntax-error"]
    first = findings[0]
    assert first.id.startswith("ruff-") and len(first.id) == 13
    assert first.fix_available and first.lines.end == 4 and first.column == 2
    assert findings[1].severity == Severity.ERROR
    assert findings[1].category == Category.BUG
    assert not findings[1].fix_available


def test_ids_stable() -> None:
    raw = json.dumps([_item("S307")])
    assert parse_ruff_json(raw)[0].id == parse_ruff_json(raw)[0].id


def test_empty_output() -> None:
    assert parse_ruff_json("") == []


@pytest.mark.parametrize(
    ("code", "severity", "category"),
    [
        (None, Severity.ERROR, Category.BUG),
        ("E902", Severity.ERROR, Category.BUG),
        ("F821", Severity.ERROR, Category.BUG),
        ("F401", Severity.WARNING, Category.BUG),
        ("B001", Severity.WARNING, Category.BUG),
        ("S307", Severity.WARNING, Category.SECURITY),
        ("PERF401", Severity.INFO, Category.PERF),
        ("SIM102", Severity.INFO, Category.STYLE),
        ("E722", Severity.WARNING, Category.BUG),
        ("E501", Severity.INFO, Category.STYLE),
    ],
)
def test_severity_and_category(code: str | None, severity: Severity, category: Category) -> None:
    assert severity_for(code) == severity
    assert category_for(code) == category


@pytest.mark.parametrize("raw", ["not json", '[{"code": "F401"}]', '{"a": 1}'])
def test_bad_json_raises(raw: str) -> None:
    with pytest.raises(AnalyzerError):
        parse_ruff_json(raw)


def test_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(AnalyzerError):
        RuffAnalyzer().run([Path("x.py")], 5)


def test_real_ruff_run(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    shutil.copy(FIXTURE, target)
    findings = RuffAnalyzer().run([target], 60)
    rules = {f.rule for f in findings}
    assert {"F401", "S307", "E722"} <= rules


def test_asserts_in_tests_are_not_findings(tmp_path: Path) -> None:
    test_file = tmp_path / "test_x.py"
    test_file.write_text("def test_a():\n    assert 1 == 1\n")
    app_file = tmp_path / "app.py"
    app_file.write_text("def f(x):\n    assert x\n    return x\n")
    findings = RuffAnalyzer().run([test_file, app_file], 60)
    assert [(f.file.name, f.rule) for f in findings if f.rule == "S101"] == [("app.py", "S101")]
