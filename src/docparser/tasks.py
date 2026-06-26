from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from typing import Any

from docparser.models import DocumentRecord, ExtractionResult, ParseTask, TaskStatus, UnifiedParseResult
from docparser.schema import ExtractionNotFound, SchemaNotFound, SchemaValidationError


class InvalidTaskTransition(ValueError):
    pass


class TaskNotFound(KeyError):
    pass


class DocumentNotFound(KeyError):
    pass


class ParseResultNotFound(KeyError):
    pass


class InMemoryTaskRepository:
    _ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELED},
        TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELED},
        TaskStatus.SUCCEEDED: set(),
        TaskStatus.FAILED: set(),
        TaskStatus.CANCELED: set(),
    }

    def __init__(self) -> None:
        self._documents: dict[str, DocumentRecord] = {}
        self._tasks: dict[str, ParseTask] = {}
        self._parse_results: dict[str, UnifiedParseResult] = {}
        self._schemas: dict[str, dict[str, Any]] = {}
        self._extraction_results: dict[str, ExtractionResult] = {}

    def create_document(
        self,
        filename: str,
        storage_key: str,
        sha256: str,
        size_bytes: int,
    ) -> DocumentRecord:
        document_id = f"doc_{uuid4().hex}"
        document = DocumentRecord(
            document_id=document_id,
            filename=filename,
            storage_key=storage_key,
            sha256=sha256,
            size_bytes=size_bytes,
        )
        self._documents[document_id] = document
        return document

    def get_document(self, document_id: str) -> DocumentRecord:
        try:
            return self._documents[document_id]
        except KeyError as exc:
            raise DocumentNotFound(document_id) from exc

    def create_parse_task(self, document_id: str) -> ParseTask:
        self.get_document(document_id)
        task_id = f"task_{uuid4().hex}"
        task = ParseTask(task_id=task_id, document_id=document_id, status=TaskStatus.QUEUED)
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> ParseTask:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise TaskNotFound(task_id) from exc

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        progress: int | None = None,
        error: str | None = None,
    ) -> ParseTask:
        task = self.get_task(task_id)
        allowed = self._ALLOWED_TRANSITIONS[task.status]
        if status not in allowed:
            raise InvalidTaskTransition(f"Cannot transition task {task_id} from {task.status} to {status}")

        updated = replace(
            task,
            status=status,
            progress=progress if progress is not None else task.progress,
            error=error,
            updated_at=datetime.now(UTC),
        )
        self._tasks[task_id] = updated
        return updated

    def store_parse_result(self, document_id: str, result: UnifiedParseResult) -> None:
        self.get_document(document_id)
        if result.document_id != document_id:
            raise ValueError("Parse result document_id does not match requested document_id")
        self._parse_results[document_id] = result

    def get_parse_result(self, document_id: str) -> UnifiedParseResult:
        self.get_document(document_id)
        try:
            return self._parse_results[document_id]
        except KeyError as exc:
            raise ParseResultNotFound(document_id) from exc

    def upsert_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        schema_id = str(schema.get("schema_id") or "")
        if not schema_id:
            raise SchemaValidationError("schema_id is required")
        stored = dict(schema)
        stored.setdefault("fields", [])
        self._schemas[schema_id] = stored
        return stored

    def list_schemas(self) -> list[dict[str, Any]]:
        return list(self._schemas.values())

    def get_schema(self, schema_id: str) -> dict[str, Any]:
        try:
            return self._schemas[schema_id]
        except KeyError as exc:
            raise SchemaNotFound(schema_id) from exc

    def delete_schema(self, schema_id: str) -> bool:
        try:
            del self._schemas[schema_id]
        except KeyError as exc:
            raise SchemaNotFound(schema_id) from exc
        return True

    def store_extraction_result(self, result: ExtractionResult) -> None:
        self._extraction_results[result.extraction_id] = result

    def get_extraction_result(self, extraction_id: str) -> ExtractionResult:
        try:
            return self._extraction_results[extraction_id]
        except KeyError as exc:
            raise ExtractionNotFound(extraction_id) from exc
