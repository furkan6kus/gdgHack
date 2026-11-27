from pathlib import Path

import pytest
from fakes import FakeLLM

from mytool.core.config import DEFAULT_MAX_COST_USD, Config, load_config
from mytool.core.llm import LLMUnitResponse
from mytool.core.models import Finding, LineRange, Severity
from mytool.core.pipeline import analyze

SOURCE = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"


class TwoFindings:
    """One finding in each of two functions, so the pipeline makes two LLM calls."""

    name = "fake"
    languages: tuple[str, ...] = ("python",)

    def __init__(self, file: Path) -> None:
        self.file = file

    def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
        return [
            Finding(
                id=f"f{line}",
                tool="fake",
                file=self.file,
                lines=LineRange(start=line, end=line),
                severity=Severity.WARNING,
                rule="X1",
                message="m",
            )
            for line in (2, 6)
        ]


def _run(tmp_path: Path, cfg: Config) -> tuple[FakeLLM, list[str]]:
    target = tmp_path / "m.py"
    target.write_text(SOURCE)
    llm = FakeLLM(lambda r: LLMUnitResponse(fixes=[]))
    run = analyze(target, cfg, llm, [TwoFindings(target)])
    return llm, run.warnings


def test_default_limit() -> None:
    assert load_config({}).max_cost_usd == DEFAULT_MAX_COST_USD


def test_env_limit_accepts_comma() -> None:
    assert load_config({"MYTOOL_MAX_COST": "1,5"}).max_cost_usd == 1.5


def test_env_limit_must_be_number() -> None:
    with pytest.raises(ValueError, match="MYTOOL_MAX_COST"):
        load_config({"MYTOOL_MAX_COST": "çok"})


def test_under_limit_calls_every_unit(tmp_path: Path) -> None:
    llm, warnings = _run(tmp_path, Config(verify=False))
    assert len(llm.calls) == 2
    assert warnings == []


def test_limit_stops_later_calls(tmp_path: Path) -> None:
    # FakeLLM reports 10 input + 2 output tokens per call: $0.00004 on Sonnet 5.5.
    llm, warnings = _run(tmp_path, Config(verify=False, max_cost_usd=0.00003))
    assert len(llm.calls) == 1
    assert len(warnings) == 1
    assert "Harcama sınırına ulaşıldı" in warnings[0]
    assert "kalan 1 kod parçası" in warnings[0]


def test_zero_limit_sends_nothing(tmp_path: Path) -> None:
    llm, warnings = _run(tmp_path, Config(verify=False, max_cost_usd=0))
    assert llm.calls == []
    assert "kalan 2 kod parçası" in warnings[0]


def test_unknown_model_price_is_reported(tmp_path: Path) -> None:
    llm, warnings = _run(tmp_path, Config(verify=False, model="bilinmeyen-model"))
    assert len(llm.calls) == 2
    assert any("fiyatı bilinmiyor" in w for w in warnings)
