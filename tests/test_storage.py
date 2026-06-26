import tempfile
import unittest
from pathlib import Path

from docparser.storage import InvalidFileTypeError, LocalDocumentStorage


class LocalDocumentStorageTests(unittest.TestCase):
    def test_save_pdf_writes_original_and_returns_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = LocalDocumentStorage(Path(temp_dir))

            stored = storage.save_pdf("sample.pdf", b"%PDF-1.4\nbody")

            self.assertEqual("sample.pdf", stored.filename)
            self.assertEqual("application/pdf", stored.mime_type)
            self.assertEqual(len(b"%PDF-1.4\nbody"), stored.size_bytes)
            self.assertTrue((Path(temp_dir) / stored.storage_key).exists())
            self.assertEqual(64, len(stored.sha256))

    def test_save_pdf_rejects_non_pdf_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = LocalDocumentStorage(Path(temp_dir))

            with self.assertRaises(InvalidFileTypeError):
                storage.save_pdf("sample.txt", b"not a pdf")


if __name__ == "__main__":
    unittest.main()
