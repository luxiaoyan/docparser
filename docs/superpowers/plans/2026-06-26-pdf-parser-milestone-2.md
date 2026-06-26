# PDF Parser Milestone 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deployable milestone-2 parse pipeline that produces a unified parse result after PDF upload and can run in Docker.

**Architecture:** Keep milestone 2 synchronous and in-process so the service is demonstrable without queue infrastructure. Add a MinerU-compatible parser boundary with a PyMuPDF native-text fallback, persist parse results in the existing in-memory repository, and expose `GET /documents/{document_id}/parse-result`. Docker uses `uv sync --frozen` and runs the same FastAPI app.

**Tech Stack:** Python 3.12, FastAPI, uv, pypdf, PyMuPDF, pytest, Docker, Docker Compose.

---

## Files

- Modify: `src/docparser/config.py` for parser command settings.
- Modify: `src/docparser/models.py` for unified parse result dataclasses.
- Create: `src/docparser/parser.py` for MinerU-compatible parser boundary and fallback parser.
- Modify: `src/docparser/tasks.py` for parse result storage.
- Modify: `src/docparser/app.py` for parsing during upload and result query API.
- Modify: `src/docparser/web/index.html` to surface parse-result links and responses.
- Create: `tests/test_parser.py` for parser result behavior.
- Modify: `tests/test_tasks.py` for parse result repository behavior.
- Modify: `tests/test_app.py` for upload and parse-result API behavior.
- Create: `Dockerfile` for container build.
- Create: `docker-compose.yml` for local deployment.
- Modify: `.dockerignore` for small Docker contexts.
- Modify: `README.md` with Docker deployment commands.

## Task 1: Parser Result Model And Fallback Parser

**Files:**
- Modify: `src/docparser/models.py`
- Create: `src/docparser/parser.py`
- Test: `tests/test_parser.py`

- [ ] **Step 1: Write failing parser tests**

Create tests that write a one-page PDF with PyMuPDF text, parse it with `MinerUParser`, and assert:

- `document.document_id` is preserved;
- `content.markdown` contains the PDF text;
- at least one text block is returned;
- `sources[0].engine` is `mineru`;
- warnings mention native fallback when a MinerU command is not configured.

- [ ] **Step 2: Run RED test**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_parser.py -q`

Expected: fail because `docparser.parser` does not exist.

- [ ] **Step 3: Implement model and parser**

Add dataclasses for file metadata, document metadata, text blocks, source info, parsed content, and unified parse result. Implement `MinerUParser.parse(document, path, preflight)` with a native fallback that uses PyMuPDF text extraction and produces stable result dictionaries.

- [ ] **Step 4: Run GREEN test**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_parser.py -q`

Expected: pass.

## Task 2: Store Parse Results

**Files:**
- Modify: `src/docparser/tasks.py`
- Test: `tests/test_tasks.py`

- [ ] **Step 1: Write failing repository test**

Add a test that stores a parse result for a document and retrieves it by document id.

- [ ] **Step 2: Run RED test**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_tasks.py -q`

Expected: fail because parse-result repository methods do not exist.

- [ ] **Step 3: Implement result storage**

Add `store_parse_result(document_id, result)` and `get_parse_result(document_id)` methods plus `ParseResultNotFound`.

- [ ] **Step 4: Run GREEN test**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_tasks.py -q`

Expected: pass.

## Task 3: API Parse Pipeline

**Files:**
- Modify: `src/docparser/app.py`
- Modify: `src/docparser/config.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing API tests**

Add tests that upload a generated PDF, expect the returned task status to be `succeeded`, and then call `GET /documents/{document_id}/parse-result` to inspect `content.markdown`.

- [ ] **Step 2: Run RED test**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_app.py -q`

Expected: fail because the API does not parse or expose results.

- [ ] **Step 3: Implement API pipeline**

Wire `MinerUParser` into `create_app`. After upload and preflight, create task, transition it to `running`, parse, store result, and transition to `succeeded`. On parse failure, transition to `failed` and return a stable error. Add `GET /documents/{document_id}/parse-result`.

- [ ] **Step 4: Run GREEN test**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_app.py -q`

Expected: pass.

## Task 4: Frontend Update

**Files:**
- Modify: `src/docparser/web/index.html`

- [ ] **Step 1: Add parse result fetch behavior**

After upload succeeds, request `GET /documents/{document_id}/parse-result` and show the unified parse result JSON in the response panel.

- [ ] **Step 2: Verify through tests**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_app.py -q`

Expected: pass, including the root-page smoke test.

## Task 5: Docker Deployment

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Modify: `README.md`

- [ ] **Step 1: Add Docker files**

Use `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` as the base image. Copy `pyproject.toml`, `uv.lock`, and source files. Run `uv sync --frozen --no-dev`. Expose port `8000` and start `uv run uvicorn docparser.app:app --host 0.0.0.0 --port 8000`.

- [ ] **Step 2: Add README deployment commands**

Document:

```bash
docker compose up --build
curl http://127.0.0.1:8000/health
```

- [ ] **Step 3: Verify Docker deployment**

Run: `docker compose up --build -d`, `docker compose ps`, `curl http://127.0.0.1:8000/health`, and `docker compose logs --tail=100`.

Expected: service is healthy and returns `{"status":"ok"}`.

## Task 6: Full Verification

**Files:**
- Modify only if verification reveals a defect.

- [ ] **Step 1: Run full test suite**

Run: `UV_CACHE_DIR=.uv-cache uv run pytest`

Expected: all tests pass.

- [ ] **Step 2: Verify deployment state**

Run: `docker compose ps`

Expected: app container is running.

- [ ] **Step 3: Git handling**

Do not commit. This workspace is not a valid git repository: `git rev-parse --git-dir` fails.
