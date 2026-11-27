"""Request/response models that exist only at the HTTP layer of the UI server."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    """User-facing error. ``message`` is Turkish and never contains a traceback."""

    code: str
    message: str


class AnalyzeRequest(BaseModel):
    path: str = Field(min_length=1)
    verify: bool = True


class AnalyzeStarted(BaseModel):
    job_id: str


class ApplyRequest(BaseModel):
    job_id: str
    suggestion_ids: list[str] = Field(min_length=1)


class ApplyResponse(BaseModel):
    applied_ids: list[str]
    changed_files: list[str]
    backup_path: str


class BrowseEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class BrowseResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[BrowseEntry]


class HealthResponse(BaseModel):
    status: str
    adapter: str
    api_key_configured: bool
