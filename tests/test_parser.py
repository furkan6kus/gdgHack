from pathlib import Path

from mytool.core.languages.python import PythonPlugin
from mytool.core.parser import unit_for_line

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"


def test_innermost_unit() -> None:
    units = PythonPlugin().extract_units(FIXTURE.read_text(encoding="utf-8"))
    inner = unit_for_line(units, 16)
    assert inner is not None
    assert inner.name == "Greeter.hello.inner"
    method = unit_for_line(units, 18)
    assert method is not None
    assert method.name == "Greeter.hello"


def test_outside_returns_none() -> None:
    units = PythonPlugin().extract_units(FIXTURE.read_text(encoding="utf-8"))
    assert unit_for_line(units, 1) is None
