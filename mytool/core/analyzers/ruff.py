"""Ruff adapter."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from mytool.core.analyzers.base import AnalyzerError
from mytool.core.models import Category, Finding, LineRange, Severity

_ERROR_CODES = {"F821", "F822", "F823"}
_BANDIT = re.compile(r"S\d")


def severity_for(code: str | None) -> Severity:
    if code is None or code.startswith("E9") or code in _ERROR_CODES:
        return Severity.ERROR
    if code.startswith(("F", "B")) or _BANDIT.match(code):
        return Severity.WARNING
    return Severity.INFO


def category_for(code: str | None) -> Category:
    if code is not None and _BANDIT.match(code) is not None:
        return Category.SECURITY
    if code is not None and code.startswith("PERF"):
        return Category.PERF
    if code is None or code.startswith(("E9", "F", "B")):
        return Category.BUG
    return Category.STYLE


def _finding_id(rule: str, file: str, row: int, col: int) -> str:
    digest = hashlib.sha1(f"{rule}:{file}:{row}:{col}".encode()).hexdigest()
    return f"ruff-{digest[:8]}"


def _to_finding(item: dict[str, Any]) -> Finding:
    code: str | None = item.get("code")
    rule = code or "syntax-error"
    start = item["location"]
    end = item.get("end_location") or start
    row = int(start["row"])
    col = int(start["column"])
    return Finding(
        id=_finding_id(rule, item["filename"], row, col),
        tool="ruff",
        file=Path(item["filename"]),
        lines=LineRange(start=row, end=max(row, int(end["row"]))),
        column=col,
        severity=severity_for(code),
        rule=rule,
        message=item["message"],
        fix_available=item.get("fix") is not None,
        category=category_for(code),
    )


def parse_ruff_json(raw: str) -> list[Finding]:
    try:
        items = json.loads(raw) if raw.strip() else []
        if not isinstance(items, list):
            raise TypeError("liste bekleniyordu")
        return [_to_finding(item) for item in items]
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise AnalyzerError(f"ruff çıktısı okunamadı: {exc}") from exc


class RuffAnalyzer:
    name = "ruff"
    languages: tuple[str, ...] = ("python",)

    def run(self, files: list[Path], timeout_s: float) -> list[Finding]:
        if not files:
            return []
        cmd = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--output-format=json",
            "--exit-zero",
            "--no-fix",
            "--extend-select",
            "B,S,PERF,SIM",
            *map(str, files),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s
            )
        except FileNotFoundError as exc:
            raise AnalyzerError("ruff bulunamadı, kurulu değil") from exc
        except subprocess.TimeoutExpired as exc:
            raise AnalyzerError(f"ruff {timeout_s:g} sn içinde bitmedi") from exc
        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"çıkış kodu {proc.returncode}"
            raise AnalyzerError(f"ruff başarısız: {detail}")
        return parse_ruff_json(proc.stdout)
