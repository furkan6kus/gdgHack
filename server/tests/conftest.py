"""Shared fixtures and helpers for the UI server tests."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.adapters.mock import MockAdapter, Scenario
from server.app import create_app

SseEvent = tuple[str, Any]
ClientFactory = Callable[..., Any]


def parse_sse(client: TestClient, url: str) -> list[SseEvent]:
    """Read an SSE stream to its end and return ``(event, json_data)`` tuples."""
    events: list[SseEvent] = []
    name: str | None = None
    with client.stream("GET", url) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("event:"):
                name = line.removeprefix("event:").strip()
            elif line.startswith("data:") and name is not None:
                events.append((name, json.loads(line.removeprefix("data:").strip())))
                name = None
    return events


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[ClientFactory]:
    """Factory yielding TestClients for a MockAdapter; all are closed at teardown."""
    dist = tmp_path / "no-dist"  # no index.html: frontend is not mounted
    opened: list[TestClient] = []

    def factory(scenario: Scenario = "ok", delay_scale: float = 0) -> TestClient:
        adapter = MockAdapter(scenario=scenario, delay_scale=delay_scale)
        client = TestClient(create_app(adapter, dist_dir=dist), base_url="http://127.0.0.1")
        client.__enter__()
        opened.append(client)
        return client

    yield factory
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    result: TestClient = make_client()
    return result


def run_job(client: TestClient, root: Path, **body: Any) -> tuple[str, list[SseEvent]]:
    """Start an analysis and return ``(job_id, events)`` once the stream ends."""
    response = client.post("/api/analyze", json={"path": str(root), **body})
    assert response.status_code == 200, response.text
    job_id: str = response.json()["job_id"]
    return job_id, parse_sse(client, f"/api/analyze/{job_id}/events")


def result_of(events: list[SseEvent]) -> dict[str, Any]:
    assert events[-1][0] == "result"
    data: dict[str, Any] = events[-1][1]
    return data
