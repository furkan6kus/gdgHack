"""Adapter selection via the MYTOOL_UI_ADAPTER environment variable."""

from __future__ import annotations

import os

from server.adapters.base import Adapter
from server.adapters.core_adapter import CoreAdapter
from server.adapters.mock import MockAdapter


def adapter_from_env() -> Adapter:
    """Return the adapter named by ``MYTOOL_UI_ADAPTER`` (mock|core, default mock)."""
    choice = os.environ.get("MYTOOL_UI_ADAPTER", "mock").strip().lower()
    if choice == "core":
        return CoreAdapter()
    if choice == "mock":
        return MockAdapter.from_env()
    raise ValueError(f"Unknown MYTOOL_UI_ADAPTER: {choice!r} (expected mock|core)")
