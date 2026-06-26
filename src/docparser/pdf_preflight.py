from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from docparser.config import ParserSettings
from docparser.models import PageInfo, PreflightResult


class PdfValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PdfPreflightService:
    def __init__(self, settings: ParserSettings) -> None:
        self.settings = settings

    def inspect(self, path: Path) -> PreflightResult:
        self._check_magic_bytes(path)

        try:
            reader = PdfReader(str(path))
        except PdfReadError as exc:
            raise PdfValidationError("PDF_CORRUPTED", "PDF is corrupted or unreadable") from exc

        if reader.is_encrypted:
            raise PdfValidationError("PDF_ENCRYPTED", "Encrypted PDFs are not supported in phase 1")

        page_count = len(reader.pages)
        if page_count > self.settings.max_pages:
            raise PdfValidationError("PAGE_LIMIT_EXCEEDED", "PDF exceeds configured page limit")

        forms = self._extract_forms(reader)
        attachments = self._extract_attachments(reader)
        pages, warnings = self._extract_page_info(path, reader)

        return PreflightResult(
            file_type="pdf",
            page_count=page_count,
            encrypted=False,
            metadata=dict(reader.metadata or {}),
            forms=forms,
            attachments=attachments,
            pages=pages,
            warnings=warnings,
        )

    def _check_magic_bytes(self, path: Path) -> None:
        with path.open("rb") as file:
            magic = file.read(5)
        if magic != b"%PDF-":
            raise PdfValidationError("INVALID_FILE_TYPE", "File does not start with PDF magic bytes")

    def _extract_forms(self, reader: PdfReader) -> list[dict[str, Any]]:
        try:
            fields = reader.get_fields() or {}
        except (AttributeError, KeyError, PdfReadError):
            return []

        forms: list[dict[str, Any]] = []
        for name, field in fields.items():
            value = field.get("/V") if hasattr(field, "get") else None
            field_type = field.get("/FT") if hasattr(field, "get") else None
            forms.append(
                {
                    "name": str(name),
                    "value": str(value) if value is not None else None,
                    "field_type": str(field_type) if field_type is not None else None,
                    "source": "pypdf.acroform",
                }
            )
        return forms

    def _extract_attachments(self, reader: PdfReader) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []
        try:
            names = reader.attachments
        except (AttributeError, KeyError, PdfReadError):
            return attachments

        for name, payloads in names.items():
            size = sum(len(payload) for payload in payloads)
            attachments.append({"name": name, "size_bytes": size, "source": "pypdf"})
        return attachments

    def _extract_page_info(self, path: Path, reader: PdfReader) -> tuple[list[PageInfo], list[str]]:
        warnings: list[str] = []
        pages: list[PageInfo] = []

        try:
            import fitz  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            warnings.append("PyMuPDF is not installed; page diagnostics are based on pypdf only.")
            for index, page in enumerate(reader.pages, start=1):
                media_box = page.mediabox
                pages.append(
                    PageInfo(
                        page_no=index,
                        width=float(media_box.width),
                        height=float(media_box.height),
                        rotation=int(page.get("/Rotate", 0)),
                    )
                )
            return pages, warnings

        with fitz.open(path) as document:
            for index, page in enumerate(document, start=1):
                rect = page.rect
                pages.append(
                    PageInfo(
                        page_no=index,
                        width=float(rect.width),
                        height=float(rect.height),
                        rotation=int(page.rotation),
                    )
                )
        return pages, warnings
