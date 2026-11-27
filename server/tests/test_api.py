"""HTTP API: health, analyze, SSE streaming, cancel."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import ClientFactory, parse_sse, result_of, run_job

STAGES = ["parsing", "static_analysis", "llm", "verify", "done"]


def test_health_ok(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "adapter": "mock", "api_key_configured": True}


def test_health_no_key(make_client: ClientFactory) -> None:
    body = make_client("no_key").get("/api/health").json()
    assert body["api_key_configured"] is False


def test_analyze_returns_job_id(client: TestClient, project: Path) -> None:
    response = client.post("/api/analyze", json={"path": str(project)})
    assert response.status_code == 200
    assert response.json()["job_id"]


def test_analyze_missing_path(client: TestClient, project: Path) -> None:
    response = client.post("/api/analyze", json={"path": str(project / "nope")})
    assert response.status_code == 404
    assert response.json()["code"] == "path_not_found"


def test_analyze_single_file(client: TestClient, project: Path) -> None:
    file = project / "a.py"
    file.write_text("x = 1\n")
    _, events = run_job(client, file)
    assert events[-1][0] == "result"


def test_analyze_requires_json(client: TestClient, project: Path) -> None:
    response = client.post("/api/analyze", data={"path": str(project)})
    assert response.status_code == 415


def test_analyze_empty_path_is_422_without_traceback(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"path": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert "Traceback" not in response.text


def test_stage_order_and_result_last(client: TestClient, project: Path) -> None:
    _, events = run_job(client, project)
    names = [name for name, _ in events]
    assert names[-1] == "result"
    assert names.count("result") == 1
    assert set(names[:-1]) == {"progress"}
    stages = [data["stage"] for name, data in events if name == "progress"]
    order = [STAGES.index(s) for s in stages]
    assert order == sorted(order)
    assert set(stages) == set(STAGES)


def test_progress_current_increases_within_stage(client: TestClient, project: Path) -> None:
    _, events = run_job(client, project)
    last: dict[str, int] = {}
    for name, data in events:
        if name == "progress" and data["current"] is not None:
            assert data["current"] > last.get(data["stage"], 0)
            last[data["stage"]] = data["current"]
    assert last


def test_result_hides_failed_suggestions(client: TestClient, project: Path) -> None:
    _, events = run_job(client, project)
    result = result_of(events)
    assert result["findings"]
    assert result["files"]
    assert result["suggestions"]
    statuses = {s["verification"]["status"] for s in result["suggestions"]}
    assert "failed" not in statuses
    assert "S6" not in {s["id"] for s in result["suggestions"]}


def test_verify_false_skips_verification(client: TestClient, project: Path) -> None:
    _, events = run_job(client, project, verify=False)
    stages = {data["stage"] for name, data in events if name == "progress"}
    assert "verify" not in stages
    suggestions = result_of(events)["suggestions"]
    assert suggestions
    assert {s["verification"]["status"] for s in suggestions} == {"skipped"}


def test_sse_replay_after_finish(client: TestClient, project: Path) -> None:
    job_id, first = run_job(client, project)
    again = parse_sse(client, f"/api/analyze/{job_id}/events")
    assert again == first
    assert again[-1][0] == "result"


def test_empty_scenario(make_client: ClientFactory, project: Path) -> None:
    _, events = run_job(make_client("empty"), project)
    result = result_of(events)
    assert result["findings"] == []
    assert result["suggestions"] == []
    assert result["files"]


def test_error_scenario(make_client: ClientFactory, project: Path) -> None:
    _, events = run_job(make_client("error"), project)
    errors = [data for name, data in events if name == "error"]
    assert [name for name, _ in events][-1] == "error"
    assert len(errors) == 1
    assert errors[0]["code"] == "analyzer_failed"


def test_no_key_scenario(make_client: ClientFactory, project: Path) -> None:
    _, events = run_job(make_client("no_key"), project)
    assert events == [("error", events[0][1])]
    assert events[0][1]["code"] == "api_key_missing"


def test_unknown_job_events(client: TestClient) -> None:
    response = client.get("/api/analyze/nope/events")
    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_unknown_job_cancel(client: TestClient) -> None:
    assert client.post("/api/analyze/nope/cancel", json={}).status_code == 404


def test_cancel_ends_with_cancelled(make_client: ClientFactory, project: Path) -> None:
    slow = make_client("ok", 1.0)
    job_id = slow.post("/api/analyze", json={"path": str(project)}).json()["job_id"]
    assert slow.post(f"/api/analyze/{job_id}/cancel", json={}).status_code == 204
    events = parse_sse(slow, f"/api/analyze/{job_id}/events")
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "cancelled"
