"""In-memory job and artifact registries for the API v1."""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .models import ArtifactInfo, JobStatus


@dataclass
class StoredArtifact:
    id: str
    path: Path
    name: str
    kind: str

    @property
    def media_type(self) -> str:
        return mimetypes.guess_type(self.path.name)[0] or "application/octet-stream"


class ArtifactRegistry:
    def __init__(self) -> None:
        self._artifacts: dict[str, StoredArtifact] = {}

    def add(self, path: Path, kind: str, name: str | None = None) -> ArtifactInfo:
        artifact_id = uuid.uuid4().hex
        resolved = path.resolve()
        artifact = StoredArtifact(
            id=artifact_id,
            path=resolved,
            name=name or resolved.name,
            kind=kind,
        )
        self._artifacts[artifact_id] = artifact
        size = resolved.stat().st_size if resolved.exists() and resolved.is_file() else None
        return ArtifactInfo(
            id=artifact_id,
            name=artifact.name,
            kind=artifact.kind,
            size=size,
            download_url=f"/api/artifacts/{artifact_id}/download",
        )

    def get(self, artifact_id: str) -> StoredArtifact | None:
        return self._artifacts.get(artifact_id)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobStatus] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        message: str,
        runner: Callable[[str], Awaitable[dict[str, Any] | None]],
    ) -> JobStatus:
        job_id = uuid.uuid4().hex
        status = JobStatus(job_id=job_id, state="queued", message=message, progress=0)
        async with self._lock:
            self._jobs[job_id] = status

        asyncio.create_task(self._run(job_id, runner))
        return status

    async def get(self, job_id: str) -> JobStatus | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(
        self,
        job_id: str,
        *,
        state: str | None = None,
        message: str | None = None,
        progress: int | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        async with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(
                update={
                    "state": state or current.state,
                    "message": message or current.message,
                    "progress": current.progress if progress is None else progress,
                    "result": current.result if result is None else result,
                    "error": error,
                }
            )

    async def _run(
        self,
        job_id: str,
        runner: Callable[[str], Awaitable[dict[str, Any] | None]],
    ) -> None:
        try:
            await self.update(job_id, state="running", progress=10)
            result = await runner(job_id)
            await self.update(
                job_id,
                state="completed",
                message="Completed",
                progress=100,
                result=result or {},
            )
        except Exception as exc:  # pragma: no cover - defensive job boundary
            await self.update(
                job_id,
                state="failed",
                message="Failed",
                progress=100,
                error=str(exc),
            )


artifacts = ArtifactRegistry()
jobs = JobManager()
