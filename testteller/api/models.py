"""Pydantic models used by the TestTeller API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


JobState = Literal["queued", "running", "completed", "failed"]


class ArtifactInfo(BaseModel):
    id: str
    name: str
    kind: str
    size: int | None = None
    download_url: str


class JobResponse(BaseModel):
    job_id: str
    state: JobState
    message: str


class JobStatus(BaseModel):
    job_id: str
    state: JobState
    message: str
    progress: int = Field(ge=0, le=100)
    result: dict[str, Any] | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    provider: str
    chromadb: dict[str, Any]


class ConfigOptionsResponse(BaseModel):
    providers: list[str]
    languages: list[str]
    frameworks: dict[str, list[str]]
    output_formats: list[str]
    defaults: dict[str, Any]


class CollectionStatusResponse(BaseModel):
    collection: str
    count: int
    chromadb: dict[str, Any]


class CodeIngestRequest(BaseModel):
    source_path: str = Field(min_length=1)
    collection_name: str | None = None
    no_cleanup_github: bool = False


class GenerateRequest(BaseModel):
    query: str = Field(min_length=1)
    collection_name: str | None = None
    num_retrieved: int = Field(default=5, ge=0, le=20)
    output_format: str = "md"


class AutomateRequest(BaseModel):
    test_case_content: str | None = None
    artifact_id: str | None = None
    collection_name: str | None = None
    language: str = "python"
    framework: str = "pytest"
    num_context_docs: int = Field(default=5, ge=1, le=20)

