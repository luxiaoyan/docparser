# PDF Parser Milestone 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the phase-1 parsing skeleton for PDF upload, task creation, local storage, PDF validation, task state tracking, and basic pypdf/PyMuPDF preflight.

**Architecture:** Implement a small FastAPI application backed by focused domain services. Keep PDF preflight independent from the API layer so it can be tested without HTTP and later reused by async workers. Use local filesystem storage and an in-memory task repository for milestone 1.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pypdf, optional PyMuPDF, pytest, httpx/TestClient.

---

## Files

- Create: `pyproject.toml` for project metadata, dependencies, and pytest config.
- Create: `src/docparser/__init__.py` package marker.
- Create: `src/docparser/config.py` for phase-1 limits and storage paths.
- Create: `src/docparser/models.py` for task states, document records, preflight metadata, and API response models.
- Create: `src/docparser/storage.py` for local file storage.
- Create: `src/docparser/pdf_preflight.py` for PDF validation and pypdf/PyMuPDF preflight.
- Create: `src/docparser/tasks.py` for in-memory task/document repository.
- Create: `src/docparser/app.py` for FastAPI routes.
- Create: `tests/test_storage.py` for local storage behavior.
- Create: `tests/test_pdf_preflight.py` for PDF validation and metadata extraction.
- Create: `tests/test_tasks.py` for task state transitions.
- Create: `tests/test_app.py` for upload and status APIs.
- Create: `README.md` with local run and test instructions.

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/docparser/__init__.py`
- Create: `README.md`

- [ ] **Step 1: Write dependency and test configuration**

Create `pyproject.toml` with:

```toml
[project]
name = "docparser"
version = "0.1.0"
description = "PDF-only document parsing service skeleton"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "python-multipart>=0.0.9",
  "pydantic>=2",
  "pypdf>=5",
  "PyMuPDF>=1.24",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Add package marker**

Create `src/docparser/__init__.py` with:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 3: Add README**

Create `README.md` with commands for installing dependencies, running tests, and starting the API.

## Task 2: Configuration And Models

**Files:**
- Create: `src/docparser/config.py`
- Create: `src/docparser/models.py`
- Test: `tests/test_tasks.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_tasks.py` with tests that expect a created task to start as `queued`, move to `running`, and reject invalid state transitions.

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_tasks.py -q`

Expected: fail because `docparser.tasks` does not exist.

- [ ] **Step 3: Implement models and config**

Create immutable settings in `config.py`, and Pydantic/dataclass models in `models.py` for:

- `TaskStatus`: `queued`, `running`, `succeeded`, `failed`, `canceled`.
- `DocumentRecord`.
- `ParseTask`.
- `PreflightResult`.
- `ApiError`.

- [ ] **Step 4: Implement task repository**

Create `tasks.py` with `InMemoryTaskRepository` that can create documents, create tasks, retrieve tasks, and update status using allowed transitions.

- [ ] **Step 5: Run GREEN test**

Run: `python -m pytest tests/test_tasks.py -q`

Expected: pass.

## Task 3: Local Storage

**Files:**
- Create: `src/docparser/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Test that saving bytes returns a document storage key, creates the file on disk, computes sha256, and rejects non-PDF filenames.

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_storage.py -q`

Expected: fail because `LocalDocumentStorage` is not implemented.

- [ ] **Step 3: Implement storage**

Create `LocalDocumentStorage.save_pdf(filename: str, content: bytes) -> StoredFile` that:

- normalizes filename,
- rejects non-PDF extension,
- computes sha256,
- writes to `<storage_root>/<document_id>/original.pdf`,
- returns document id, filename, storage key, size, and sha256.

- [ ] **Step 4: Run GREEN test**

Run: `python -m pytest tests/test_storage.py -q`

Expected: pass.

## Task 4: PDF Preflight

**Files:**
- Create: `src/docparser/pdf_preflight.py`
- Test: `tests/test_pdf_preflight.py`

- [ ] **Step 1: Write failing preflight tests**

Test three behaviors:

- invalid magic bytes are rejected;
- generated one-page PDF returns `page_count == 1`;
- page limit is enforced.

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_pdf_preflight.py -q`

Expected: fail because `PdfPreflightService` is not implemented.

- [ ] **Step 3: Implement preflight**

Create `PdfPreflightService.inspect(path: Path) -> PreflightResult` that:

- verifies `%PDF-` magic bytes;
- uses pypdf to read encryption state, page count, metadata, and AcroForm fields;
- uses PyMuPDF when installed to enrich page sizes and renderability diagnostics;
- raises `PdfValidationError` with stable error codes for invalid, encrypted, corrupted, or over-limit PDFs.

- [ ] **Step 4: Run GREEN test**

Run: `python -m pytest tests/test_pdf_preflight.py -q`

Expected: pass.

## Task 5: FastAPI App

**Files:**
- Create: `src/docparser/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing API tests**

Test:

- `GET /health` returns `{"status": "ok"}`;
- `POST /documents` accepts a PDF and returns `document_id`, `task_id`, and `status`;
- `GET /tasks/{task_id}` returns task status;
- uploading a `.txt` file returns HTTP 400.

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_app.py -q`

Expected: fail because `docparser.app` does not exist.

- [ ] **Step 3: Implement API**

Create a FastAPI app factory `create_app()` with:

- `GET /health`;
- `POST /documents`;
- `GET /tasks/{task_id}`;
- dependency-injected repository, storage, and preflight service;
- stable JSON errors.

- [ ] **Step 4: Run GREEN test**

Run: `python -m pytest tests/test_app.py -q`

Expected: pass.

## Task 6: Full Verification

**Files:**
- Modify: docs or code only if verification reveals issues.

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Check project files**

Run: `rg --files`

Expected: includes `src/docparser/...`, `tests/...`, `pyproject.toml`, and the design/plan docs.

- [ ] **Step 3: Commit handling**

This workspace is not a valid git repository, so do not run commit commands. Report that commit was skipped because `git rev-parse --git-dir` fails.
