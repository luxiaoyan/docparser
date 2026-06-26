from importlib.resources import files
import json
import logging
from os import getenv
from pathlib import Path
from uuid import uuid4

from docparser.config import ParserSettings
from docparser.models import TaskStatus
from docparser.parser import MinerUParser, ParsePipelineError
from docparser.pdf_preflight import PdfPreflightService, PdfValidationError
from docparser.schema import ExtractionNotFound, SchemaExtractor, SchemaNotFound, SchemaValidationError
from docparser.storage import InvalidFileTypeError, LocalDocumentStorage
from docparser.tasks import DocumentNotFound, InMemoryTaskRepository, ParseResultNotFound, TaskNotFound


class MissingDependencyError(RuntimeError):
    pass


engine_raw_logger = logging.getLogger("docparser.engine_raw")
uvicorn_logger = logging.getLogger("uvicorn.error")


def log_engine_results(document_id: str, result: dict[str, object]) -> None:
    engine_results = result.get("engine_results", {})
    if not isinstance(engine_results, dict):
        return
    for engine, payload in engine_results.items():
        message = json.dumps(
            {
                "document_id": document_id,
                "engine": engine,
                "raw": payload,
            },
            ensure_ascii=False,
            default=str,
        )
        engine_raw_logger.info(message)
        uvicorn_logger.info("engine_raw %s", message)


def create_app(
    *,
    repository: InMemoryTaskRepository | None = None,
    storage: LocalDocumentStorage | None = None,
    preflight: PdfPreflightService | None = None,
    parser: MinerUParser | None = None,
    extractor: SchemaExtractor | None = None,
):
    try:
        from fastapi import FastAPI, File, HTTPException, UploadFile
        from fastapi.responses import FileResponse
    except ModuleNotFoundError as exc:
        raise MissingDependencyError("FastAPI is not installed. Install project dependencies to run the API.") from exc

    settings = ParserSettings(mineru_command=getenv("DOCPARSER_MINERU_COMMAND"))
    repository = repository or InMemoryTaskRepository()
    storage = storage or LocalDocumentStorage(settings.storage_root)
    preflight = preflight or PdfPreflightService(settings)
    parser = parser or MinerUParser(settings.mineru_command)
    extractor = extractor or SchemaExtractor()

    app = FastAPI(title="PDF Document Parser", version="0.1.0")

    @app.get("/", include_in_schema=False)
    def web_console() -> FileResponse:
        index_path = files("docparser.web").joinpath("index.html")
        return FileResponse(index_path)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/documents")
    async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
        content = await file.read()
        try:
            stored = storage.save_pdf(file.filename or "upload.pdf", content)
            document_path = Path(storage.root) / stored.storage_key
            preflight_result = preflight.inspect(document_path)
        except InvalidFileTypeError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILE_TYPE", "message": str(exc)}) from exc
        except PdfValidationError as exc:
            raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc

        document = repository.create_document(
            filename=stored.filename,
            storage_key=stored.storage_key,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
        )
        task = repository.create_parse_task(document.document_id)
        repository.update_task_status(task.task_id, TaskStatus.RUNNING, progress=20)

        try:
            parse_result = parser.parse(document, document_path, preflight_result)
            repository.store_parse_result(document.document_id, parse_result)
            log_engine_results(document.document_id, parse_result.to_dict())
            task = repository.update_task_status(task.task_id, TaskStatus.SUCCEEDED, progress=100)
        except ParsePipelineError as exc:
            repository.update_task_status(task.task_id, TaskStatus.FAILED, error=str(exc))
            raise HTTPException(status_code=500, detail={"code": "PARSER_FAILED", "message": str(exc)}) from exc

        return {"document_id": document.document_id, "task_id": task.task_id, "status": task.status.value}

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, object]:
        try:
            task = repository.get_task(task_id)
        except TaskNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": task_id}) from exc
        return {
            "task_id": task.task_id,
            "document_id": task.document_id,
            "status": task.status.value,
            "progress": task.progress,
            "error": task.error,
        }

    @app.get("/documents/{document_id}/parse-result")
    def get_parse_result(document_id: str) -> dict[str, object]:
        try:
            result = repository.get_parse_result(document_id)
        except DocumentNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "DOCUMENT_NOT_FOUND", "message": document_id}) from exc
        except ParseResultNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "PARSE_RESULT_NOT_FOUND", "message": document_id}) from exc
        return result.to_dict()

    @app.post("/schemas")
    async def create_schema(schema: dict[str, object]) -> dict[str, object]:
        try:
            return repository.upsert_schema(schema)
        except SchemaValidationError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_SCHEMA", "message": str(exc)}) from exc

    @app.get("/schemas")
    def list_schemas() -> list[dict[str, object]]:
        return repository.list_schemas()

    @app.get("/schemas/{schema_id}")
    def get_schema(schema_id: str) -> dict[str, object]:
        try:
            return repository.get_schema(schema_id)
        except SchemaNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "SCHEMA_NOT_FOUND", "message": schema_id}) from exc

    @app.put("/schemas/{schema_id}")
    async def update_schema(schema_id: str, schema: dict[str, object]) -> dict[str, object]:
        updated = dict(schema)
        updated["schema_id"] = schema_id
        try:
            return repository.upsert_schema(updated)
        except SchemaValidationError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_SCHEMA", "message": str(exc)}) from exc

    @app.delete("/schemas/{schema_id}")
    def delete_schema(schema_id: str) -> dict[str, bool]:
        try:
            return {"deleted": repository.delete_schema(schema_id)}
        except SchemaNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "SCHEMA_NOT_FOUND", "message": schema_id}) from exc

    @app.post("/documents/{document_id}/extract")
    async def extract_document(document_id: str, request: dict[str, object]) -> dict[str, str]:
        schema_id = str(request.get("schema_id") or "")
        try:
            schema = repository.get_schema(schema_id)
            parse_result = repository.get_parse_result(document_id)
        except SchemaNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "SCHEMA_NOT_FOUND", "message": schema_id}) from exc
        except DocumentNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "DOCUMENT_NOT_FOUND", "message": document_id}) from exc
        except ParseResultNotFound as exc:
            raise HTTPException(status_code=404, detail={"code": "PARSE_RESULT_NOT_FOUND", "message": document_id}) from exc

        extraction_id = f"ext_{uuid4().hex}"
        result = extractor.extract(extraction_id, document_id, schema, parse_result)
        repository.store_extraction_result(result)
        return {
            "extraction_id": result.extraction_id,
            "document_id": result.document_id,
            "schema_id": result.schema_id,
            "status": result.status,
        }

    @app.get("/extractions/{extraction_id}")
    def get_extraction(extraction_id: str) -> dict[str, object]:
        try:
            return repository.get_extraction_result(extraction_id).to_dict()
        except ExtractionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "EXTRACTION_NOT_FOUND", "message": extraction_id},
            ) from exc

    return app


try:
    app = create_app()
except MissingDependencyError:
    app = None
