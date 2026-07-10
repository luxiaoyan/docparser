import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from docparser.config import ParserSettings
from docparser.models import DocumentRecord
from docparser.parser import MinerUParser
from docparser.pdf_preflight import PdfPreflightService


def write_text_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page(width=240, height=120)
    page.insert_text((24, 48), text)
    document.save(path)
    document.close()


class MinerUParserTests(unittest.TestCase):
    def test_parser_returns_unified_result_with_native_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.pdf"
            write_text_pdf(path, "Contract No: HT-2026-001")
            document = DocumentRecord(
                document_id="doc_test",
                filename="sample.pdf",
                storage_key="doc_test/original.pdf",
                sha256="a" * 64,
                size_bytes=path.stat().st_size,
            )
            preflight = PdfPreflightService(ParserSettings()).inspect(path)

            result = MinerUParser().parse(document, path, preflight)

            payload = result.to_dict()
            self.assertEqual("doc_test", payload["document_id"])
            self.assertIn("Contract No: HT-2026-001", payload["content"]["markdown"])
            self.assertGreaterEqual(len(payload["content"]["text_blocks"]), 1)
            self.assertEqual("mineru", payload["sources"][0]["engine"])
            self.assertEqual("fallback", payload["sources"][0]["status"])
            self.assertIn("MinerU command is not configured", payload["document"]["warnings"][0])
            self.assertIn("mineru", payload["engine_results"])
            self.assertIn("pymupdf", payload["engine_results"])
            self.assertEqual("fallback", payload["engine_results"]["mineru"]["status"])
            self.assertNotIn("pypdf", payload["engine_results"])
            self.assertEqual(1, len(payload["engine_results"]["pymupdf"]["pages"]))

    def test_parser_calls_mineru_http_service(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.pdf"
            write_text_pdf(path, "Contract No: HT-2026-001")
            document = DocumentRecord(
                document_id="doc_test",
                filename="sample.pdf",
                storage_key="doc_test/original.pdf",
                sha256="a" * 64,
                size_bytes=path.stat().st_size,
            )
            preflight = PdfPreflightService(ParserSettings()).inspect(path)
            service_payload = b"""
            {
              "version": "service-test",
              "status": "success",
              "parse_mode": "txt",
              "markdown": "Contract No: HT-2026-001",
              "text_blocks": [
                {
                  "block_id": "txt_0001",
                  "type": "paragraph",
                  "text": "Contract No: HT-2026-001",
                  "page_no": 1,
                  "source": "mineru-service",
                  "confidence": 0.95
                }
              ],
              "tables": [],
              "images": [],
              "warnings": []
            }
            """

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return None

                def read(self):
                    return service_payload

            with patch("urllib.request.urlopen", return_value=Response()) as urlopen:
                result = MinerUParser(service_url="http://mineru-service:8001/parse").parse(
                    document,
                    path,
                    preflight,
                )

            request = urlopen.call_args.args[0]
            self.assertEqual("http://mineru-service:8001/parse", request.full_url)
            self.assertEqual("POST", request.get_method())
            self.assertIn("multipart/form-data", request.headers["Content-type"])
            self.assertIn(b"Contract No: HT-2026-001", result.content.markdown.encode())
            self.assertEqual("success", result.sources[0].status)
            self.assertEqual("service-test", result.sources[0].version)

    def test_parser_calls_mineru_api_file_parse_service(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.pdf"
            write_text_pdf(path, "Contract No: HT-2026-001")
            document = DocumentRecord(
                document_id="doc_test",
                filename="sample.pdf",
                storage_key="doc_test/original.pdf",
                sha256="a" * 64,
                size_bytes=path.stat().st_size,
            )
            preflight = PdfPreflightService(ParserSettings()).inspect(path)
            service_payload = b"""
            {
              "task_id": "task_test",
              "status": "completed",
              "backend": "pipeline",
              "version": "2.5.0",
              "results": {
                "sample": {
                  "md_content": "Contract No: HT-2026-001",
                  "content_list": "[{\\"type\\": \\"text\\", \\"text\\": \\"Contract No: HT-2026-001\\", \\"page_idx\\": 0}]"
                }
              }
            }
            """

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return None

                def read(self):
                    return service_payload

            with patch("urllib.request.urlopen", return_value=Response()) as urlopen:
                result = MinerUParser(service_url="http://mineru-service:8000/file_parse").parse(
                    document,
                    path,
                    preflight,
                )

            request = urlopen.call_args.args[0]
            self.assertEqual("http://mineru-service:8000/file_parse", request.full_url)
            self.assertIn(b'name="files"; filename="sample.pdf"', request.data)
            self.assertIn(b'name="return_content_list"', request.data)
            self.assertIn("Contract No: HT-2026-001", result.content.markdown)
            self.assertEqual("2.5.0", result.sources[0].version)
            self.assertEqual("mineru-api", result.content.text_blocks[0].source)


if __name__ == "__main__":
    unittest.main()
