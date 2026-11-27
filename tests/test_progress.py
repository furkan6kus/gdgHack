from pathlib import Path

import pytest
from fakes import FakeLLM

from mytool.core.config import Config
from mytool.core.llm import LLMUnitResponse
from mytool.core.models import Finding, LineRange, ProgressEvent, Severity, Stage
from mytool.core.pipeline import Cancelled, analyze


class OneFinding:
    name = "fake"
    languages: tuple[str, ...] = ("python",)

    def __init__(self, file: Path) -> None:
        self.file = file

    def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
        return [
            Finding(
                id="f1",
                tool="fake",
                file=self.file,
                lines=LineRange(start=1, end=1),
                severity=Severity.WARNING,
                rule="X1",
                message="m",
            )
        ]


def _project(tmp_path: Path) -> Path:
    a = tmp_path / "a.py"
    a.write_text("import os\n")
    (tmp_path / "b.py").write_text("x = 1\n")
    return a


def test_progress_stages_in_order(tmp_path: Path) -> None:
    a = _project(tmp_path)
    events: list[ProgressEvent] = []
    llm = FakeLLM(lambda r: LLMUnitResponse(fixes=[]))
    analyze(tmp_path, Config(verify=False), llm, [OneFinding(a)], on_progress=events.append)
    stages = [e.stage for e in events]
    assert stages == [
        Stage.PARSING,
        Stage.PARSING,
        Stage.STATIC_ANALYSIS,
        Stage.STATIC_ANALYSIS,
        Stage.LLM,
        Stage.DONE,
    ]
    assert (events[1].current, events[1].total) == (2, 2)
    assert events[3].message == "1 bulgu bulundu"


def test_static_only_still_reports_done(tmp_path: Path) -> None:
    a = _project(tmp_path)
    events: list[ProgressEvent] = []
    analyze(tmp_path, Config(), None, [OneFinding(a)], on_progress=events.append)
    assert events[-1].stage == Stage.DONE
    assert Stage.LLM not in {e.stage for e in events}


def test_cancel_stops_before_llm(tmp_path: Path) -> None:
    a = _project(tmp_path)
    seen: list[ProgressEvent] = []
    llm = FakeLLM(lambda r: LLMUnitResponse(fixes=[]))
    with pytest.raises(Cancelled):
        analyze(
            tmp_path,
            Config(),
            llm,
            [OneFinding(a)],
            on_progress=seen.append,
            should_cancel=lambda: any(e.stage == Stage.STATIC_ANALYSIS for e in seen),
        )
    assert llm.calls == []
