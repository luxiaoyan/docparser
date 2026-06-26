import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from docparser.config import ParserSettings
from docparser.pdf_preflight import PdfPreflightService, PdfValidationError


def write_one_page_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as file:
        writer.write(file)


class PdfPreflightTests(unittest.TestCase):
    def test_rejects_invalid_pdf_magic_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.pdf"
            path.write_bytes(b"not a pdf")
            service = PdfPreflightService(ParserSettings())

            with self.assertRaises(PdfValidationError) as error:
                service.inspect(path)

            self.assertEqual("INVALID_FILE_TYPE", error.exception.code)

    def test_reads_one_page_pdf_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "one.pdf"
            write_one_page_pdf(path)
            service = PdfPreflightService(ParserSettings())

            result = service.inspect(path)

            self.assertEqual(1, result.page_count)
            self.assertFalse(result.encrypted)
            self.assertEqual("pdf", result.file_type)

    def test_enforces_page_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "one.pdf"
            write_one_page_pdf(path)
            service = PdfPreflightService(ParserSettings(max_pages=0))

            with self.assertRaises(PdfValidationError) as error:
                service.inspect(path)

            self.assertEqual("PAGE_LIMIT_EXCEEDED", error.exception.code)


if __name__ == "__main__":
    unittest.main()
