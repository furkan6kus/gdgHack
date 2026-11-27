import json
import re
import subprocess
import sys

import pytest

from mytool.core.analyzers.messages_tr import MESSAGES, translate

ENABLED = re.compile(r"^(E4|E7|E9|F|B|S|PERF|SIM)\d")


def _sample(english: str) -> str:
    return re.sub(r"\{\w+\}", "deger", english)


@pytest.mark.parametrize(
    ("rule", "english", "turkish"),
    [(rule, en, tr) for rule, variants in MESSAGES.items() for en, tr in variants],
)
def test_every_variant_translates(rule: str, english: str, turkish: str) -> None:
    result = translate(rule, _sample(english))
    assert "…" not in result
    assert result != _sample(english) or english == "{message}"


def test_real_examples() -> None:
    assert translate("F401", "`os` imported but unused") == (
        "`os` içe aktarılmış ama kullanılmıyor"
    )
    assert translate("F821", "Undefined name `foo`") == "Tanımsız isim `foo`"
    assert translate("E712", "Avoid equality comparisons to `True`; use `x:` for truth checks") == (
        "`True` ile `==` karşılaştırması yapmayın; doğrudan `x:` yazın"
    )
    assert translate("S105", 'Possible hardcoded password assigned to: "PASSWORD"') == (
        'Koda gömülü parola olabilir: "PASSWORD"'
    )


def test_changed_wording_still_turkish() -> None:
    assert translate("F841", "some new ruff wording") == (
        "Yerel değişken `…` atanmış ama hiç kullanılmıyor"
    )


def test_unknown_rule_keeps_message() -> None:
    assert translate("ZZ999", "unchanged") == "unchanged"


def test_syntax_error() -> None:
    assert translate(None, "SyntaxError: Expected ')'") == "Sözdizimi hatası: Expected ')'"


def test_all_enabled_rules_have_turkish() -> None:
    """Every stable rule mytool turns on (see RuffAnalyzer) has a Turkish entry."""
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "rule", "--all", "--output-format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    rules = json.loads(proc.stdout)
    enabled = {
        r["code"] for r in rules if r["code"] and ENABLED.match(r["code"]) and not r.get("preview")
    }
    stable = {r["code"] for r in rules if "stable" in str(r.get("status", "")).lower()}
    checked = enabled & stable if stable else enabled
    assert len(checked) > 150  # guard against the filter silently matching nothing
    assert sorted(checked - MESSAGES.keys()) == []
