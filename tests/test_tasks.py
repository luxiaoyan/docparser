import unittest

from docparser.models import (
    ExtractedField,
    ExtractionResult,
    ParsedContent,
    ParseDocumentInfo,
    ParseFileInfo,
    ParseSource,
    TaskStatus,
    UnifiedParseResult,
)
from docparser.tasks import InvalidTaskTransition, InMemoryTaskRepository


class TaskRepositoryTests(unittest.TestCase):
    def test_created_parse_task_starts_queued(self):
        repo = InMemoryTaskRepository()
        document = repo.create_document(
            filename="sample.pdf",
            storage_key="documents/doc_001/original.pdf",
            sha256="abc",
            size_bytes=128,
        )

        task = repo.create_parse_task(document.document_id)

        self.assertEqual(TaskStatus.QUEUED, task.status)
        self.assertEqual(document.document_id, task.document_id)

    def test_task_can_move_from_queued_to_running(self):
        repo = InMemoryTaskRepository()
        document = repo.create_document("sample.pdf", "key", "abc", 128)
        task = repo.create_parse_task(document.document_id)

        updated = repo.update_task_status(task.task_id, TaskStatus.RUNNING)

        self.assertEqual(TaskStatus.RUNNING, updated.status)

    def test_task_rejects_transition_from_succeeded_to_running(self):
        repo = InMemoryTaskRepository()
        document = repo.create_document("sample.pdf", "key", "abc", 128)
        task = repo.create_parse_task(document.document_id)
        repo.update_task_status(task.task_id, TaskStatus.RUNNING)
        repo.update_task_status(task.task_id, TaskStatus.SUCCEEDED)

        with self.assertRaises(InvalidTaskTransition):
            repo.update_task_status(task.task_id, TaskStatus.RUNNING)

    def test_store_and_get_parse_result(self):
        repo = InMemoryTaskRepository()
        document = repo.create_document("sample.pdf", "key", "abc", 128)
        result = UnifiedParseResult(
            document_id=document.document_id,
            file=ParseFileInfo(name="sample.pdf", sha256="abc", size_bytes=128),
            document=ParseDocumentInfo(
                file_type="pdf",
                page_count=1,
                encrypted=False,
                parse_mode="native",
                metadata={},
                warnings=[],
            ),
            content=ParsedContent(
                markdown="hello",
                text_blocks=[],
                tables=[],
                forms=[],
                images=[],
                attachments=[],
                annotations=[],
            ),
            sources=[ParseSource(engine="mineru", version="test", status="success")],
        )

        repo.store_parse_result(document.document_id, result)

        self.assertEqual(result, repo.get_parse_result(document.document_id))

    def test_schema_crud(self):
        repo = InMemoryTaskRepository()
        schema = {"schema_id": "contract_v1", "name": "Contract", "fields": []}

        repo.upsert_schema(schema)

        self.assertEqual(schema, repo.get_schema("contract_v1"))
        self.assertEqual([schema], repo.list_schemas())

        updated = {"schema_id": "contract_v1", "name": "Contract v2", "fields": []}
        repo.upsert_schema(updated)

        self.assertEqual(updated, repo.get_schema("contract_v1"))
        self.assertTrue(repo.delete_schema("contract_v1"))
        self.assertEqual([], repo.list_schemas())

    def test_store_and_get_extraction_result(self):
        repo = InMemoryTaskRepository()
        result = ExtractionResult(
            extraction_id="ext_test",
            document_id="doc_test",
            schema_id="contract_v1",
            status="succeeded",
            fields={
                "contract_no": ExtractedField(
                    value="HT-001",
                    normalized_value="HT-001",
                    confidence=0.9,
                    source="text",
                    status="valid",
                )
            },
        )

        repo.store_extraction_result(result)

        self.assertEqual(result, repo.get_extraction_result("ext_test"))


if __name__ == "__main__":
    unittest.main()
