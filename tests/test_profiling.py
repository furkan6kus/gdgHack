from pathlib import Path

import pytest

from mytool.core.languages.python import PythonPlugin
from mytool.core.models import CodeUnit, LineRange, ProfileEntry, UnitKind
from mytool.core.profiling import Workload, WorkloadError, hot_units, measure, profile
from mytool.core.verify import Workspace

SLOW = """def work(n):
    total = 0
    for i in range(n):
        for j in range(n):
            total += i * j
    return total


def idle():
    return 1


if __name__ == "__main__":
    print(work(900))
"""
EXPECTED_OUT = f"{sum(range(900)) ** 2}\n"


def make_project(root: Path, source: str = SLOW) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0"\n')
    calc = root / "calc.py"
    calc.write_text(source)
    (root / "bench.py").write_text("from calc import work\n\nprint(work(900))\n")
    return calc


def test_profile_finds_slow_function_and_hot_unit(tmp_path: Path) -> None:
    calc = make_project(tmp_path)
    with Workspace(tmp_path) as ws:
        workload = Workload(script=ws.path_for(tmp_path / "bench.py"))
        entries, total = profile(ws, workload, ws.path_for(calc), 60)
    assert total > 0
    assert entries[0].function == "work"
    assert entries[0].line == 1
    assert entries[0].calls == 1
    assert all(e.function != "<module>" for e in entries)
    units = PythonPlugin().extract_units(calc.read_text())
    assert [u.name for u in hot_units(entries, total, units)] == ["work"]


def test_measure_returns_median_and_first_stdout(tmp_path: Path) -> None:
    make_project(tmp_path)
    with Workspace(tmp_path) as ws:
        workload = Workload(script=ws.path_for(tmp_path / "bench.py"))
        seconds, out = measure(ws, workload, 60, runs=2)
    assert seconds > 0
    assert out == EXPECTED_OUT


def test_measure_failing_script_raises(tmp_path: Path) -> None:
    make_project(tmp_path)
    (tmp_path / "boom.py").write_text("raise SystemExit(3)\n")
    with Workspace(tmp_path) as ws, pytest.raises(WorkloadError, match="çıkış kodu 3"):
        measure(ws, Workload(script=ws.path_for(tmp_path / "boom.py")), 60, runs=1)


def _unit(name: str, start: int, end: int) -> CodeUnit:
    lines = LineRange(start=start, end=end)
    return CodeUnit(name=name, kind=UnitKind.FUNCTION, lines=lines, source="")


def test_hot_units_skip_small_share_and_cap_at_three() -> None:
    entries = [
        ProfileEntry(function=f"f{i}", line=10 * i + 1, calls=1, tottime=1.0 - i / 10, cumtime=1.0)
        for i in range(5)
    ]
    tiny = ProfileEntry(function="tiny", line=101, calls=1, tottime=0.5, cumtime=0.01)
    units = [_unit(f"f{i}", 10 * i + 1, 10 * i + 5) for i in range(5)] + [_unit("tiny", 101, 105)]
    assert [u.name for u in hot_units([*entries, tiny], 10.0, units)] == ["f0", "f1", "f2"]
    assert hot_units([tiny], 10.0, units) == []
    assert hot_units(entries, 0.0, units) == []
