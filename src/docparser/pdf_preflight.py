from pathlib import Path
from typing import Any

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
            import fitz  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise PdfValidationError("PYMUPDF_MISSING", "PyMuPDF is required for PDF preflight") from exc

        try:
            document = fitz.open(path)
        except Exception as exc:
            raise PdfValidationError("PDF_CORRUPTED", "PDF is corrupted or unreadable") from exc

        with document:
            if document.needs_pass:
                raise PdfValidationError("PDF_ENCRYPTED", "Encrypted PDFs are not supported in phase 1")

            page_count = document.page_count
            if page_count > self.settings.max_pages:
                raise PdfValidationError("PAGE_LIMIT_EXCEEDED", "PDF exceeds configured page limit")

            pages = self._extract_page_info(document)
            return PreflightResult(
                file_type="pdf",
                page_count=page_count,
                encrypted=False,
                metadata=dict(document.metadata or {}),
                forms=self._extract_forms(document),
                attachments=self._extract_attachments(document),
                pages=pages,
                warnings=[],
            )

    def _check_magic_bytes(self, path: Path) -> None:
        with path.open("rb") as file:
            magic = file.read(5)
        if magic != b"%PDF-":
            raise PdfValidationError("INVALID_FILE_TYPE", "File does not start with PDF magic bytes")

    def _extract_forms(self, document: Any) -> list[dict[str, Any]]:
        forms: list[dict[str, Any]] = []
        for page_index in range(document.page_count):
            widgets = document[page_index].widgets() or []
            for widget in widgets:
                field_name = getattr(widget, "field_name", None)
                if not field_name:
                    continue
                value = getattr(widget, "field_value", None)
                label = getattr(widget, "field_label", None)
                field_type = getattr(widget, "field_type_string", None)
                forms.append(
                    {
                        "name": str(field_name),
                        "label": str(label) if label else None,
                        "value": str(value) if value is not None else None,
                        "field_type": str(field_type) if field_type is not None else None,
                        "page_no": page_index + 1,
                        "source": "pymupdf.widget",
                    }
                )
        return forms

    def _extract_attachments(self, document: Any) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []
        if not hasattr(document, "embfile_count"):
            return attachments

        for index in range(document.embfile_count()):
            info = document.embfile_info(index) or {}
            name = info.get("filename") or info.get("name") or f"attachment_{index + 1}"
            size = info.get("size")
            if size is None:
                try:
                    size = len(document.embfile_get(index))
                except Exception:
                    size = 0
            attachments.append({"name": str(name), "size_bytes": int(size), "source": "pymupdf"})
        return attachments

    def _extract_page_info(self, document: Any) -> list[PageInfo]:
        pages: list[PageInfo] = []
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
        return pages
