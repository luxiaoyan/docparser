# PDF Parser Milestones 3 And 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unified-model diagnostics and schema-based field extraction APIs on top of existing parse results.

**Architecture:** Keep storage in-memory for this milestone. Use a focused `SchemaExtractor` service for deterministic strategies and validation, extend the repository with schema/extraction stores, expose CRUD/extraction APIs, and add a compact frontend schema panel that reuses the existing response viewer.

**Tech Stack:** Python 3.12, FastAPI, uv, pytest, built-in `re` and dataclasses.

---

## Files

- Create: `src/docparser/schema.py` for schema validation, extraction strategies, and field normalization.
- Modify: `src/docparser/models.py` for extraction result dataclasses.
- Modify: `src/docparser/tasks.py` for schema and extraction result storage.
- Modify: `src/docparser/app.py` for schema CRUD and extraction APIs.
- Modify: `src/docparser/web/index.html` for a minimal schema/extraction control panel.
- Create: `tests/test_schema.py` for extractor behavior.
- Modify: `tests/test_tasks.py` for repository storage behavior.
- Modify: `tests/test_app.py` for API behavior.
- Modify: `README.md` with milestone 4 API examples.

## Task 1: Deterministic Extractor

- [ ] Write failing tests for form-field and regex extraction.
- [ ] Implement `SchemaExtractor.extract(document_id, schema, parse_result)`.
- [ ] Support required missing warnings and `string`, `number`, `money`, `boolean` normalization.
- [ ] Run `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_schema.py -q`.

## Task 2: Repository Stores

- [ ] Add failing tests for schema CRUD and extraction result storage.
- [ ] Implement schema and extraction result methods in `InMemoryTaskRepository`.
- [ ] Run `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_tasks.py -q`.

## Task 3: API

- [ ] Add failing tests for `POST /schemas`, `GET /schemas`, `GET /schemas/{id}`, `PUT /schemas/{id}`, `DELETE /schemas/{id}`, `POST /documents/{id}/extract`, and `GET /extractions/{id}`.
- [ ] Implement synchronous extraction APIs.
- [ ] Run `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_app.py -q`.

## Task 4: Frontend

- [ ] Add a schema textarea with a default contract-number schema.
- [ ] Add buttons to save schema and extract fields from the latest uploaded document.
- [ ] Keep output in the existing response panel.

## Task 5: Verification

- [ ] Run `UV_CACHE_DIR=.uv-cache uv run pytest`.
- [ ] Restart the local service if needed.
- [ ] Smoke-test schema creation and extraction through HTTP.
- [ ] Do not commit because this workspace is not a valid git repository.
