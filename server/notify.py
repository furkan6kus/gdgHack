"""Telegram notifications: an analysis finished (with its findings) or failed.

Set ``TELEGRAM_BOT_TOKEN`` (from @BotFather) and ``TELEGRAM_CHAT_ID`` (your chat
with the bot). Without them nothing is sent. Sending never blocks or breaks an
analysis: failures are only logged.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import httpx

from server.contracts import AnalyzeResult
from server.schemas import ErrorPayload

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LISTED = 3  # keep the message short: the worst few lines only
MAX_TEXT = 90
TIMEOUT_S = 10.0
_CODE = re.compile(r"`([^`]+)`")


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = (
            token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        ).strip()
        self.chat_id = (
            chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        ).strip()

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, text: str) -> bool:
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                response = await client.post(
                    API.format(token=self.token),
                    json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
                )
            if response.status_code != 200:
                log.warning("telegram: HTTP %s: %s", response.status_code, response.text[:200])
                return False
            return True
        except httpx.HTTPError as exc:
            log.warning("telegram: send failed: %s", exc)
            return False


def result_message(root: Path, result: AnalyzeResult) -> str:
    """Short "ready" note: what was found, the worst lines first, and how many fixes are ready."""
    name = _name(root)
    if not result.findings:
        return f"✅ {name} hazır: sorun bulunmadı."
    errors = sum(1 for f in result.findings if f.severity == "error")
    minor = len(result.findings) - errors
    if errors:
        parts = [f"{errors} ciddi hata"] + ([f"{minor} küçük sorun"] if minor else [])
        lines = [f"🔴 {name} hazır: {', '.join(parts)}"]
    else:
        lines = [f"🟡 {name} hazır: {minor} küçük sorun, ciddi hata yok"]
    many_files = len({f.file for f in result.findings}) > 1
    for finding in sorted(result.findings, key=_severity_rank)[:MAX_LISTED]:
        where = (
            f"{finding.file}, satır {finding.line_start}"
            if many_files
            else f"Satır {finding.line_start}"
        )
        lines.append(f"• {where}: {_short(finding.message)}")
    if len(result.findings) > MAX_LISTED:
        lines.append(f"…ve {len(result.findings) - MAX_LISTED} sorun daha")
    ready = sum(1 for s in result.suggestions if s.verification.status == "passed")
    if ready:
        lines.append(f"🛠 {ready} düzeltme uygulanmaya hazır.")
    return "\n".join(lines)


def applied_message(root: Path, files: list[str], count: int, explanation: str = "") -> str:
    target = ", ".join(files) or _name(root)
    text = f"🛠 {target}: {count} düzeltme uygulandı."
    return f"{text}\n{_short(explanation)}" if explanation else text


def error_message(root: Path, error: ErrorPayload) -> str:
    return f"⚠️ {_name(root)} analiz edilemedi: {_short(error.message, 140)}"


def _name(root: Path) -> str:
    return root.name or str(root)


def _short(text: str, limit: int = MAX_TEXT) -> str:
    """One line; `code` becomes 'code' (backticks look odd in a chat); cut at a word."""
    line = " ".join(_CODE.sub(lambda m: f"'{m.group(1)}'", text).replace("`", "").split())
    if len(line) <= limit:
        return line
    return line[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _severity_rank(finding: object) -> int:
    order = {"error": 0, "warning": 1, "info": 2}
    return order.get(getattr(finding, "severity", "info"), 3)
