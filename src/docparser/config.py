from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParserSettings:
    max_file_size_bytes: int = 100 * 1024 * 1024
    max_pages: int = 300
    storage_root: Path = Path("data/documents")
    mineru_command: str | None = None
    mineru_service_url: str | None = None
