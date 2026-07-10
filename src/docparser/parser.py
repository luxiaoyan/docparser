from dataclasses import asdict
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any
import uuid
import urllib.error
import urllib.parse
import urllib.request

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
    def __init__(self, command: str | None = None, service_url: str | None = None) -> None:
        self.command = command
        self.service_url = service_url

    def parse(self, document: DocumentRecord, path: Path, preflight: PreflightResult) -> UnifiedParseResult:
        if self.service_url:
            try:
                return self._parse_with_service(document, path, preflight)
            except ParsePipelineError:
                raise
            except Exception as exc:
                raise ParsePipelineError(f"MinerU service parser failed: {exc}") from exc

        if self.command:
            try:
                return self._parse_with_command(document, path, preflight)
            except ParsePipelineError:
                raise
            except Exception as exc:
                raise ParsePipelineError(f"MinerU parser failed: {exc}") from exc

        warning = "MinerU command is not configured; used PyMuPDF native text fallback."
        return self._parse_with_pymupdf_fallback(document, path, preflight, [warning])

    def _parse_with_service(
        self,
        document: DocumentRecord,
        path: Path,
        preflight: PreflightResult,
    ) -> UnifiedParseResult:
        service_url = self.service_url or ""
        request = self._build_service_request(service_url, path)
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace") or str(exc)
            raise ParsePipelineError(f"MinerU service returned HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ParsePipelineError(f"MinerU service request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ParsePipelineError("MinerU service did not return JSON") from exc

        payload = self._normalize_service_payload(payload, path)
        return self._result_from_payload(document, preflight, payload)

    def _build_service_request(self, service_url: str, path: Path) -> urllib.request.Request:
        parsed_url = urllib.parse.urlparse(service_url)
        if parsed_url.path.rstrip("/") == "/file_parse":
            return self._build_multipart_request(
                service_url,
                path,
                file_field_name="files",
                fields={
                    "backend": "pipeline",
                    "parse_method": "txt",
                    "return_md": "true",
                    "return_content_list": "true",
                    "return_images": "false",
                    "response_format_zip": "false",
                },
            )

        return self._build_multipart_request(service_url, path, file_field_name="file", fields={})

    def _build_multipart_request(
        self,
        service_url: str,
        path: Path,
        *,
        file_field_name: str,
        fields: dict[str, str],
    ) -> urllib.request.Request:
        boundary = f"----docparser-{uuid.uuid4().hex}"
        file_bytes = path.read_bytes()
        body_parts: list[bytes] = []
        for name, value in fields.items():
            body_parts.extend(
                [
                    f"--{boundary}\r\n".encode("utf-8"),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                    str(value).encode("utf-8"),
                    b"\r\n",
                ]
            )
        body_parts.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{file_field_name}"; '
                    f'filename="{path.name}"\r\n'
                ).encode("utf-8"),
                b"Content-Type: application/pdf\r\n\r\n",
                file_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        return urllib.request.Request(
            service_url,
            data=b"".join(body_parts),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            },
            method="POST",
        )

    def _normalize_service_payload(self, payload: dict[str, Any], path: Path) -> dict[str, Any]:
        if "results" not in payload:
            return payload

        results = payload.get("results")
        if not isinstance(results, dict) or not results:
            raise ParsePipelineError("MinerU API response did not contain parse results")

        result = self._select_mineru_api_result(results, path)
        markdown = str(result.get("md_content") or "")
        content_items = self._parse_mineru_api_content_list(result.get("content_list"))
        text_blocks, tables, images = self._content_items_to_payload_parts(content_items)
        if markdown and not text_blocks:
            text_blocks.append(
                {
                    "block_id": "txt_0001",
                    "type": "paragraph",
                    "text": markdown.strip(),
                    "page_no": 1,
                    "source": "mineru-api",
                    "confidence": 0.8,
                }
            )

        return {
            "version": str(payload.get("version", "unknown")),
            "status": "success",
            "parse_mode": str(payload.get("backend", "pipeline")),
            "markdown": markdown,
            "text_blocks": text_blocks,
            "tables": tables,
            "images": images,
            "warnings": [],
            "raw": payload,
        }

    def _select_mineru_api_result(self, results: dict[str, Any], path: Path) -> dict[str, Any]:
        for key in (path.stem, path.name):
            item = results.get(key)
            if isinstance(item, dict):
                return item

        first = next(iter(results.values()))
        if not isinstance(first, dict):
            raise ParsePipelineError("MinerU API result entry was not an object")
        return first

    def _parse_mineru_api_content_list(self, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return []
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _content_items_to_payload_parts(
        self,
        content_items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        text_blocks: list[dict[str, Any]] = []
        tables: list[dict[str, Any]] = []
        images: list[dict[str, Any]] = []

        for index, item in enumerate(content_items, start=1):
            item_type = str(item.get("type", "unknown"))
            page_no = int(item.get("page_idx", 0)) + 1
            if item_type == "text" and item.get("text"):
                text_blocks.append(
                    {
                        "block_id": f"txt_{index:04d}",
                        "type": "paragraph",
                        "text": str(item["text"]),
                        "page_no": page_no,
                        "source": "mineru-api",
                        "confidence": 0.9,
                    }
                )
            elif item_type == "table":
                tables.append(
                    {
                        "table_id": f"tbl_{index:04d}",
                        "name": f"table_{index}",
                        "page_no": page_no,
                        "html": item.get("table_body") or item.get("html") or "",
                        "markdown": item.get("text") or "",
                        "source": "mineru-api",
                        "confidence": 0.85,
                    }
                )
            elif item_type == "image":
                images.append(
                    {
                        "image_id": f"img_{index:04d}",
                        "page_no": page_no,
                        "storage_key": item.get("img_path") or item.get("image_path") or "",
                        "source": "mineru-api",
                    }
                )

        return text_blocks, tables, images

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
            "pymupdf": {
                "engine": "pymupdf",
                "page_count": preflight.page_count,
                "encrypted": preflight.encrypted,
                "metadata": preflight.metadata,
                "forms": preflight.forms,
                "attachments": preflight.attachments,
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
