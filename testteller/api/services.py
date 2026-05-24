"""Service helpers that adapt TestTeller's CLI-oriented core to HTTP jobs."""

from __future__ import annotations

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from testteller.automator_agent.cli import (
    get_collection_name as get_automation_collection_name,
    initialize_vector_store,
    validate_framework,
)
from testteller.automator_agent.parser.markdown_parser import MarkdownTestCaseParser
from testteller.automator_agent.rag_enhanced_generator import RAGEnhancedTestGenerator
from testteller.config import settings
from testteller.core.constants import (
    DEFAULT_AUTOMATION_FRAMEWORK,
    DEFAULT_AUTOMATION_LANGUAGE,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_TEST_GENERATION_DIR,
    SUPPORTED_FRAMEWORKS,
    SUPPORTED_LANGUAGES,
    SUPPORTED_TEST_OUTPUT_FORMATS,
)
from testteller.core.data_ingestion.unified_document_parser import UnifiedDocumentParser
from testteller.core.llm.llm_manager import LLMManager
from testteller.generator_agent.agent import TestTellerRagAgent
from testteller.main import get_collection_name, save_test_cases_with_format

from .jobs import artifacts, jobs


ROOT_DIR = Path.cwd()
UPLOAD_DIR = ROOT_DIR / "uploads"
GENERATED_DIR = ROOT_DIR / DEFAULT_TEST_GENERATION_DIR
AUTOMATION_DIR = ROOT_DIR / "testteller_automated_tests"

SUPPORTED_UPLOAD_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".xlsx"}


def ensure_runtime_dirs() -> None:
    for directory in (UPLOAD_DIR, GENERATED_DIR, AUTOMATION_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def validate_output_format(output_format: str) -> None:
    if output_format not in SUPPORTED_TEST_OUTPUT_FORMATS:
        raise ValueError(
            f"Unsupported output format '{output_format}'. "
            f"Supported formats: {', '.join(SUPPORTED_TEST_OUTPUT_FORMATS)}"
        )


def validate_language_framework(language: str, framework: str) -> None:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language '{language}'. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    if not validate_framework(language, framework):
        raise ValueError(
            f"Unsupported framework '{framework}' for {language}. "
            f"Supported frameworks: {', '.join(SUPPORTED_FRAMEWORKS[language])}"
        )


def get_chromadb_info(agent: TestTellerRagAgent | None = None) -> dict[str, Any]:
    if agent is not None and getattr(agent, "vector_store", None) is not None:
        vector_store = agent.vector_store
        if getattr(vector_store, "use_remote", False):
            return {
                "mode": "remote",
                "host": getattr(vector_store, "host", None),
                "port": getattr(vector_store, "port", None),
            }
        return {
            "mode": "local",
            "persist_directory": str(getattr(vector_store, "db_path", "")),
        }

    chromadb = settings.chromadb if settings and settings.chromadb else None
    if chromadb and chromadb.use_remote:
        return {"mode": "remote", "host": chromadb.host, "port": chromadb.port}
    return {
        "mode": "local",
        "persist_directory": chromadb.persist_directory if chromadb else "./chroma_data",
    }


async def ingest_documents_job(
    job_id: str,
    path: str,
    collection_name: str | None,
    enhanced: bool,
    chunk_size: int,
) -> dict[str, Any]:
    collection = get_collection_name(collection_name)
    await jobs.update(job_id, message="Ingesting documents", progress=25)
    agent = TestTellerRagAgent(collection_name=collection)
    try:
        await agent.ingest_documents_from_path(path, enhanced_parsing=enhanced, chunk_size=chunk_size)
        count = await agent.get_ingested_data_count()
        await jobs.update(job_id, message="Documents indexed", progress=90)
        return {"collection": collection, "count": count, "path": path}
    finally:
        if hasattr(agent, "close"):
            agent.close()


async def ingest_code_job(
    job_id: str,
    source_path: str,
    collection_name: str | None,
    no_cleanup_github: bool,
) -> dict[str, Any]:
    collection = get_collection_name(collection_name)
    await jobs.update(job_id, message="Analyzing source code", progress=25)
    agent = TestTellerRagAgent(collection_name=collection)
    try:
        await agent.ingest_code_from_source(
            source_path,
            cleanup_github_after=not no_cleanup_github,
        )
        count = await agent.get_ingested_data_count()
        await jobs.update(job_id, message="Source code indexed", progress=90)
        return {"collection": collection, "count": count, "source_path": source_path}
    finally:
        if hasattr(agent, "close"):
            agent.close()


async def generate_job(
    job_id: str,
    query: str,
    collection_name: str | None,
    num_retrieved: int,
    output_format: str,
) -> dict[str, Any]:
    validate_output_format(output_format)
    collection = get_collection_name(collection_name)
    await jobs.update(job_id, message="Retrieving project context", progress=20)
    agent = TestTellerRagAgent(collection_name=collection)
    try:
        test_cases = await agent.generate_test_cases(query, n_retrieved_docs=num_retrieved)
        if "Error:" not in test_cases[:20]:
            await jobs.update(job_id, message="Storing high-quality test case feedback", progress=70)
            if os.getenv("ENABLE_TEST_CASE_FEEDBACK", "true").lower() == "true":
                await agent.store_generated_test_cases(
                    test_cases,
                    query,
                    {"num_retrieved_docs": num_retrieved, "api_job_id": job_id},
                )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = GENERATED_DIR / f"testteller-testcases-{timestamp}.{output_format}"
        actual_path, actual_format = await save_test_cases_with_format(
            test_cases,
            str(output_path),
            output_format,
        )
        artifact = artifacts.add(Path(actual_path), "testcases", Path(actual_path).name)
        await jobs.update(job_id, message="Test cases generated", progress=90)
        return {
            "collection": collection,
            "content": test_cases,
            "artifact": artifact.dict(),
            "output_format": actual_format,
        }
    finally:
        if hasattr(agent, "close"):
            agent.close()


async def automate_job(
    job_id: str,
    test_case_content: str | None,
    artifact_id: str | None,
    collection_name: str | None,
    language: str,
    framework: str,
    num_context_docs: int,
) -> dict[str, Any]:
    validate_language_framework(language, framework)
    collection = get_automation_collection_name(collection_name)
    input_path = await _resolve_automation_input(job_id, test_case_content, artifact_id)
    output_path = AUTOMATION_DIR / f"job-{job_id}"
    output_path.mkdir(parents=True, exist_ok=True)

    await jobs.update(job_id, message="Parsing generated test cases", progress=30)
    parser = MarkdownTestCaseParser()
    parsed_doc = await UnifiedDocumentParser().parse_for_automation(input_path)
    test_cases = parsed_doc.test_cases or parser.parse_file(input_path)
    if not test_cases and parsed_doc.content:
        test_cases = parser.parse_content(parsed_doc.content)
    if not test_cases:
        raise ValueError("No structured test cases were found to automate.")

    await jobs.update(job_id, message="Extracting application context", progress=50)
    vector_store = await asyncio.to_thread(initialize_vector_store, collection)
    llm_manager = LLMManager()
    generator = RAGEnhancedTestGenerator(
        framework=framework,
        output_dir=output_path,
        vector_store=vector_store,
        language=language,
        llm_manager=llm_manager,
        num_context_docs=num_context_docs,
    )

    await jobs.update(job_id, message="Generating executable tests", progress=65)
    generated_files = await generator.generate(test_cases)
    await asyncio.to_thread(generator.write_files, generated_files)

    zip_base = AUTOMATION_DIR / f"testteller-automation-{job_id}"
    zip_path = Path(shutil.make_archive(str(zip_base), "zip", output_path))
    artifact = artifacts.add(zip_path, "automation", zip_path.name)
    files = [
        {"name": name, "content": content, "size": len(content)}
        for name, content in sorted(generated_files.items())
    ]
    await jobs.update(job_id, message="Automation suite generated", progress=90)
    return {
        "collection": collection,
        "language": language,
        "framework": framework,
        "files": files,
        "artifact": artifact.dict(),
    }


async def _resolve_automation_input(
    job_id: str,
    test_case_content: str | None,
    artifact_id: str | None,
) -> Path:
    if test_case_content:
        input_path = UPLOAD_DIR / f"automation-input-{job_id}.md"
        input_path.write_text(test_case_content, encoding="utf-8")
        return input_path

    if artifact_id:
        artifact = artifacts.get(artifact_id)
        if not artifact:
            raise ValueError("Artifact not found.")
        return artifact.path

    raise ValueError("Provide test_case_content or artifact_id.")

