"""Configuration. The API key is never stored here, only checked for presence."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

DEFAULT_MODEL = "claude-sonnet-5-5"
# Tahmini harcama bu tutara (USD, analiz başına) ulaşınca yeni LLM isteği gönderilmez.
DEFAULT_MAX_COST_USD = 0.50

DENY_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa*",
    "*secret*",
    "*credentials*",
    "*.p12",
)


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str = DEFAULT_MODEL
    max_tokens_per_request: int = 16000
    effort: Literal["low", "medium", "high"] = "medium"
    max_findings: int = 20
    max_cost_usd: float = DEFAULT_MAX_COST_USD
    subprocess_timeout_s: int = 60
    verify: bool = True
    deny_patterns: tuple[str, ...] = DENY_PATTERNS


def load_config(env: Mapping[str, str] | None = None, **overrides: Any) -> Config:
    env = os.environ if env is None else env
    values: dict[str, Any] = {}
    if env.get("MYTOOL_MODEL"):
        values["model"] = env["MYTOOL_MODEL"]
    if env.get("MYTOOL_MAX_COST"):
        try:
            values["max_cost_usd"] = float(env["MYTOOL_MAX_COST"].replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"MYTOOL_MAX_COST sayı olmalı: {env['MYTOOL_MAX_COST']!r}") from exc
    values.update({k: v for k, v in overrides.items() if v is not None})
    return Config(**values)


def has_api_key(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return bool(env.get("ANTHROPIC_API_KEY"))


def is_denied(path: Path, patterns: Iterable[str]) -> bool:
    name = path.name.lower()
    return any(fnmatch(name, p.lower()) for p in patterns)
