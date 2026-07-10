import importlib.util
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path

import fitz

from docparser.app import MissingDependencyError, create_app
from docparser.config import ParserSettings
from docparser.pdf_preflight import PdfPreflightService
from docparser.storage import LocalDocumentStorage
from docparser.tasks import InMemoryTaskRepository


def write_text_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page(width=240, height=120)
    page.insert_text((24, 48), text)
    document.save(path)
    document.close()


class AppFactoryTests(unittest.TestCase):
    def test_root_serves_upload_console(self):
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("FastAPI is not installed.")

        from fastapi.testclient import TestClient

        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("PDF Document Parser", response.text)
        self.assertIn('id="pdf-file"', response.text)
        self.assertIn("/documents", response.text)
        self.assertIn("parse-result", response.text)
        self.assertIn('id="schema-json"', response.text)
        self.assertIn("/schemas", response.text)
        self.assertIn("/extract", response.text)
        self.assertIn('data-view="merged"', response.text)
        self.assertIn('data-view="pymupdf"', response.text)
        self.assertIn('data-view="mineru"', response.text)
        self.assertIn('data-view="response"', response.text)
        self.assertIn("合并结果", response.text)
        self.assertIn("PyMuPDF 原始", response.text)
        self.assertIn("MinerU 原始", response.text)
        self.assertIn("当前响应", response.text)

    def test_health_reports_mineru_configuration(self):
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("FastAPI is not installed.")

        from fastapi.testclient import TestClient

        with patch.dict(
            "os.environ",
            {
                "DOCPARSER_MINERU_SERVICE_URL": "http://mineru-service:8000/file_parse",
                "DOCPARSER_MINERU_COMMAND": "",
            },
        ):
            client = TestClient(create_app())

        response = client.get("/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "status": "ok",
                "parser_backend": "mineru_service",
                "mineru_configured": True,
                "mineru_service_url": "http://mineru-service:8000/file_parse",
            },
            response.json(),
        )

    def test_upload_parses_pdf_and_exposes_parse_result(self):
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("FastAPI is not installed.")

        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "contract.pdf"
            write_text_pdf(pdf_path, "Contract No: HT-2026-001")
            settings = ParserSettings(storage_root=Path(temp_dir) / "documents")
            repository = InMemoryTaskRepository()
            client = TestClient(
                create_app(
                    repository=repository,
                    storage=LocalDocumentStorage(settings.storage_root),
                    preflight=PdfPreflightService(settings),
                )
            )

            with self.assertLogs("docparser.engine_raw", level="INFO") as logs:
                with pdf_path.open("rb") as file:
                    upload_response = client.post(
                        "/documents",
                        files={"file": ("contract.pdf", file, "application/pdf")},
                    )

            self.assertEqual(200, upload_response.status_code)
            upload_payload = upload_response.json()
            self.assertEqual("succeeded", upload_payload["status"])
            log_text = "\n".join(logs.output)
            self.assertIn('"engine": "mineru"', log_text)
            self.assertIn('"engine": "pymupdf"', log_text)
            self.assertNotIn('"engine": "pypdf"', log_text)

            result_response = client.get(f"/documents/{upload_payload['document_id']}/parse-result")

            self.assertEqual(200, result_response.status_code)
            result_payload = result_response.json()
            self.assertIn("Contract No: HT-2026-001", result_payload["content"]["markdown"])
            self.assertEqual("mineru", result_payload["sources"][0]["engine"])
            self.assertEqual("fallback", result_payload["sources"][0]["status"])
            self.assertIn("mineru", result_payload["engine_results"])
            self.assertIn("pymupdf", result_payload["engine_results"])
            self.assertNotIn("pypdf", result_payload["engine_results"])

    def test_schema_crud_and_extraction_api(self):
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("FastAPI is not installed.")

        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "contract.pdf"
            write_text_pdf(pdf_path, "Contract No: HT-2026-001")
            settings = ParserSettings(storage_root=Path(temp_dir) / "documents")
            client = TestClient(
                create_app(
                    repository=InMemoryTaskRepository(),
                    storage=LocalDocumentStorage(settings.storage_root),
                    preflight=PdfPreflightService(settings),
                )
            )
            schema = {
                "schema_id": "contract_v1",
                "name": "合同字段抽取",
                "fields": [
                    {
                        "name": "contract_no",
                        "label": "合同编号",
                        "type": "string",
                        "required": True,
                        "strategies": [
                            {"type": "regex", "pattern": "Contract No[:：\\s]*([A-Za-z0-9\\-]+)"}
                        ],
                    }
                ],
            }

            create_schema_response = client.post("/schemas", json=schema)
            self.assertEqual(200, create_schema_response.status_code)
            self.assertEqual(schema["schema_id"], create_schema_response.json()["schema_id"])
            self.assertEqual([schema], client.get("/schemas").json())
            self.assertEqual(schema, client.get("/schemas/contract_v1").json())

            with pdf_path.open("rb") as file:
                upload_response = client.post(
                    "/documents",
                    files={"file": ("contract.pdf", file, "application/pdf")},
                )
            document_id = upload_response.json()["document_id"]

            extraction_response = client.post(
                f"/documents/{document_id}/extract",
                json={"schema_id": "contract_v1"},
            )

            self.assertEqual(200, extraction_response.status_code)
            extraction_payload = extraction_response.json()
            self.assertEqual("succeeded", extraction_payload["status"])

            result_response = client.get(f"/extractions/{extraction_payload['extraction_id']}")

            self.assertEqual(200, result_response.status_code)
            result_payload = result_response.json()
            self.assertEqual("HT-2026-001", result_payload["fields"]["contract_no"]["normalized_value"])
            self.assertEqual("valid", result_payload["fields"]["contract_no"]["status"])

            update_response = client.put("/schemas/contract_v1", json={**schema, "name": "合同字段抽取 v2"})
            self.assertEqual("合同字段抽取 v2", update_response.json()["name"])
            delete_response = client.delete("/schemas/contract_v1")
            self.assertEqual({"deleted": True}, delete_response.json())

    def test_create_app_reports_missing_fastapi_when_dependency_is_absent(self):
        if importlib.util.find_spec("fastapi") is not None:
            self.skipTest("FastAPI is installed; dependency-missing branch is not active.")

        with self.assertRaises(MissingDependencyError):
            create_app()


if __name__ == "__main__":
    unittest.main()
