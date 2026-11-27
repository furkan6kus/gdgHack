"""Run a workload under cProfile and time it. Runs only inside a verify.Workspace copy."""

from __future__ import annotations

import os
import pstats
import statistics
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mytool.core.models import CodeUnit, ProfileEntry
from mytool.core.parser import unit_for_line

if TYPE_CHECKING:
    from mytool.core.verify import Workspace

MAX_ENTRIES = 20
MAX_HOT_UNITS = 3
MIN_SHARE = 0.02
_TAIL_LINES = 10
_PYTEST_ARGS = ["-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]


class WorkloadError(Exception):
    """The workload could not run or failed; message is for the user."""


@dataclass(frozen=True)
class Workload:
    """A script inside the workspace copy, or the project tests when script is None."""

    script: Path | None = None

    def args(self) -> list[str]:
        return [str(self.script)] if self.script is not None else list(_PYTEST_ARGS)


def _run(ws: Workspace, argv: list[str], timeout_s: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [ws.python, *argv],
            cwd=ws.root,
            env=ws.env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkloadError(f"iş yükü zaman aşımına uğradı ({timeout_s:g}s)") from exc


def _fail_detail(proc: subprocess.CompletedProcess[str]) -> str:
    return "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-_TAIL_LINES:])


def _same_file(filename: str, target: Path) -> bool:
    if filename.startswith(("<", "~")):
        return False
    try:
        return os.path.samefile(filename, target)
    except OSError:
        return False


def _entries_for(stats: pstats.Stats, target: Path) -> list[ProfileEntry]:
    entries = [
        ProfileEntry(function=name, line=line, calls=nc, tottime=tt, cumtime=ct)
        for (filename, line, name), (_cc, nc, tt, ct, _callers) in stats.stats.items()  # type: ignore[attr-defined]
        if name != "<module>" and _same_file(filename, target)
    ]
    return sorted(entries, key=lambda e: e.tottime, reverse=True)[:MAX_ENTRIES]


def profile(
    ws: Workspace, workload: Workload, target: Path, timeout_s: float
) -> tuple[list[ProfileEntry], float]:
    """Entries of `target` sorted by tottime, and the total profiled time of the whole run."""
    with tempfile.TemporaryDirectory(prefix="mytool-prof-") as tmp:
        out = Path(tmp) / "prof.out"
        proc = _run(ws, ["-m", "cProfile", "-o", str(out), *workload.args()], timeout_s)
        if not out.is_file():
            raise WorkloadError(f"profil üretilemedi:\n{_fail_detail(proc)}")
        stats = pstats.Stats(str(out))
    return _entries_for(stats, target), float(stats.total_tt)  # type: ignore[attr-defined]


def measure(
    ws: Workspace, workload: Workload, timeout_s: float, runs: int = 3
) -> tuple[float, str]:
    """Median wall time of `runs` unprofiled runs and the stdout of the first run.

    stdout is empty for the project-tests workload: pytest prints timings that always differ.
    """
    times: list[float] = []
    first_stdout = ""
    for index in range(runs):
        started = time.perf_counter()
        proc = _run(ws, workload.args(), timeout_s)
        times.append(time.perf_counter() - started)
        if proc.returncode != 0:
            raise WorkloadError(
                f"iş yükü başarısız (çıkış kodu {proc.returncode}):\n{_fail_detail(proc)}"
            )
        if index == 0 and workload.script is not None:
            first_stdout = proc.stdout
    return statistics.median(times), first_stdout


def _share(entries: list[ProfileEntry], unit: CodeUnit, total_s: float) -> float:
    inside = [e.cumtime for e in entries if unit.lines.start <= e.line <= unit.lines.end]
    return max(inside, default=0.0) / total_s


def hot_units(entries: list[ProfileEntry], total_s: float, units: list[CodeUnit]) -> list[CodeUnit]:
    """Up to 3 units holding the top entries, skipping those below 2% of total profile time."""
    if total_s <= 0:
        return []
    chosen: list[CodeUnit] = []
    for entry in entries:
        unit = unit_for_line(units, entry.line)
        if unit is None or unit in chosen or _share(entries, unit, total_s) < MIN_SHARE:
            continue
        chosen.append(unit)
        if len(chosen) == MAX_HOT_UNITS:
            break
    return chosen
