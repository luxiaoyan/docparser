from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class StoredFile:
    document_id: str
    filename: str
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str = "application/pdf"


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    filename: str
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str = "application/pdf"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ParseTask:
    task_id: str
    document_id: str
    status: TaskStatus
    progress: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PageInfo:
    page_no: int
    width: float | None = None
    height: float | None = None
    rotation: int | None = None


@dataclass(frozen=True)
class PreflightResult:
    file_type: str
    page_count: int
    encrypted: bool
    metadata: dict[str, Any]
    forms: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    pages: list[PageInfo]
    warnings: list[str]


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str


@dataclass(frozen=True)
class ParseFileInfo:
    name: str
    sha256: str
    size_bytes: int
    mime_type: str = "application/pdf"


@dataclass(frozen=True)
class ParseDocumentInfo:
    file_type: str
    page_count: int
    encrypted: bool
    parse_mode: str
    metadata: dict[str, Any]
    warnings: list[str]


@dataclass(frozen=True)
class TextBlock:
    block_id: str
    type: str
    text: str
    page_no: int
    source: str
    confidence: float


@dataclass(frozen=True)
class ParseSource:
    engine: str
    version: str
    status: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedContent:
    markdown: str
    text_blocks: list[TextBlock]
    tables: list[dict[str, Any]]
    forms: list[dict[str, Any]]
    images: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    annotations: list[dict[str, Any]]


@dataclass(frozen=True)
class UnifiedParseResult:
    document_id: str
    file: ParseFileInfo
    document: ParseDocumentInfo
    content: ParsedContent
    sources: list[ParseSource]
    engine_results: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExtractedField:
    value: Any
    normalized_value: Any
    confidence: float
    source: str
    status: str
    strategy: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    extraction_id: str
    document_id: str
    schema_id: str
    status: str
    fields: dict[str, ExtractedField]
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
