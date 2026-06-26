from dataclasses import asdict
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from docparser.models import (
    DocumentRecord,
    ParsedContent,
    ParseDocumentInfo,
    ParseFileInfo,
    ParseSource,
    PreflightResult,
    TextBlock,
    UnifiedParseResult,
)


class ParsePipelineError(RuntimeError):
    pass


class MinerUParser:
    def __init__(self, command: str | None = None) -> None:
        self.command = command

    def parse(self, document: DocumentRecord, path: Path, preflight: PreflightResult) -> UnifiedParseResult:
        if self.command:
            try:
                return self._parse_with_command(document, path, preflight)
            except ParsePipelineError:
                raise
            except Exception as exc:
                raise ParsePipelineError(f"MinerU parser failed: {exc}") from exc

        warning = "MinerU command is not configured; used PyMuPDF native text fallback."
        return self._parse_with_pymupdf_fallback(document, path, preflight, [warning])

    def _parse_with_command(
        self,
        document: DocumentRecord,
        path: Path,
        preflight: PreflightResult,
    ) -> UnifiedParseResult:
        command = self.command or ""
        command_text = command.format(input=str(path))
        completed = subprocess.run(
            shlex.split(command_text),
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or "MinerU command exited with a non-zero status"
            raise ParsePipelineError(message)

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ParsePipelineError("MinerU command did not return JSON on stdout") from exc

        return self._result_from_payload(document, preflight, payload)

    def _engine_results_from_preflight(self, preflight: PreflightResult) -> dict[str, Any]:
        return {
            "pypdf": {
                "engine": "pypdf",
                "page_count": preflight.page_count,
                "encrypted": preflight.encrypted,
                "metadata": preflight.metadata,
                "forms": preflight.forms,
                "attachments": preflight.attachments,
            },
            "pymupdf": {
                "engine": "pymupdf",
                "pages": [asdict(page) for page in preflight.pages],
                "warnings": preflight.warnings,
            },
        }

    def _result_from_payload(
        self,
        document: DocumentRecord,
        preflight: PreflightResult,
        payload: dict[str, Any],
    ) -> UnifiedParseResult:
        text_blocks = [
            TextBlock(
                block_id=str(item.get("block_id", f"txt_{index:04d}")),
                type=str(item.get("type", "paragraph")),
                text=str(item.get("text", "")),
                page_no=int(item.get("page_no", 1)),
                source=str(item.get("source", "mineru")),
                confidence=float(item.get("confidence", 0.9)),
            )
            for index, item in enumerate(payload.get("text_blocks", []), start=1)
            if item.get("text")
        ]
        warnings = [str(item) for item in payload.get("warnings", [])]
        engine_results = self._engine_results_from_preflight(preflight)
        engine_results["mineru"] = {
            "engine": "mineru",
            "version": str(payload.get("version", "unknown")),
            "status": str(payload.get("status", "success")),
            "parse_mode": str(payload.get("parse_mode", "native")),
            "raw": payload.get("raw", payload),
        }
        return UnifiedParseResult(
            document_id=document.document_id,
            file=ParseFileInfo(
                name=document.filename,
                sha256=document.sha256,
                size_bytes=document.size_bytes,
                mime_type=document.mime_type,
            ),
            document=ParseDocumentInfo(
                file_type=preflight.file_type,
                page_count=preflight.page_count,
                encrypted=preflight.encrypted,
                parse_mode=str(payload.get("parse_mode", "native")),
                metadata=preflight.metadata,
                warnings=preflight.warnings + warnings,
            ),
            content=ParsedContent(
                markdown=str(payload.get("markdown", "")),
                text_blocks=text_blocks,
                tables=list(payload.get("tables", [])),
                forms=preflight.forms,
                images=list(payload.get("images", [])),
                attachments=preflight.attachments,
                annotations=list(payload.get("annotations", [])),
            ),
            sources=[
                ParseSource(
                    engine="mineru",
                    version=str(payload.get("version", "unknown")),
                    status=str(payload.get("status", "success")),
                    warnings=warnings,
                )
            ],
            engine_results=engine_results,
        )

    def _parse_with_pymupdf_fallback(
        self,
        document: DocumentRecord,
        path: Path,
        preflight: PreflightResult,
        warnings: list[str],
    ) -> UnifiedParseResult:
        try:
            import fitz  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise ParsePipelineError("PyMuPDF is required for native fallback parsing") from exc

        text_blocks: list[TextBlock] = []
        markdown_parts: list[str] = []
        with fitz.open(path) as pdf:
            for page_index, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if not text:
                    continue
                block = TextBlock(
                    block_id=f"txt_{page_index:04d}",
                    type="paragraph",
                    text=text,
                    page_no=page_index,
                    source="pymupdf.text",
                    confidence=0.75,
                )
                text_blocks.append(block)
                markdown_parts.append(text)

        engine_results = self._engine_results_from_preflight(preflight)
        engine_results["mineru"] = {
            "engine": "mineru",
            "version": "not-configured",
            "status": "fallback",
            "raw": {
                "markdown": "\n\n".join(markdown_parts),
                "text_blocks": [asdict(block) for block in text_blocks],
                "warnings": warnings,
            },
        }
        return UnifiedParseResult(
            document_id=document.document_id,
            file=ParseFileInfo(
                name=document.filename,
                sha256=document.sha256,
                size_bytes=document.size_bytes,
                mime_type=document.mime_type,
            ),
            document=ParseDocumentInfo(
                file_type=preflight.file_type,
                page_count=preflight.page_count,
                encrypted=preflight.encrypted,
                parse_mode="native",
                metadata=preflight.metadata,
                warnings=preflight.warnings + warnings,
            ),
            content=ParsedContent(
                markdown="\n\n".join(markdown_parts),
                text_blocks=text_blocks,
                tables=[],
                forms=preflight.forms,
                images=[],
                attachments=preflight.attachments,
                annotations=[],
            ),
            sources=[
                ParseSource(
                    engine="mineru",
                    version="not-configured",
                    status="fallback",
                    warnings=warnings,
                )
            ],
            engine_results=engine_results,
        )
