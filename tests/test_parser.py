import tempfile
import unittest
from pathlib import Path

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
            self.assertIn("pypdf", payload["engine_results"])
            self.assertIn("pymupdf", payload["engine_results"])
            self.assertEqual("fallback", payload["engine_results"]["mineru"]["status"])
            self.assertEqual(1, payload["engine_results"]["pypdf"]["page_count"])
            self.assertEqual(1, len(payload["engine_results"]["pymupdf"]["pages"]))


if __name__ == "__main__":
    unittest.main()
