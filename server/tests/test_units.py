"""Contracts and adapter selection."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from server.adapters import adapter_from_env
from server.adapters.core_adapter import CoreAdapter
from server.adapters.mock import MockAdapter
from server.contracts import Patch
from server.errors import AdapterError


def test_unified_diff() -> None:
    patch = Patch(file="src/a.py", original_text="a = 1\nb = 2\n", new_text="a = 1\nb = 3\n")
    diff = patch.unified_diff()
    assert "--- a/src/a.py" in diff
    assert "+++ b/src/a.py" in diff
    assert "-b = 2" in diff
    assert "+b = 3" in diff


def test_adapter_env_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYTOOL_UI_ADAPTER", "mock")
    assert isinstance(adapter_from_env(), MockAdapter)


def test_adapter_env_default_is_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MYTOOL_UI_ADAPTER", raising=False)
    assert isinstance(adapter_from_env(), MockAdapter)


def test_adapter_env_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYTOOL_UI_ADAPTER", "core")
    assert isinstance(adapter_from_env(), CoreAdapter)


def test_adapter_env_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYTOOL_UI_ADAPTER", "bogus")
    with pytest.raises(ValueError, match="bogus"):
        adapter_from_env()


def test_core_adapter_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    adapter = CoreAdapter()
    assert not adapter.api_key_configured()
    with pytest.raises(AdapterError) as info:
        adapter.analyze(tmp_path, verify=True, on_progress=lambda _: None, cancel=threading.Event())
    assert info.value.code == "api_key_missing"
