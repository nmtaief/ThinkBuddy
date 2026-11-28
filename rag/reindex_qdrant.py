"""Re-indexing & Two-Layer Sync Utility for Existing OCR/Textbook Data.

Migrates existing PostgreSQL curriculum tables (books, chapters, concepts, chunks,
exercise_items) or JSONL manifests into:
1. Layer 1: Structural Syllabus Map (rag/syllabus_index.py)
2. Layer 2: Typed Hybrid Vector Collection in Qdrant (rag/qdrant_store.py)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.common.database import AsyncSessionLocal
from core.curriculum.models import Book, Chunk, Concept, ExerciseItem
from rag.bilingual_map import translate_chapter_title_en
from rag.qdrant_store import BookChunkPayload, QdrantBookStore, get_qdrant_store
from rag.syllabus_index import SyllabusChapterEntry, SyllabusIndexStore, get_syllabus_index_store

logger = logging.getLogger(__name__)


def classify_content_and_category(
    chunk_type: str | None = None,
    text: str = "",
    item_type: str | None = None,
) -> tuple[str, str]:
    """Map legacy chunk_type / item_type into strict (content_type, question_category)."""
    ct_raw = (chunk_type or "").strip().lower()
    it_raw = (item_type or "").strip().lower()
    txt_lower = (text or "").lower()

    if ct_raw in ("worked_example", "example") or "উদাহরণ" in txt_lower or "example" in txt_lower:
        content_type = "worked_example"
    elif ct_raw in ("exercise", "exercise_question", "question") or it_raw:
        content_type = "exercise_question"
    else:
        content_type = "concept"

    if content_type == "concept":
        return content_type, "none"

    if it_raw in ("cq", "creative", "সৃজনশীল") or "সৃজনশীল" in txt_lower or "(ঘ)" in txt_lower:
        category = "cq"
    elif it_raw in ("mcq", "multiple_choice", "বহুনির্বাচনি") or "নিচের কোনটি" in txt_lower:
        category = "mcq"
    elif it_raw in ("gyanmulok", "জ্ঞানমূলক") or "কাকে বলে" in txt_lower or "কী?" in txt_lower:
        category = "gyanmulok"
    elif it_raw in ("anudhabon", "অনুধাবন", "short") or "কেন" in txt_lower or "ব্যাখ্যা" in txt_lower:
        category = "anudhabon"
    elif it_raw == "numerical" or re.search(
        r"নির্ণয় করো|হিসাব করো|calculate|find the value", txt_lower
    ):
        category = "numerical"
    else:
        category = "none"

    return content_type, category


async def reindex_postgres_to_qdrant(
    qdrant_store: QdrantBookStore | None = None,
    syllabus_store: SyllabusIndexStore | None = None,
    class_level: int | None = None,
    subject: str | None = None,
    batch_size: int = 256,
    max_rows: int | None = None,
) -> dict[str, int]:
    """Read existing PostgreSQL books/chapters/chunks/exercises/questions and index into Layer 1 & Layer 2."""
    q_store = qdrant_store or get_qdrant_store()
    s_store = syllabus_store or get_syllabus_index_store()

    books_indexed = 0
    chapters_indexed = 0
    chunks_indexed = 0
    exercises_indexed = 0

    async with AsyncSessionLocal() as session:
        stmt = select(Book).options(selectinload(Book.chapters))
        if class_level is not None:
            stmt = stmt.where(Book.class_level == class_level)
        if subject:
            stmt = stmt.where(Book.subject.ilike(f"%{subject}%"))
        books = (await session.execute(stmt)).scalars().all()

        for book in books:
            books_indexed += 1
            prev_chapter_title: str | None = None
            for chapter in sorted(book.chapters, key=lambda c: c.number):
                concepts = (
                    (await session.execute(select(Concept).where(Concept.chapter_id == chapter.id)))
                    .scalars()
                    .all()
                )

                topics = [c.title for c in concepts if c.kind in ("concept", "definition")]
                formulas = [c.title for c in concepts if c.kind == "formula"]
                if not topics:
                    topics = [chapter.title]

                prereqs = (
                    [prev_chapter_title]
                    if prev_chapter_title
                    else [
                        f"Foundational {book.subject} concepts (Class {max(5, book.class_level - 1)})"
                    ]
                )
                prev_chapter_title = chapter.title or f"Chapter {chapter.number}"

                en_title = (
                    chapter.title
                    if book.medium == "en"
                    else translate_chapter_title_en(chapter.title, book.subject, chapter.number)
                )
                if en_title and en_title not in topics:
                    topics = [*topics, en_title]

                s_store.upsert_entry(
                    SyllabusChapterEntry(
                        book_name=book.title,
                        subject=book.subject,
                        class_level=book.class_level,
                        chapter_number=chapter.number,
                        chapter_title_bn=chapter.title if book.medium == "bn" else "",
                        chapter_title_en=en_title,
                        topics=topics,
                        key_formulas_and_definitions=formulas,
                        prerequisite_topics=prereqs,
                    )
                )
                chapters_indexed += 1

                # Index retrievable chunks for this chapter
                chunks = (
                    (
                        await session.execute(
                            select(Chunk).where(
                                Chunk.chapter_id == chapter.id,
                                Chunk.retrievable.is_(True),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                payloads: list[BookChunkPayload] = []
                concept_map = {c.id: c.title for c in concepts}
                for chk in chunks:
                    c_type, q_cat = classify_content_and_category(chk.chunk_type, chk.text)
                    topic_name = concept_map.get(chk.concept_id) or chapter.title
                    lang = chk.language if chk.language in ("bn", "en") else "bn"
                    header_prefix = (
                        f"{book.title} | Ch {chapter.number} | {topic_name} / {en_title}\n"
                    )
                    payloads.append(
                        BookChunkPayload(
                            chunk_id=str(chk.id),
                            source_table="chunks",
                            chunk_index=chk.chunk_index,
                            book_name=book.title,
                            subject=book.subject,
                            chapter_number=chapter.number,
                            topic=topic_name,
                            language=lang,
                            content_type=c_type,
                            question_category=q_cat,
                            text=chk.text,
                            embedding_text=f"{header_prefix}{chk.text}",
                            printed_page=chk.printed_page,
                            pdf_page_index=chk.pdf_page_index,
                            curriculum_year=2026,
                            schema_version="2.0",
                            updated_at=chk.updated_at.isoformat() if chk.updated_at else None,
                        )
                    )

                if payloads:
                    chunks_indexed += await q_store.upsert_chunks(payloads)

                # Index exercise items for this chapter
                ex_items = (
                    (
                        await session.execute(
                            select(ExerciseItem).where(ExerciseItem.chapter_id == chapter.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                ex_payloads: list[BookChunkPayload] = []
                for ex in ex_items:
                    _, q_cat = classify_content_and_category(
                        "exercise_question", ex.question_text, item_type=ex.item_type
                    )
                    lang = "en" if book.medium == "en" else "bn"
                    topic_lbl = ex.exercise_label or chapter.title
                    header_prefix = f"{book.title} | Ch {chapter.number} | {topic_lbl}\n"
                    ex_payloads.append(
                        BookChunkPayload(
                            chunk_id=str(ex.id),
                            source_table="exercise_items",
                            chunk_index=0,
                            book_name=book.title,
                            subject=book.subject,
                            chapter_number=chapter.number,
                            topic=topic_lbl,
                            language=lang,
                            content_type="exercise_question",
                            question_category=q_cat,
                            text=ex.question_text,
                            embedding_text=f"{header_prefix}{ex.question_text}",
                            printed_page=ex.printed_page,
                            pdf_page_index=ex.pdf_page_index,
                            answer_key=ex.answer_key,
                            curriculum_year=2026,
                            schema_version="2.0",
                            updated_at=ex.updated_at.isoformat() if ex.updated_at else None,
                        )
                    )
                if ex_payloads:
                    exercises_indexed += await q_store.upsert_chunks(ex_payloads)

        # Index active Question Bank rows (questions table) using paginated batching
        from sqlalchemy import text as sql_text

        offset_rows = 0
        eff_batch = max(32, int(batch_size))
        while True:
            if max_rows is not None and offset_rows >= max_rows:
                break
            fetch_limit = eff_batch if max_rows is None else min(eff_batch, max_rows - offset_rows)
            q_rows = (
                (
                    await session.execute(
                        sql_text("""
                        SELECT q.id, q.class_level, q.version, q.subject, q.book_topic_name,
                               q.format, q.cognitive_tier, q.question_text, q.correct_answer,
                               q.updated_at, COALESCE(bt.chapter_number, 1) AS chapter_number
                        FROM questions q
                        LEFT JOIN book_topics bt ON q.book_topic_id = bt.id
                        WHERE (q.is_quarantined = FALSE OR q.is_quarantined IS NULL)
                          AND q.question_text IS NOT NULL
                          AND length(trim(q.question_text)) > 0
                        ORDER BY q.id
                        LIMIT :lim OFFSET :off;
                    """),
                        {"lim": fetch_limit, "off": offset_rows},
                    )
                )
                .mappings()
                .all()
            )

            if not q_rows:
                break

            qb_payloads: list[BookChunkPayload] = []
            for qr in q_rows:
                fmt = (qr["format"] or "").lower()
                tier = (qr["cognitive_tier"] or "").lower()
                if fmt == "mcq":
                    q_cat = "mcq"
                elif fmt == "cq":
                    q_cat = "cq"
                elif "gyan" in tier:
                    q_cat = "gyanmulok"
                elif "anudhabon" in tier:
                    q_cat = "anudhabon"
                else:
                    _, q_cat = classify_content_and_category(
                        "exercise_question", qr["question_text"], item_type=fmt
                    )
                lang = qr["version"] if qr["version"] in ("bn", "en") else "bn"
                subj = (qr["subject"] or "general").lower()
                cl = qr["class_level"] or 8
                b_name = f"Class {cl} {subj.title()} ({lang.upper()})"
                ch_num = int(qr["chapter_number"] or 1)
                topic_lbl = qr["book_topic_name"] or subj.title()
                raw_q_text = qr["question_text"].strip()
                header_prefix = f"{b_name} | Ch {ch_num} | {topic_lbl}\n"
                qb_payloads.append(
                    BookChunkPayload(
                        chunk_id=str(qr["id"]),
                        source_table="questions",
                        chunk_index=0,
                        book_name=b_name,
                        subject=subj,
                        chapter_number=ch_num,
                        topic=topic_lbl,
                        language=lang,
                        content_type="exercise_question",
                        question_category=q_cat,
                        text=raw_q_text,
                        embedding_text=f"{header_prefix}{raw_q_text}",
                        printed_page=1,
                        pdf_page_index=1,
                        answer_key=qr["correct_answer"],
                        curriculum_year=2026,
                        schema_version="2.0",
                        updated_at=qr["updated_at"].isoformat() if qr["updated_at"] else None,
                    )
                )
            exercises_indexed += await q_store.upsert_chunks(qb_payloads)
            offset_rows += len(q_rows)

    s_store.save()
    stats = {
        "books_indexed": books_indexed,
        "chapters_indexed": chapters_indexed,
        "chunks_indexed": chunks_indexed,
        "exercises_indexed": exercises_indexed,
    }
    logger.info("Re-indexed PostgreSQL curriculum to Qdrant & SyllabusIndex: %s", stats)
    return stats


async def index_manifest_to_layers(
    manifest_path: str | Path,
    qdrant_store: QdrantBookStore | None = None,
    syllabus_store: SyllabusIndexStore | None = None,
) -> dict[str, int]:
    """Index a Knowledge Factory JSONL manifest directly into Layer 1 and Layer 2."""
    path = Path(manifest_path)
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    header = json.loads(lines[0])
    book_info = header["book"]
    chapters_info = header.get("chapters", [])
    concepts_info = header.get("concepts", [])
    chunk_lines = [
        json.loads(line) for line in lines[1:] if json.loads(line).get("type") == "chunk"
    ]

    q_store = qdrant_store or get_qdrant_store()
    s_store = syllabus_store or get_syllabus_index_store()

    chapter_by_id = {str(ch["id"]): ch for ch in chapters_info}
    concept_by_id = {str(cp["id"]): cp for cp in concepts_info}

    prev_title: str | None = None
    for ch in sorted(chapters_info, key=lambda c: int(c.get("number", 1))):
        ch_id = str(ch["id"])
        ch_concepts = [cp for cp in concepts_info if str(cp.get("chapter_id")) == ch_id]
        topics = [cp["title"] for cp in ch_concepts if cp.get("kind", "concept") != "formula"] or [
            ch["title"]
        ]
        formulas = [cp["title"] for cp in ch_concepts if cp.get("kind") == "formula"]
        prereqs = [prev_title] if prev_title else []
        prev_title = ch["title"]
        s_store.upsert_entry(
            SyllabusChapterEntry(
                book_name=book_info["title"],
                subject=book_info["subject"],
                class_level=int(book_info.get("class_level", 8)),
                chapter_number=int(ch["number"]),
                chapter_title_bn=ch["title"] if book_info.get("medium", "bn") == "bn" else "",
                chapter_title_en=ch["title"] if book_info.get("medium", "bn") == "en" else "",
                topics=topics,
                key_formulas_and_definitions=formulas,
                prerequisite_topics=prereqs,
            )
        )
    s_store.save()

    payloads: list[BookChunkPayload] = []
    for item in chunk_lines:
        ch = chapter_by_id.get(str(item.get("chapter_id")), {})
        cp = concept_by_id.get(str(item.get("concept_id")), {})
        c_type, q_cat = classify_content_and_category(
            item.get("content_type") or item.get("chunk_type"),
            item.get("text", ""),
            item_type=item.get("question_category"),
        )
        payloads.append(
            BookChunkPayload(
                chunk_id=str(item.get("id")) if item.get("id") else None,
                book_name=book_info["title"],
                subject=book_info["subject"],
                chapter_number=int(ch.get("number", 1)),
                topic=item.get("topic") or cp.get("title") or ch.get("title", "General"),
                language=item.get("language", book_info.get("medium", "bn")),
                content_type=c_type,
                question_category=q_cat,
                text=item["text"].strip(),
                printed_page=int(item.get("printed_page", 1)),
                pdf_page_index=int(item.get("pdf_page_index", 1)),
                answer_key=item.get("answer_key"),
            )
        )
    upserted = await q_store.upsert_chunks(payloads)
    return {"chapters_indexed": len(chapters_info), "chunks_indexed": upserted}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(reindex_postgres_to_qdrant())
