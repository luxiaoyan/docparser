#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def mineru_version() -> str:
    try:
        return version("mineru")
    except PackageNotFoundError:
        return "unknown"


def find_output_dir(output_root: Path, input_path: Path, method: str) -> Path:
    expected = output_root / input_path.stem / method
    if expected.exists():
        return expected

    candidates = sorted(output_root.glob(f"{input_path.stem}/*"))
    if candidates:
        return candidates[0]

    raise RuntimeError(f"MinerU did not create an output directory under {output_root}")


def read_content_list(output_dir: Path, stem: str) -> list[dict[str, object]]:
    content_path = output_dir / f"{stem}_content_list.json"
    if not content_path.exists():
        return []

    with content_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def build_payload(input_path: Path, output_dir: Path, method: str) -> dict[str, object]:
    markdown_path = output_dir / f"{input_path.stem}.md"
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    content_items = read_content_list(output_dir, input_path.stem)

    text_blocks: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    images: list[dict[str, object]] = []

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
                    "source": "mineru",
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
                    "source": "mineru",
                    "confidence": 0.85,
                }
            )
        elif item_type == "image":
            images.append(
                {
                    "image_id": f"img_{index:04d}",
                    "page_no": page_no,
                    "storage_key": item.get("img_path") or item.get("image_path") or "",
                    "source": "mineru",
                }
            )

    if markdown and not text_blocks:
        text_blocks.append(
            {
                "block_id": "txt_0001",
                "type": "paragraph",
                "text": markdown.strip(),
                "page_no": 1,
                "source": "mineru",
                "confidence": 0.8,
            }
        )

    output_files = [str(path.relative_to(output_dir)) for path in sorted(output_dir.glob("*")) if path.is_file()]

    return {
        "version": mineru_version(),
        "status": "success",
        "parse_mode": method,
        "markdown": markdown,
        "text_blocks": text_blocks,
        "tables": tables,
        "images": images,
        "warnings": [],
        "raw": {
            "markdown": markdown,
            "content_list": content_items,
            "output_files": output_files,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MinerU and emit docparser-compatible JSON.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--backend", default="pipeline")
    parser.add_argument("--method", default="txt")
    args = parser.parse_args()

    input_path = args.input.resolve()
    mineru_exe = Path(sys.executable).with_name("mineru")
    if not mineru_exe.exists():
        print(f"mineru executable not found next to {sys.executable}", file=sys.stderr)
        return 127

    with tempfile.TemporaryDirectory(prefix="docparser-mineru-") as temp_dir:
        output_root = Path(temp_dir)
        completed = subprocess.run(
            [
                str(mineru_exe),
                "-p",
                str(input_path),
                "-o",
                str(output_root),
                "-b",
                args.backend,
                "-m",
                args.method,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
            sys.stderr.write(completed.stdout)
            return completed.returncode

        output_dir = find_output_dir(output_root, input_path, args.method)
        json.dump(build_payload(input_path, output_dir, args.method), sys.stdout, ensure_ascii=False)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
