import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from mytool.core.analyzers.messages_tr import MESSAGES, SYNTAX_RULES, translate
from mytool.core.analyzers.ruff import RuffAnalyzer
from mytool.core.models import Category, Severity

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


def test_syntax_error_without_code() -> None:
    assert translate(None, "SyntaxError: Expected an expression") == "Bir ifade bekleniyordu"


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


@pytest.mark.parametrize(
    ("message", "turkish"),
    [
        ("Unexpected indentation", "Beklenmeyen girinti: bu satır fazladan içeride"),
        (
            "unindent does not match any outer indentation level",
            "Girinti hiçbir üst satırın girintisiyle eşleşmiyor",
        ),
        ("Expected `:`, found newline", "`:` bekleniyordu, satır sonu bulundu"),
        ("Expected dedent, found end of file", "Girintili blok kapanmadan dosya bitti"),
        ("Expected an expression", "Bir ifade bekleniyordu"),
        ("Expected an identifier", "Bir isim bekleniyordu"),
        (
            "Expected an indented block after function definition",
            "Fonksiyon tanımı sonrasında girintili (içeriden başlayan) blok bekleniyordu",
        ),
        (
            "Expected an indented block after `if` statement",
            "`if` deyimi sonrasında girintili (içeriden başlayan) blok bekleniyordu",
        ),
        ("Got unexpected token $", "Beklenmeyen karakter: $"),
        ("missing closing quote in string literal", "Metnin kapanış tırnağı eksik"),
    ],
)
def test_syntax_errors_in_turkish(message: str, turkish: str) -> None:
    assert translate("invalid-syntax", message) == turkish


def test_unknown_syntax_error_has_turkish_lead() -> None:
    assert translate("invalid-syntax", "brand new parser text").startswith("Sözdizimi hatası")


def test_real_syntax_errors_are_turkish(tmp_path: Path) -> None:
    """Every parse error ruff reports for these snippets gets a known Turkish text."""
    snippets = [
        "def f():\nreturn 1\n",
        "if x\n    pass\n",
        "def f():\n    x = 1\n  y = 2\n",
        "x = (1, 2\n",
        "x = 'abc\n",
        "f(a=1, 2)\n",
        "def f(a=1, b):\n    pass\n",
        "try:\n    pass\n",
        "x = 1 2\n",
        "from x import\n",
        "x = $\n",
        "del 1\n",
    ]
    for i, code in enumerate(snippets):
        (tmp_path / f"s{i}.py").write_text(code)
    findings = RuffAnalyzer().run(sorted(tmp_path.glob("*.py")), 60)
    syntax = [f for f in findings if f.rule in SYNTAX_RULES]
    assert len(syntax) >= len(snippets)
    for finding in syntax:
        assert not finding.message.startswith("Sözdizimi hatası"), finding.message
        assert finding.severity == Severity.ERROR
        assert finding.category == Category.BUG
