# Test Case Generator

An AI-powered test case generation platform for QA teams. It analyzes product requirements, backend APIs, and frontend flows, then generates structured test cases and executable automation suites from one clean web interface.

## Problem Statement

Writing comprehensive test cases manually takes a lot of time and often misses edge cases. QA teams need a faster way to turn requirements, API behavior, and application flows into reliable test coverage.

## Solution

Test Case Generator provides a full-stack AI assistant that helps QA teams:

- Upload requirement documents such as TXT, Markdown, PDF, DOCX, and XLSX.
- Add backend/API/frontend source code context from a local path or GitHub repository.
- Generate unit, integration, end-to-end, API, and edge-case test scenarios.
- Convert generated test cases into executable automation code.
- Download generated test case files and automation suites.

## Features

- Professional React frontend with light and dark theme support.
- FastAPI backend that wraps the existing TestTeller generation engine.
- RAG-based context retrieval using ChromaDB.
- Multi-provider LLM support through environment variables.
- Supports Gemini, OpenAI, Claude, and local Llama/Ollama configuration.
- Generates automation for Python, JavaScript, TypeScript, and Java test stacks.
- In-memory job tracking for long-running ingestion and generation tasks.
- Downloadable generated artifacts.

## Tech Stack

- Frontend: React, Vite, TypeScript, Tailwind CSS, Framer Motion, lucide-react
- Backend: Python, FastAPI, Uvicorn
- AI/RAG: LLM provider APIs, ChromaDB
- Test generation core: TestTeller agent logic
- Container support: Docker and Docker Compose

## Project Structure

```text
frontend/                 React web app
testteller/api/           FastAPI backend routes, jobs, and services
testteller/               Core test generation and automation logic
tests/                    Unit tests
docker-compose.yml        Full stack container setup
.env.example              Safe sample environment file
```

## Setup

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
```

Create a local `.env` file from the safe example:

```powershell
copy .env.example .env
```

Add your API key to `.env`:

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_api_key_here
```

Do not commit `.env`.

## Run Locally

Start the backend from the project root:

```powershell
python -m testteller.main serve --host 127.0.0.1 --port 8080
```

Start the frontend in another terminal:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

Open the app:

```text
http://127.0.0.1:3000
```

If port `3000` is already busy, Vite will show another local URL such as `http://127.0.0.1:3001`.

## Docker

```powershell
docker compose up --build
```

Frontend:

```text
http://127.0.0.1:3000
```

Backend health check:

```text
http://127.0.0.1:8080/api/health
```

## API Endpoints

- `GET /api/health`
- `GET /api/config/options`
- `GET /api/collections/{collection}/status`
- `POST /api/ingest/documents`
- `POST /api/ingest/code`
- `POST /api/generate`
- `POST /api/automate`
- `GET /api/jobs/{job_id}`
- `GET /api/artifacts/{artifact_id}/download`

## Testing

Run backend API tests:

```powershell
python -m pytest tests\unit\test_api.py -q
```

Build frontend:

```powershell
cd frontend
npm run build
```

## Environment Safety

Real API keys must stay in `.env`, which is ignored by git. Commit only `.env.example` with placeholder values.
