from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from docparser.models import StoredFile


class InvalidFileTypeError(ValueError):
    pass


class LocalDocumentStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_pdf(self, filename: str, content: bytes) -> StoredFile:
        safe_name = Path(filename).name
        if Path(safe_name).suffix.lower() != ".pdf":
            raise InvalidFileTypeError("Only .pdf files are supported")

        document_id = f"doc_{uuid4().hex}"
        document_dir = self.root / document_id
        document_dir.mkdir(parents=True, exist_ok=False)
        target = document_dir / "original.pdf"
        target.write_bytes(content)

        digest = sha256(content).hexdigest()
        storage_key = str(target.relative_to(self.root)).replace("\\", "/")
        return StoredFile(
            document_id=document_id,
            filename=safe_name,
            storage_key=storage_key,
            sha256=digest,
            size_bytes=len(content),
        )
