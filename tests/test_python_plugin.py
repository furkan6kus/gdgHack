from pathlib import Path

from mytool.core.languages import plugin_for
from mytool.core.languages.python import PythonPlugin
from mytool.core.models import UnitKind

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"


def _units() -> dict[str, tuple[UnitKind, int, int]]:
    units = PythonPlugin().extract_units(FIXTURE.read_text(encoding="utf-8"))
    return {u.name: (u.kind, u.lines.start, u.lines.end) for u in units}


def test_names_and_kinds() -> None:
    units = _units()
    assert units["deco"][0] == UnitKind.FUNCTION
    assert units["Greeter"][0] == UnitKind.CLASS
    assert units["Greeter.hello"][0] == UnitKind.METHOD
    assert units["Greeter.hello.inner"][0] == UnitKind.FUNCTION
    assert units["risky"][0] == UnitKind.FUNCTION


def test_decorator_included_in_range() -> None:
    assert _units()["decorated"][1:] == (8, 10)


def test_nested_ranges() -> None:
    units = _units()
    assert units["Greeter"][1:] == (13, 18)
    assert units["Greeter.hello.inner"][1:] == (15, 16)


def test_source_text() -> None:
    units = PythonPlugin().extract_units("@d\ndef f():\n    pass\n")
    assert units[0].source.startswith("@d")


def test_registry() -> None:
    assert plugin_for(Path("a.py")) is not None
    assert plugin_for(Path("a.txt")) is None
