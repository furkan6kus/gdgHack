"""Configuration. The API key is never stored here, only checked for presence."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

DEFAULT_MODEL = "claude-sonnet-5-5"

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
    max_tokens_per_request: int = 4096
    max_findings: int = 20
    subprocess_timeout_s: int = 60
    verify: bool = True
    deny_patterns: tuple[str, ...] = DENY_PATTERNS


def load_config(env: Mapping[str, str] | None = None, **overrides: Any) -> Config:
    env = os.environ if env is None else env
    values: dict[str, Any] = {}
    if env.get("MYTOOL_MODEL"):
        values["model"] = env["MYTOOL_MODEL"]
    values.update({k: v for k, v in overrides.items() if v is not None})
    return Config(**values)


def has_api_key(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return bool(env.get("ANTHROPIC_API_KEY"))


def is_denied(path: Path, patterns: Iterable[str]) -> bool:
    name = path.name.lower()
    return any(fnmatch(name, p.lower()) for p in patterns)
