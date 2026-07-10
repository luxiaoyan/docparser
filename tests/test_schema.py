import unittest

from docparser.models import (
    ParsedContent,
    ParseDocumentInfo,
    ParseFileInfo,
    ParseSource,
    TextBlock,
    UnifiedParseResult,
)
from docparser.schema import SchemaExtractor


def make_parse_result(markdown: str, *, forms: list[dict[str, object]] | None = None) -> UnifiedParseResult:
    return UnifiedParseResult(
        document_id="doc_test",
        file=ParseFileInfo(name="contract.pdf", sha256="abc", size_bytes=123),
        document=ParseDocumentInfo(
            file_type="pdf",
            page_count=1,
            encrypted=False,
            parse_mode="txt",
            metadata={},
            warnings=[],
        ),
        content=ParsedContent(
            markdown=markdown,
            text_blocks=[
                TextBlock(
                    block_id="txt_0001",
                    type="paragraph",
                    text=markdown,
                    page_no=1,
                    source="mineru",
                    confidence=0.9,
                )
            ],
            tables=[],
            forms=forms or [],
            images=[],
            attachments=[],
            annotations=[],
        ),
        sources=[ParseSource(engine="mineru", version="3.4.0", status="success")],
    )


class SchemaExtractorTests(unittest.TestCase):
    def test_extracts_form_field_before_regex(self):
        schema = {
            "schema_id": "contract_v1",
            "name": "Contract",
            "fields": [
                {
                    "name": "contract_no",
                    "label": "合同编号",
                    "type": "string",
                    "required": True,
                    "strategies": [
                        {"type": "form_field", "field_names": ["contract_no", "合同编号"]},
                        {"type": "regex", "pattern": "合同编号[:：\\s]*([A-Za-z0-9\\-]+)"},
                    ],
                }
            ],
        }
        result = make_parse_result(
            "合同编号：HT-TEXT-001",
            forms=[
                {
                    "name": "contract_no",
                    "label": "合同编号",
                    "value": "HT-FORM-001",
                    "source": "pymupdf.widget",
                }
            ],
        )

        extraction = SchemaExtractor().extract("ext_test", "doc_test", schema, result)

        field = extraction.to_dict()["fields"]["contract_no"]
        self.assertEqual("HT-FORM-001", field["value"])
        self.assertEqual("HT-FORM-001", field["normalized_value"])
        self.assertEqual("form", field["source"])
        self.assertEqual("valid", field["status"])
        self.assertEqual(1.0, field["confidence"])

    def test_extracts_regex_and_normalizes_money(self):
        schema = {
            "schema_id": "invoice_v1",
            "name": "Invoice",
            "fields": [
                {
                    "name": "amount",
                    "label": "金额",
                    "type": "money",
                    "required": True,
                    "strategies": [{"type": "regex", "pattern": "金额[:：\\s]*¥?([0-9,]+\\.\\d{2})"}],
                }
            ],
        }

        extraction = SchemaExtractor().extract(
            "ext_test",
            "doc_test",
            schema,
            make_parse_result("金额：¥12,345.60"),
        )

        field = extraction.to_dict()["fields"]["amount"]
        self.assertEqual("12,345.60", field["value"])
        self.assertEqual("12345.60", field["normalized_value"])
        self.assertEqual("text", field["source"])
        self.assertEqual("valid", field["status"])

    def test_required_missing_field_is_reported(self):
        schema = {
            "schema_id": "contract_v1",
            "name": "Contract",
            "fields": [
                {
                    "name": "contract_no",
                    "label": "合同编号",
                    "type": "string",
                    "required": True,
                    "strategies": [{"type": "regex", "pattern": "合同编号[:：\\s]*([A-Za-z0-9\\-]+)"}],
                }
            ],
        }

        extraction = SchemaExtractor().extract("ext_test", "doc_test", schema, make_parse_result("无编号"))

        payload = extraction.to_dict()
        self.assertEqual("missing", payload["fields"]["contract_no"]["status"])
        self.assertIn("Missing required field: contract_no", payload["warnings"])

    def test_extracts_table_column(self):
        schema = {
            "schema_id": "invoice_table_v1",
            "name": "Invoice Table",
            "fields": [
                {
                    "name": "amount",
                    "label": "金额",
                    "type": "money",
                    "required": True,
                    "strategies": [{"type": "table_column", "headers": ["金额"]}],
                }
            ],
        }
        result = make_parse_result("table")
        result.content.tables.append(
            {
                "headers": ["品名", "金额"],
                "rows": [["服务费", "1,200.00"]],
                "source": "mineru",
            }
        )

        extraction = SchemaExtractor().extract("ext_test", "doc_test", schema, result)

        field = extraction.to_dict()["fields"]["amount"]
        self.assertEqual("1,200.00", field["value"])
        self.assertEqual("1200.00", field["normalized_value"])
        self.assertEqual("table", field["source"])


if __name__ == "__main__":
    unittest.main()
