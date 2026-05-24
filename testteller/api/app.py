"""FastAPI application for TestTeller."""

from __future__ import annotations

import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from testteller._version import __version__
from testteller.config import settings
from testteller.core.constants import (
    APP_NAME,
    DEFAULT_AUTOMATION_FRAMEWORK,
    DEFAULT_AUTOMATION_LANGUAGE,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_TEST_OUTPUT_FORMAT,
    SUPPORTED_FRAMEWORKS,
    SUPPORTED_LANGUAGES,
    SUPPORTED_LLM_PROVIDERS,
    SUPPORTED_TEST_OUTPUT_FORMATS,
)
from testteller.generator_agent.agent import TestTellerRagAgent

from .jobs import artifacts, jobs
from .models import (
    AutomateRequest,
    CodeIngestRequest,
    CollectionStatusResponse,
    ConfigOptionsResponse,
    GenerateRequest,
    HealthResponse,
    JobResponse,
    JobStatus,
)
from .services import (
    SUPPORTED_UPLOAD_EXTENSIONS,
    UPLOAD_DIR,
    automate_job,
    ensure_runtime_dirs,
    generate_job,
    get_chromadb_info,
    ingest_code_job,
    ingest_documents_job,
    validate_language_framework,
    validate_output_format,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    yield


app = FastAPI(
    title="TestTeller API",
    version=__version__,
    description="HTTP API for AI-assisted QA test generation and automation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    provider = settings.llm.provider if settings and settings.llm else "unknown"
    return HealthResponse(
        status="ok",
        app=APP_NAME,
        version=__version__,
        provider=provider,
        chromadb=get_chromadb_info(),
    )


@app.get("/api/config/options", response_model=ConfigOptionsResponse)
async def config_options() -> ConfigOptionsResponse:
    return ConfigOptionsResponse(
        providers=SUPPORTED_LLM_PROVIDERS,
        languages=SUPPORTED_LANGUAGES,
        frameworks=SUPPORTED_FRAMEWORKS,
        output_formats=SUPPORTED_TEST_OUTPUT_FORMATS,
        defaults={
            "collection_name": DEFAULT_COLLECTION_NAME,
            "language": DEFAULT_AUTOMATION_LANGUAGE,
            "framework": DEFAULT_AUTOMATION_FRAMEWORK,
            "output_format": DEFAULT_TEST_OUTPUT_FORMAT,
        },
    )


@app.get("/api/collections/{collection}/status", response_model=CollectionStatusResponse)
async def collection_status(collection: str) -> CollectionStatusResponse:
    agent = TestTellerRagAgent(collection_name=collection)
    try:
        count = await agent.get_ingested_data_count()
        return CollectionStatusResponse(
            collection=collection,
            count=count,
            chromadb=get_chromadb_info(agent),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if hasattr(agent, "close"):
            agent.close()


@app.post("/api/ingest/documents", response_model=JobResponse)
async def ingest_documents(
    files: Annotated[list[UploadFile] | None, File()] = None,
    path: Annotated[str | None, Form()] = None,
    collection_name: Annotated[str | None, Form()] = None,
    enhanced: Annotated[bool, Form()] = True,
    chunk_size: Annotated[int, Form(ge=100, le=5000)] = 1000,
) -> JobResponse:
    try:
        source_path = await _resolve_document_source(files, path)
        status = await jobs.create(
            "Document ingestion queued",
            lambda job_id: ingest_documents_job(
                job_id,
                str(source_path),
                collection_name,
                enhanced,
                chunk_size,
            ),
        )
        return JobResponse(job_id=status.job_id, state=status.state, message=status.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ingest/code", response_model=JobResponse)
async def ingest_code(payload: CodeIngestRequest) -> JobResponse:
    status = await jobs.create(
        "Code ingestion queued",
        lambda job_id: ingest_code_job(
            job_id,
            payload.source_path,
            payload.collection_name,
            payload.no_cleanup_github,
        ),
    )
    return JobResponse(job_id=status.job_id, state=status.state, message=status.message)


@app.post("/api/generate", response_model=JobResponse)
async def generate(payload: GenerateRequest) -> JobResponse:
    try:
        validate_output_format(payload.output_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status = await jobs.create(
        "Test generation queued",
        lambda job_id: generate_job(
            job_id,
            payload.query,
            payload.collection_name,
            payload.num_retrieved,
            payload.output_format,
        ),
    )
    return JobResponse(job_id=status.job_id, state=status.state, message=status.message)


@app.post("/api/automate", response_model=JobResponse)
async def automate(payload: AutomateRequest) -> JobResponse:
    try:
        validate_language_framework(payload.language, payload.framework)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status = await jobs.create(
        "Automation generation queued",
        lambda job_id: automate_job(
            job_id,
            payload.test_case_content,
            payload.artifact_id,
            payload.collection_name,
            payload.language,
            payload.framework,
            payload.num_context_docs,
        ),
    )
    return JobResponse(job_id=status.job_id, state=status.state, message=status.message)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def job_status(job_id: str) -> JobStatus:
    status = await jobs.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@app.get("/api/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str) -> FileResponse:
    artifact = artifacts.get(artifact_id)
    if not artifact or not artifact.path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(
        artifact.path,
        media_type=artifact.media_type,
        filename=artifact.name,
    )


async def _resolve_document_source(files: list[UploadFile] | None, path: str | None) -> Path:
    if path:
        source = Path(path)
        if not source.exists():
            raise ValueError(f"Path does not exist: {path}")
        return source

    if not files:
        raise ValueError("Upload at least one document or provide a server-side path.")

    batch_dir = UPLOAD_DIR / f"docs-{len(list(UPLOAD_DIR.glob('docs-*'))) + 1}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
            raise ValueError(
                f"Unsupported file '{upload.filename}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_UPLOAD_EXTENSIONS))}"
            )
        destination = batch_dir / Path(upload.filename or "document").name
        with destination.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
    return batch_dir
