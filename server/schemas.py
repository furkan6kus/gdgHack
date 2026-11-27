"""Request/response models that exist only at the HTTP layer of the UI server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from server.contracts import LLMChoice


class ErrorPayload(BaseModel):
    """User-facing error. ``message`` is Turkish and never contains a traceback."""

    code: str
    message: str


class AnalyzeRequest(BaseModel):
    path: str = Field(min_length=1)
    verify: bool = True
    llm: LLMChoice | None = None


class AnalyzeStarted(BaseModel):
    job_id: str


class ApplyRequest(BaseModel):
    job_id: str
    suggestion_ids: list[str] = Field(min_length=1)


class ApplyResponse(BaseModel):
    applied_ids: list[str]
    changed_files: list[str]
    backup_path: str
    history_id: str | None = None


class BrowseEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class BrowseResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[BrowseEntry]


class Place(BaseModel):
    name: str
    path: str
    kind: Literal["home", "folder", "drive"]


class HealthResponse(BaseModel):
    status: str
    adapter: str
    api_key_configured: bool
    telegram_configured: bool = False


class PickRequest(BaseModel):
    kind: Literal["files", "folder"] = "files"
    initial_dir: str | None = None


class PickResponse(BaseModel):
    paths: list[str]


class CloneRequest(BaseModel):
    url: str = Field(min_length=1, max_length=300)


class ModelInfo(BaseModel):
    id: str
    name: str
    note: str
    input_per_mtok: float
    output_per_mtok: float


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    default_model: str
    default_effort: str
