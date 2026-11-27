"""POST /api/apply rules."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import ClientFactory, parse_sse, run_job

PASSED = "S1"
SKIPPED = "S4"


def _apply(client: TestClient, job_id: str, ids: list[str]) -> tuple[int, dict[str, object]]:
    response = client.post("/api/apply", json={"job_id": job_id, "suggestion_ids": ids})
    return response.status_code, response.json()


def test_apply_passed_succeeds(client: TestClient, project: Path) -> None:
    job_id, _ = run_job(client, project)
    status, body = _apply(client, job_id, [PASSED])
    assert status == 200
    assert body["applied_ids"] == [PASSED]
    assert body["changed_files"]
    backup = Path(str(body["backup_path"]))
    assert backup.parent == project.resolve() / ".mytool" / "backup"


def test_mixed_request_rejected_and_nothing_applied(client: TestClient, project: Path) -> None:
    job_id, _ = run_job(client, project)
    status, body = _apply(client, job_id, [PASSED, SKIPPED])
    assert status == 400
    assert body["code"] == "not_verified"
    assert _apply(client, job_id, [PASSED])[0] == 200


def test_unknown_suggestion(client: TestClient, project: Path) -> None:
    job_id, _ = run_job(client, project)
    status, body = _apply(client, job_id, ["S999"])
    assert (status, body["code"]) == (400, "unknown_suggestion")


def test_failed_suggestion_was_stripped(client: TestClient, project: Path) -> None:
    job_id, _ = run_job(client, project)
    status, body = _apply(client, job_id, ["S6"])
    assert (status, body["code"]) == (400, "unknown_suggestion")


def test_apply_twice_conflicts(client: TestClient, project: Path) -> None:
    job_id, _ = run_job(client, project)
    assert _apply(client, job_id, [PASSED])[0] == 200
    status, body = _apply(client, job_id, [PASSED])
    assert (status, body["code"]) == (409, "already_applied")


def test_empty_ids_is_422(client: TestClient, project: Path) -> None:
    job_id, _ = run_job(client, project)
    assert _apply(client, job_id, [])[0] == 422


def test_unknown_job(client: TestClient) -> None:
    status, body = _apply(client, "nope", [PASSED])
    assert (status, body["code"]) == (404, "job_not_found")


def test_apply_before_finish(make_client: ClientFactory, project: Path) -> None:
    slow = make_client("ok", 1.0)
    job_id = slow.post("/api/analyze", json={"path": str(project)}).json()["job_id"]
    status, body = _apply(slow, job_id, [PASSED])
    assert (status, body["code"]) == (409, "job_not_finished")
    slow.post(f"/api/analyze/{job_id}/cancel", json={})
    parse_sse(slow, f"/api/analyze/{job_id}/events")
