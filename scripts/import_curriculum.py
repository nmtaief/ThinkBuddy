"""CLI command to import Knowledge Factory curriculum manifest files into PostgreSQL + pgvector."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.ingest import CurriculumImporter


async def run_import(manifest_path: str, resume: bool = True) -> int:
    path = Path(manifest_path)
    if not path.is_file():
        print(f"Error: Manifest file '{manifest_path}' does not exist.", file=sys.stderr)
        return 1

    print(f"Starting curriculum ingestion from: {manifest_path}")
    importer = CurriculumImporter()
    result = await importer.import_manifest(manifest_path, resume=resume)

    print("\n" + "=" * 50)
    print("INGESTION COMPLETED")
    print(f"  • Batch ID:            {result.batch_id}")
    print(f"  • Book ID:             {result.book_id}")
    print(f"  • Total in Manifest:   {result.total_manifest_chunks}")
    print(f"  • Newly Ingested:      {result.newly_ingested}")
    print(f"  • Skipped (Existing):  {result.already_existing}")
    print(f"  • Unretrievable:       {result.unretrievable_chunks}")
    print(f"  • Status:              {result.status}")
    print("=" * 50)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Import curriculum manifest into ThinkBuddy")
    parser.add_argument("manifest", help="Path to Knowledge Factory manifest (.jsonl)")
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume; re-process all chunks",
    )

    args = parser.parse_args()
    code = asyncio.run(run_import(args.manifest, resume=not args.no_resume))
    sys.exit(code)


if __name__ == "__main__":
    main()
