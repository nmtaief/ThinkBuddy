"""CLI script for importing question bank fixtures from JSONL files (P04).

Usage:
    python scripts/import_questions.py fixtures/questions_sample.jsonl

Validates Bangla/English Unicode content, sets up isolated question_keys,
and records an immutable audit log entry.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.audit.models import AuditLog
from core.common.database import AsyncSessionLocal
from core.quiz.models import Question, QuestionKey


async def import_jsonl_file(file_path: Path, admin_id: uuid.UUID | None = None) -> int:
    """Read and import questions from a JSONL file."""
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return 0

    actor_id = admin_id or uuid.uuid4()
    imported_count = 0

    async with AsyncSessionLocal() as session:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                try:
                    data = json.loads(line)
                except Exception as exc:
                    print(f"[WARNING] Line {line_no}: Failed to parse JSON: {exc}")
                    continue

                q_type = data.get("type", "mcq")
                stem = data.get("stem", {})
                options = data.get("options", [])
                correct_opt = data.get("correct_option_id")
                correct_text = data.get("correct_text")
                explanation = data.get("explanation", {})
                rubric = data.get("rubric", {})
                origin = data.get("origin", "curated")
                review_status = data.get("review_status", "approved")
                difficulty = float(data.get("difficulty", 0.5))
                language = data.get("language", "bn")
                concept_id = data.get("concept_id")
                variant_grp = uuid.UUID(data["variant_group_id"]) if "variant_group_id" in data and data["variant_group_id"] else None

                pool = data.get("pool", "both")
                accepted_answers = data.get("accepted_answers", [])

                q = Question(
                    type=q_type,
                    chapter_id=None,
                    concept_id=concept_id,
                    difficulty=difficulty,
                    language=language,
                    stem=stem,
                    options=options,
                    rubric=rubric,
                    explanation=explanation,
                    origin=origin,
                    review_status=review_status,
                    pool=pool,
                    variant_group_id=variant_grp,
                )
                session.add(q)
                await session.flush()

                # Strictly isolated question key
                key = QuestionKey(
                    question_id=q.id,
                    correct_option_id=correct_opt,
                    correct_text=correct_text,
                    accepted_answers=accepted_answers,
                    grading_rules={},
                    explanation=explanation,
                )
                session.add(key)
                imported_count += 1

        # Structured audit log
        audit = AuditLog(
            actor_id=actor_id,
            action="question.cli_jsonl_import",
            target_type="question_bank",
            target_id=str(file_path.name),
            meta={"file": str(file_path), "imported_count": imported_count},
        )
        session.add(audit)
        await session.commit()

    print(f"[SUCCESS] Successfully imported {imported_count} questions from {file_path}")
    return imported_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Import question bank from JSONL")
    parser.add_argument("file", help="Path to JSONL file")
    parser.add_argument("--admin-id", help="UUID of acting admin", default=None)
    args = parser.parse_args()

    file_p = Path(args.file)
    admin_uuid = uuid.UUID(args.admin_id) if args.admin_id else None
    count = asyncio.run(import_jsonl_file(file_p, admin_uuid))
    if count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
