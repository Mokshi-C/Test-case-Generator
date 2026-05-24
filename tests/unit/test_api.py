"""Unit tests for the TestTeller HTTP API."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from testteller.api.app import app
from testteller.api.jobs import JobManager
from testteller.api.services import validate_language_framework, validate_output_format


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "TestTeller"
    assert "chromadb" in body


def test_config_options_endpoint():
    response = client.get("/api/config/options")

    assert response.status_code == 200
    body = response.json()
    assert "gemini" in body["providers"]
    assert "python" in body["languages"]
    assert "pytest" in body["frameworks"]["python"]
    assert "md" in body["output_formats"]


def test_validation_errors():
    try:
        validate_output_format("html")
    except ValueError as exc:
        assert "Unsupported output format" in str(exc)
    else:
        raise AssertionError("Expected invalid output format to raise")

    try:
        validate_language_framework("python", "jest")
    except ValueError as exc:
        assert "Unsupported framework" in str(exc)
    else:
        raise AssertionError("Expected invalid framework to raise")


def test_job_manager_lifecycle():
    async def runner(job_id: str):
        return {"job_id": job_id, "ok": True}

    manager = JobManager()

    import asyncio

    async def execute():
        created = await manager.create("Queued", runner)
        for _ in range(20):
            current = await manager.get(created.job_id)
            if current and current.state == "completed":
                return current
            await asyncio.sleep(0.01)
        return await manager.get(created.job_id)

    status = asyncio.run(execute())

    assert status is not None
    assert status.state == "completed"
    assert status.progress == 100
    assert status.result["ok"] is True


@patch("testteller.api.app.jobs.create", new_callable=AsyncMock)
def test_document_ingestion_creates_job(mock_create, tmp_path: Path):
    document = tmp_path / "requirements.md"
    document.write_text("# Requirements", encoding="utf-8")
    mock_create.return_value = Mock(
        job_id="job-1",
        state="queued",
        message="Document ingestion queued",
    )

    with document.open("rb") as handle:
        response = client.post(
            "/api/ingest/documents",
            files={"files": ("requirements.md", handle, "text/markdown")},
            data={"collection_name": "test_collection"},
        )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-1"
    assert mock_create.await_count == 1


@patch("testteller.api.app.jobs.create", new_callable=AsyncMock)
def test_code_ingestion_creates_job(mock_create):
    mock_create.return_value = Mock(
        job_id="job-2",
        state="queued",
        message="Code ingestion queued",
    )

    response = client.post(
        "/api/ingest/code",
        json={"source_path": "https://github.com/example/app", "collection_name": "test_collection"},
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-2"


@patch("testteller.api.app.jobs.create", new_callable=AsyncMock)
def test_generate_creates_job(mock_create):
    mock_create.return_value = Mock(
        job_id="job-3",
        state="queued",
        message="Test generation queued",
    )

    response = client.post(
        "/api/generate",
        json={
            "query": "Generate API tests",
            "collection_name": "test_collection",
            "num_retrieved": 5,
            "output_format": "md",
        },
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-3"


@patch("testteller.api.app.jobs.create", new_callable=AsyncMock)
def test_automation_creates_job(mock_create):
    mock_create.return_value = Mock(
        job_id="job-4",
        state="queued",
        message="Automation generation queued",
    )

    response = client.post(
        "/api/automate",
        json={
            "test_case_content": "# Test Cases",
            "collection_name": "test_collection",
            "language": "python",
            "framework": "pytest",
            "num_context_docs": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-4"

