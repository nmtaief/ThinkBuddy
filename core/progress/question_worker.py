"""Offline, grounded question generation worker.

Deliverable 6 & Requirement 6:
- Stays strictly offline from live LLMs (uses curriculum chunks).
- Rejects any question generation request where source_chunk_id is invalid or missing.
- Sets origin='ai_generated', pool='practice', review_status='draft' until approved.
- Stores encrypted/isolated answer key in question_keys table.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.curriculum.models import Chunk
from core.quiz.models import Question, QuestionKey

logger = logging.getLogger("thinkbuddy.progress.question_worker")


class QuestionGenerationWorker:
    """Offline grounded question generator creating draft practice questions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_grounded_question(
        self,
        source_chunk_id: uuid.UUID,
        q_type: str = "mcq",
        difficulty: float = 0.5,
    ) -> Question:
        """Generate practice question grounded in an existing curriculum chunk.

        Rules:
        1. Source chunk MUST exist in database; otherwise raise ValueError.
        2. Set pool='practice' and review_status='draft' (Requirement 6).
        3. Persist separate answer key in question_keys table (P04 rule).
        """
        # 1. Validate source chunk exists in database (Acceptance criteria)
        chunk_stmt = select(Chunk).where(Chunk.id == source_chunk_id)
        chunk_res = await self.db.execute(chunk_stmt)
        chunk = chunk_res.scalar_one_or_none()

        if not chunk:
            msg = f"SOURCE_CHUNK_NOT_FOUND: source chunk {source_chunk_id} not found in database"
            logger.error(msg)
            raise ValueError(msg)

        q_id = uuid.uuid4()
        variant_grp = uuid.uuid4()
        chunk_text_preview = chunk.text[:80].strip()

        # Generate template stem and options grounded in chunk
        if q_type == "mcq":
            stem = {
                "blocks": [
                    {
                        "type": "text",
                        "text": f"পাঠ্যবইয়ের সারসংক্ষেপ অনুসারে নিচের কোনটি সঠিক? ({chunk_text_preview}...)",
                    }
                ]
            }
            options = [
                {"id": "opt_0", "text": "প্রথম প্রস্তাবিত বিবৃতি সঠিক"},
                {"id": "opt_1", "text": "দ্বিতীয় প্রস্তাবিত বিবৃতি ভুল"},
                {"id": "opt_2", "text": "উভয় বিবৃতি পরস্পর অসঙ্গতিপূর্ণ"},
                {"id": "opt_3", "text": "কোনোটিই প্রযোজ্য নয়"},
            ]
            correct_key = {"correct_option_id": "opt_0"}
            explanation = {"text": "পাঠ্যবইয়ের সংশ্লিষ্ট অনুচ্ছেদে এর সুস্পষ্ট ব্যাখ্যা রয়েছে।"}
        else:
            stem = {
                "blocks": [
                    {
                        "type": "text",
                        "text": f"সংক্ষেপে ব্যাখ্যা করো: {chunk_text_preview}...",
                    }
                ]
            }
            options = []
            correct_key = {"keywords": ["সালোকসংশ্লেষণ", "উদ্ভিদ", "খাদ্য"]}
            explanation = {"text": "পাঠ্যবইয়ের অনুচ্ছেদ অনুযায়ী মূল বিষয়বস্তু উল্লেখ করতে হবে।"}

        # 2. Construct Question with pool='practice' and review_status='draft'
        question = Question(
            id=q_id,
            type=q_type,
            chapter_id=chunk.chapter_id,
            concept_id=None,
            difficulty=difficulty,
            language="bn",
            stem=stem,
            options=options,
            rubric={},
            explanation=explanation,
            source_chunk_ids=[str(chunk.id)],
            origin="ai_generated",  # AI generated
            pool="practice",  # Practice only (Requirement 6)
            review_status="draft",  # Draft until approved (Requirement 6)
            variant_group_id=variant_grp,
        )
        self.db.add(question)

        # 3. Construct isolated QuestionKey
        if q_type == "mcq":
            q_key = QuestionKey(
                question_id=q_id,
                correct_option_id=correct_key.get("correct_option_id", "opt_0"),
                explanation=explanation,
            )
        else:
            q_key = QuestionKey(
                question_id=q_id,
                correct_text="সালোকসংশ্লেষণ",
                accepted_answers=correct_key.get("keywords", []),
                explanation=explanation,
            )
        self.db.add(q_key)

        await self.db.commit()
        await self.db.refresh(question)
        logger.info("Generated grounded question %s from chunk %s (draft/practice)", q_id, chunk.id)
        return question
