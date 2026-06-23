import argparse
import json
import os
from pathlib import Path

from backend.process_raw_data.process_service import process_file

_SUPPORTED_SUFFIXES = {
    ".md",
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
}
 

def _iter_input_files(input_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(input_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    ]


def _output_paths(input_dir: Path, output_dir: Path, source_path: Path) -> tuple[Path, Path]:
    relative = source_path.relative_to(input_dir)
    markdown_path = (output_dir / relative).with_suffix(".md")
    metadata_path = markdown_path.with_suffix(".metadata.json")
    return markdown_path, metadata_path


def process_directory(input_dir: Path, output_dir: Path) -> None:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    files = _iter_input_files(input_dir)
    print(f"Found {len(files)} supported files in {input_dir}")

    for source_path in files:
        print(f"Processing {source_path}...")
        doc = process_file(source_path)
        if doc is None:
            print("  Skipped: unsupported or empty result")
            continue

        markdown_path, metadata_path = _output_paths(input_dir, output_dir, source_path)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)

        markdown_path.write_text(doc["content"], encoding="utf-8")
        metadata_path.write_text(
            json.dumps(doc["metadata"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  Wrote {markdown_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process raw documents into markdown for ingestion")
    parser.add_argument(
        "--input-dir",
        default=os.getenv("RAW_DATA_DIR", "/app/data/raw"),
        help="Directory containing raw input files",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("PROCESSED_DATA_DIR", "/app/data/processed"),
        help="Directory where processed markdown files will be written",
    )
    args = parser.parse_args()

    process_directory(Path(args.input_dir), Path(args.output_dir))


if __name__ == "__main__":
    main()
