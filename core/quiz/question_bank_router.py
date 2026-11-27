"""FastAPI Router for Question Bank, Quiz Routing, and Mastery Tracking."""

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.progress_analytics import ProgressAnalytics
from api.quiz_modes import QuizGenerator
from services.mastery_tracker import MasteryTracker

router = APIRouter(prefix="/v1/quiz-bank", tags=["Question Bank & Mastery"])

# Global in-memory singleton tracker and sample catalog for routing
tracker_instance = MasteryTracker()
sample_catalog: list[dict[str, Any]] = []


def get_tracker():
    return tracker_instance


async def get_catalog() -> list[dict[str, Any]]:
    if sample_catalog:
        return sample_catalog
    try:
        from sqlalchemy import text

        from core.common.database import get_db_session

        async for db in get_db_session():
            q = text("""
                SELECT id, class_level, version, subject, paper,
                       book_topic_id, book_topic_name, subtopic_name,
                       source_type, format, cognitive_tier, difficulty, mcq_subtype,
                       question_text, options_json, correct_answer, explanation_text,
                       exact_citation, appearance_tags, repetitiveness_score, importance_score
                FROM questions
                WHERE question_text IS NOT NULL AND length(trim(question_text)) > 0
                ORDER BY importance_score DESC
                LIMIT 1000;
            """)
            rows = (await db.execute(q)).fetchall()
            items = []
            for r in rows:
                d = dict(r._mapping)
                d["id"] = str(d["id"])
                if d.get("book_topic_id"):
                    d["book_topic_id"] = str(d["book_topic_id"])
                if isinstance(d.get("options_json"), str):
                    try:
                        d["options_json"] = json.loads(d["options_json"])
                    except Exception:
                        pass
                d["options"] = d.get("options_json")
                if isinstance(d.get("appearance_tags"), str):
                    try:
                        d["appearance_tags"] = json.loads(d["appearance_tags"])
                    except Exception:
                        pass
                items.append(d)
            return items
    except Exception as e:
        print(f"Error fetching live catalog: {e}")
    return sample_catalog


async def fetch_matching_questions(
    class_level: int | None = None,
    subject: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "limit": limit,
        "class_level": class_level,
        "subject": f"%{subject}%" if subject else None,
        "format": filters.get("format") if filters else None,
        "cognitive_tier": filters.get("cognitive_tier") if filters else None,
        "source_type": filters.get("source_type") if filters else None,
    }

    if not subject:
        query_sql = """
            WITH ranked AS (
                SELECT q.id, q.class_level, q.version, q.subject, q.paper,
                       q.book_topic_id, COALESCE(bt.book_topic_name, q.book_topic_name) as book_topic_name, q.subtopic_name,
                       q.source_type, q.format, q.cognitive_tier, q.difficulty, q.mcq_subtype,
                       q.question_text, q.options_json, q.correct_answer, q.explanation_text,
                       q.exact_citation, q.appearance_tags, q.repetitiveness_score, q.importance_score,
                       q.uddipok_id, u.stem_text as uddipok_text,
                       ROW_NUMBER() OVER (PARTITION BY q.subject ORDER BY q.importance_score DESC, random()) as rn
                FROM questions q
                LEFT JOIN book_topics bt ON q.book_topic_id = bt.id
                LEFT JOIN uddipok_stems u ON q.uddipok_id = u.id
                WHERE q.question_text IS NOT NULL
                  AND length(trim(q.question_text)) > 0
                  AND (q.is_quarantined = FALSE OR q.is_quarantined IS NULL)
                  AND (q.is_auto_gradable = TRUE OR q.is_auto_gradable IS NULL)
                  AND (:class_level IS NULL OR q.class_level = :class_level)
                  AND (:subject IS NULL OR q.subject ILIKE :subject)
                  AND (:format IS NULL OR q.format = :format)
                  AND (:cognitive_tier IS NULL OR q.cognitive_tier = :cognitive_tier)
                  AND (:source_type IS NULL OR q.source_type = :source_type)
            )
            SELECT * FROM ranked
            WHERE rn <= 35
            ORDER BY rn, importance_score DESC
            LIMIT :limit;
        """
    else:
        query_sql = """
            SELECT q.id, q.class_level, q.version, q.subject, q.paper,
                   q.book_topic_id, COALESCE(bt.book_topic_name, q.book_topic_name) as book_topic_name, q.subtopic_name,
                   q.source_type, q.format, q.cognitive_tier, q.difficulty, q.mcq_subtype,
                   q.question_text, q.options_json, q.correct_answer, q.explanation_text,
                   q.exact_citation, q.appearance_tags, q.repetitiveness_score, q.importance_score,
                   q.uddipok_id, u.stem_text as uddipok_text
            FROM questions q
            LEFT JOIN book_topics bt ON q.book_topic_id = bt.id
            LEFT JOIN uddipok_stems u ON q.uddipok_id = u.id
            WHERE q.question_text IS NOT NULL
              AND length(trim(q.question_text)) > 0
              AND (q.is_quarantined = FALSE OR q.is_quarantined IS NULL)
              AND (q.is_auto_gradable = TRUE OR q.is_auto_gradable IS NULL)
              AND (:class_level IS NULL OR q.class_level = :class_level)
              AND (:subject IS NULL OR q.subject ILIKE :subject)
              AND (:format IS NULL OR q.format = :format)
              AND (:cognitive_tier IS NULL OR q.cognitive_tier = :cognitive_tier)
              AND (:source_type IS NULL OR q.source_type = :source_type)
            ORDER BY q.importance_score DESC
            LIMIT :limit;
        """
    try:
        from sqlalchemy import text

        from core.common.database import get_db_session

        async for db in get_db_session():
            rows = (await db.execute(text(query_sql), params)).fetchall()
            items = []
            for r in rows:
                d = dict(r._mapping)
                d["id"] = str(d["id"])
                if d.get("book_topic_id"):
                    d["book_topic_id"] = str(d["book_topic_id"])
                if d.get("uddipok_id"):
                    d["uddipok_id"] = str(d["uddipok_id"])
                if isinstance(d.get("options_json"), str):
                    try:
                        d["options_json"] = json.loads(d["options_json"])
                    except Exception:
                        pass
                d["options"] = d.get("options_json")
                if isinstance(d.get("appearance_tags"), str):
                    try:
                        d["appearance_tags"] = json.loads(d["appearance_tags"])
                    except Exception:
                        pass
                items.append(d)
            if items:
                return items
    except Exception as e:
        print(f"Error fetching matching questions: {e}")
    return await get_catalog()


class DailyQuizRequest(BaseModel):
    user_id: str
    class_level: int = Field(default=8, ge=6, le=12)
    subject: str | None = None
    limit: int = Field(default=10, ge=5, le=30)


class PracticeQuizRequest(BaseModel):
    user_id: str
    class_level: int | None = Field(default=8, ge=6, le=12)
    subject: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=5, le=50)


class QuizAttemptRequest(BaseModel):
    user_id: str
    question_id: str
    is_correct: bool
    quiz_mode: str = "daily_quiz"
    time_taken_sec: int = 30
    question_metadata: dict[str, Any] | None = None


@router.get("/daily")
async def get_daily_quiz_endpoint(
    user_id: str = Query(...),
    class_level: int = Query(default=8, ge=6, le=12),
    limit: int = Query(default=10, ge=5, le=30),
    subject: str | None = Query(default=None),
    tracker: MasteryTracker = Depends(get_tracker),
    catalog: list[dict[str, Any]] = Depends(get_catalog),
):
    """Generates a 40/40/20 Daily Quiz with answer keys redacted (GET)."""
    pool = await fetch_matching_questions(class_level=class_level, subject=subject, limit=100)
    gen = QuizGenerator(pool or catalog, tracker)
    quiz = gen.generate_daily_quiz(user_id, class_level, limit, subject=subject)
    return {
        "user_id": user_id,
        "class_level": class_level,
        "total_items": len(quiz),
        "quiz_mode": "daily_quiz",
        "items": quiz,
    }


@router.post("/daily")
async def generate_daily_quiz_endpoint(
    req: DailyQuizRequest,
    tracker: MasteryTracker = Depends(get_tracker),
    catalog: list[dict[str, Any]] = Depends(get_catalog),
):
    """Generates a 40/40/20 Daily Quiz with answer keys redacted (POST)."""
    pool = await fetch_matching_questions(
        class_level=req.class_level, subject=req.subject, limit=100
    )
    gen = QuizGenerator(pool or catalog, tracker)
    quiz = gen.generate_daily_quiz(req.user_id, req.class_level, req.limit, subject=req.subject)
    return {
        "user_id": req.user_id,
        "class_level": req.class_level,
        "total_items": len(quiz),
        "quiz_mode": "daily_quiz",
        "items": quiz,
    }


@router.post("/practice")
async def generate_practice_quiz_endpoint(
    req: PracticeQuizRequest,
    tracker: MasteryTracker = Depends(get_tracker),
    catalog: list[dict[str, Any]] = Depends(get_catalog),
):
    """Generates a multi-filtered Practice Quiz with answer keys redacted."""
    active_filters = dict(req.filters)
    if req.class_level:
        active_filters.setdefault("class_level", req.class_level)
    if req.subject:
        active_filters.setdefault("subject", req.subject)

    pool = await fetch_matching_questions(
        class_level=req.class_level, subject=req.subject, filters=req.filters, limit=200
    )
    gen = QuizGenerator(pool or catalog, tracker)
    quiz = gen.generate_practice_quiz(req.user_id, active_filters, req.limit)
    return {
        "user_id": req.user_id,
        "total_items": len(quiz),
        "quiz_mode": "practice_quiz",
        "items": quiz,
    }


@router.post("/attempt")
async def record_quiz_attempt_endpoint(
    req: QuizAttemptRequest,
    tracker: MasteryTracker = Depends(get_tracker),
    catalog: list[dict[str, Any]] = Depends(get_catalog),
):
    """Submits a single question attempt and updates state machine & rollups."""
    # Lookup question
    q = None
    for item in catalog:
        if str(item.get("id")) == str(req.question_id):
            q = item
            break
    if not q:
        q = req.question_metadata or {
            "id": req.question_id,
            "class_level": 8,
            "subject": "math",
            "book_topic_id": "default",
            "book_topic_name": "General Topic",
            "related_topic_ids": [],
        }

    db_conn = None
    try:
        from core.common.database import get_db_session

        async for db in get_db_session():
            db_conn = db
            break
    except Exception:
        pass

    res = await tracker.record_quiz_attempt_db(
        db=db_conn,
        user_id=req.user_id,
        question=q,
        is_correct=req.is_correct,
        quiz_mode=req.quiz_mode,
        time_taken_sec=req.time_taken_sec,
    )
    return res


@router.get("/progress/hierarchical")
async def get_hierarchical_progress_endpoint(
    user_id: str = Query(...),
    class_level: int = Query(default=8, ge=6, le=12),
    tracker: MasteryTracker = Depends(get_tracker),
    catalog: list[dict[str, Any]] = Depends(get_catalog),
):
    """Returns the nested tree: Class -> Subjects -> Chapters -> Topics -> Cognitive Tiers."""
    analytics = ProgressAnalytics(tracker, catalog)
    return analytics.get_hierarchical_progress(user_id, class_level)
