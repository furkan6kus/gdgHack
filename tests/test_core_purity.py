import re
from pathlib import Path

CORE = Path(__file__).parent.parent / "mytool" / "core"
FORBIDDEN = re.compile(
    r"^\s*(?:import|from)\s+(?:rich|typer)\b|(?<![\w.])(?:print|input)\s*\(", re.MULTILINE
)


def test_core_has_no_terminal_code() -> None:
    offenders = [
        str(path.relative_to(CORE))
        for path in CORE.rglob("*.py")
        if FORBIDDEN.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, offenders
