"""Curriculum RAG tool definitions and execution engine for Buddy AI Tutor.

Implements function calling tools:
- get_exercise_question(class_level?, subject?, chapter?, exercise_label?, question_no, subpart?)
- list_available_books()
- search_textbook(query, subject, chapter, top_k)
- get_chapter_list(subject, class_level?)
- get_page(subject, printed_page, class_level?)
- get_concepts(concept_or_topic)
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.curriculum.models import Book, Chapter, Chunk, Concept, ExerciseItem

logger = logging.getLogger(__name__)

# Standard OpenAI / OpenRouter function calling tool schema
CHAT_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_exercise_question",
            "description": (
                "Retrieve the exact textbook exercise problem/question text by its question number and exercise label. "
                "Call this whenever a student asks for a specific question (e.g. 'অনুশীলনী ১ এর ৩ নং', 'chapter 1 er 3 no', 'ex 9.1 no 5')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question_no": {
                        "type": "integer",
                        "description": "Question number (e.g. 3, 5).",
                    },
                    "class_level": {
                        "type": "integer",
                        "description": "Optional class level (e.g. 6, 7, 8, 9, 10). If omitted, student's current class is used.",
                    },
                    "subject": {
                        "type": "string",
                        "enum": ["math", "science", "english", "bangla"],
                        "description": "Subject of the textbook (e.g. 'math' or 'science').",
                    },
                    "chapter": {
                        "type": "string",
                        "description": "Optional chapter number (e.g. '1', '9') or chapter title (e.g. 'প্যাটার্ন').",
                    },
                    "exercise_label": {
                        "type": "string",
                        "description": "Exercise label (e.g. 'অনুশীলনী ১', 'অনুশীলনী ৯.১', '1.1').",
                    },
                    "subpart": {
                        "type": "string",
                        "description": "Optional subpart (e.g. 'ক', 'খ', 'a', 'b').",
                    },
                },
                "required": ["question_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_available_books",
            "description": (
                "List all authoritative NCTB textbook titles, classes, and subjects currently available in ThinkBuddy's library. "
                "Call this when the student asks what books exist, or asks about SSC books, Class 9 books, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_chapter_list",
            "description": (
                "Get the ordered list of chapters from the student's authoritative NCTB textbook. "
                "Use this to resolve queries like 'last chapter', 'first chapter', 'chapter 3', "
                "or subject chapters like 'statistics chapter' / 'পরিসংখ্যান অধ্যায়'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "enum": ["math", "science", "english", "bangla"],
                        "description": "Subject of the textbook (e.g. 'math' or 'science').",
                    },
                    "class_level": {
                        "type": "integer",
                        "description": "Optional class level (e.g. 6, 7, 8, 9).",
                    },
                },
                "required": ["subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_textbook",
            "description": (
                "Search the student's class textbook for specific passages, definitions, formulas, "
                "or worked examples. Call this when you need to verify or cite curriculum content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords or concept phrase to search for.",
                    },
                    "subject": {
                        "type": "string",
                        "enum": ["math", "science", "english", "bangla"],
                        "description": "Optional subject to restrict search to.",
                    },
                    "class_level": {
                        "type": "integer",
                        "description": "Optional class level.",
                    },
                    "chapter": {
                        "type": "string",
                        "description": "Optional chapter number (e.g. '11' or '9') or chapter title.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of passages to return (default 3, max 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page",
            "description": (
                "Retrieve textbook text from an exact printed page number in the student's class textbook."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "enum": ["math", "science", "english", "bangla"],
                        "description": "Textbook subject.",
                    },
                    "printed_page": {
                        "type": "integer",
                        "description": "The printed page number shown in the physical textbook.",
                    },
                    "class_level": {
                        "type": "integer",
                        "description": "Optional class level.",
                    },
                },
                "required": ["subject", "printed_page"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_concepts",
            "description": (
                "Retrieve concept definitions, formulas, and guided study hints for an educational topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "concept_or_topic": {
                        "type": "string",
                        "description": "Concept or formula name (e.g. 'Pythagoras', 'মিয়োসিস', 'গড় ও মধ্যক').",
                    },
                    "class_level": {
                        "type": "integer",
                        "description": "Optional class level.",
                    },
                },
                "required": ["concept_or_topic"],
            },
        },
    },
]


def normalize_subject_name(raw: str | None) -> str:
    """Normalize subject inputs like 'maths', 'gonit', 'গণিত' to standard keys."""
    if not raw:
        return "math"
    s = raw.strip().lower()
    if any(k in s for k in ["math", "গণিত", "অঙ্ক", "algebra", "geometry", "trigonometry", "ত্রিকোণমিতি", "statistics"]):
        return "math"
    if any(k in s for k in ["science", "বিজ্ঞান", "biology", "physics", "chemistry"]):
        return "science"
    if any(k in s for k in ["english", "ইংরেজি"]):
        return "english"
    if any(k in s for k in ["bangla", "বাংলা"]):
        return "bangla"
    return "math"


class ToolExecutor:
    """Executes AI Tutor tool calls against the curriculum database."""

    def __init__(self, db: AsyncSession, student_profile: dict[str, Any] | None = None) -> None:
        self.db = db
        self.student_profile = student_profile or {"class_level": 8, "medium": "bn"}
        self.used_citations: list[dict[str, Any]] = []

    async def execute_tool(self, name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        """Dispatch and execute tool call."""
        if not args or not isinstance(args, dict):
            args = {}
        default_class = int(self.student_profile.get("class_level", 8))
        class_level = int(args.get("class_level") or default_class)
        medium = self.student_profile.get("medium", "bn")

        if name == "get_exercise_question":
            subject = normalize_subject_name(args.get("subject"))
            chapter = str(args.get("chapter")) if args.get("chapter") is not None else None
            exercise_label = str(args.get("exercise_label")) if args.get("exercise_label") else None
            question_no = int(args.get("question_no", 0))
            subpart = str(args.get("subpart")) if args.get("subpart") else None
            return await self._get_exercise_question(
                class_level, subject, medium, chapter, exercise_label, question_no, subpart
            )

        elif name == "list_available_books":
            return await self._list_available_books()

        elif name == "get_chapter_list":
            subject = normalize_subject_name(args.get("subject"))
            return await self._get_chapter_list(class_level, subject, medium)

        elif name == "search_textbook":
            query = str(args.get("query", ""))
            subject = normalize_subject_name(args.get("subject")) if args.get("subject") else None
            chapter = str(args.get("chapter")) if args.get("chapter") is not None else None
            top_k = min(5, max(1, int(args.get("top_k", 3))))
            return await self._search_textbook(query, class_level, medium, subject, chapter, top_k)

        elif name == "get_page":
            subject = normalize_subject_name(args.get("subject"))
            printed_page = int(args.get("printed_page", 0))
            return await self._get_page(class_level, medium, subject, printed_page)

        elif name == "get_concepts":
            concept_or_topic = str(args.get("concept_or_topic", ""))
            return await self._get_concepts(class_level, medium, concept_or_topic)

        return {"error": f"Unknown tool '{name}'"}

    async def _list_available_books(self) -> dict[str, Any]:
        """Return catalog of available books in ThinkBuddy library with retrievable content."""
        stmt = (
            select(Book, func.count(Chunk.id).label("chunk_count"))
            .outerjoin(Chunk, Chunk.book_id == Book.id)
            .where(
                Book.title != "General Science",
                Book.title != "সাধারণ বিজ্ঞান (Science)",
                ~Book.edition.like("ed_%"),
            )
            .options(selectinload(Book.chapters))
            .group_by(Book.id)
            .having(func.count(Chunk.id) > 0)
            .order_by(Book.class_level.asc(), Book.subject.asc())
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        catalog = []
        book_names = []
        for b, chunk_count in rows:
            catalog.append({
                "class_level": b.class_level,
                "subject": b.subject,
                "title": b.title,
                "total_chapters": len(b.chapters),
                "chunks_count": chunk_count,
            })
            book_names.append(f"Class {b.class_level} {b.subject.title()} ({b.title})")

        return {
            "total_books": len(catalog),
            "available_books": catalog,
            "library_coverage_summary": (
                f"ThinkBuddy library currently has {len(catalog)} authoritative NCTB curriculum textbooks with loaded content: "
                + ", ".join(book_names)
                + "."
            ),
        }

    async def _get_exercise_question(
        self,
        class_level: int,
        subject: str,
        medium: str,
        chapter: str | None,
        exercise_label: str | None,
        question_no: int,
        subpart: str | None,
    ) -> dict[str, Any]:
        """Fetch exact exercise question from exercise_items table."""
        # 1. Check if the book exists in the library
        stmt_book = select(Book).where(Book.class_level == class_level, Book.subject == subject)
        res_book = await self.db.execute(stmt_book)
        book = res_book.scalar_one_or_none()
        if not book:
            return {
                "found": False,
                "reason": "not_in_library",
                "class_level": class_level,
                "subject": subject,
                "message": f"Class {class_level} {subject} বই এখনো আমার লাইব্রেরিতে নেই।",
            }

        # 2. Query exercise_items
        stmt = (
            select(ExerciseItem, Chapter, Book)
            .join(Chapter, ExerciseItem.chapter_id == Chapter.id)
            .join(Book, ExerciseItem.book_id == Book.id)
            .where(
                Book.class_level == class_level,
                Book.subject == subject,
                ExerciseItem.question_no == question_no,
            )
        )
        if subpart:
            stmt = stmt.where(ExerciseItem.subpart == subpart)
        if chapter:
            try:
                ch_num = int(chapter)
                stmt = stmt.where(Chapter.number == ch_num)
            except ValueError:
                stmt = stmt.where(Chapter.title.ilike(f"%{chapter}%"))
        if exercise_label:
            stmt = stmt.where(ExerciseItem.exercise_label.ilike(f"%{exercise_label}%"))

        res = await self.db.execute(stmt)
        rows = res.all()

        # Fallback: if not found with exercise_label, try matching by chapter if available
        if not rows and chapter:
            stmt_fallback = (
                select(ExerciseItem, Chapter, Book)
                .join(Chapter, ExerciseItem.chapter_id == Chapter.id)
                .join(Book, ExerciseItem.book_id == Book.id)
                .where(
                    Book.class_level == class_level,
                    Book.subject == subject,
                    ExerciseItem.question_no == question_no,
                )
            )
            try:
                ch_num = int(chapter)
                stmt_fallback = stmt_fallback.where(Chapter.number == ch_num)
                res_fb = await self.db.execute(stmt_fallback)
                rows = res_fb.all()
            except ValueError:
                pass

        if not rows:
            # Fallback: Search chunk text for the exercise item in the target chapter/book
            bn_to_ascii = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
            ascii_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
            bn_q = str(question_no).translate(ascii_to_bn)

            # 1. Resolve chapter number
            ch_num = None
            if chapter:
                try:
                    ch_num = int(chapter)
                except ValueError:
                    pass
            elif exercise_label:
                m = re.search(r"(\d+)(?:\.\d+)?", exercise_label.translate(bn_to_ascii))
                if m:
                    ch_num = int(m.group(1))

            stmt_chunks = (
                select(Chunk, Chapter, Book)
                .join(Chapter, Chunk.chapter_id == Chapter.id)
                .join(Book, Chunk.book_id == Book.id)
                .where(
                    Book.class_level == class_level,
                    Book.subject == subject,
                    Chunk.retrievable == True,
                )
            )
            if ch_num is not None:
                stmt_chunks = stmt_chunks.where(Chapter.number == ch_num)
            elif chapter:
                stmt_chunks = stmt_chunks.where(Chapter.title.ilike(f"%{chapter}%"))

            stmt_chunks = stmt_chunks.order_by(Chunk.printed_page)
            res_chunks = await self.db.execute(stmt_chunks)
            all_chunks = res_chunks.all()

            if all_chunks:
                # Find candidate exercise pages
                target_start_page = None
                target_end_page = None

                if exercise_label:
                    clean_lbl = exercise_label.translate(bn_to_ascii).lower()
                    ex_num_match = re.search(r"(\d+(?:\.\d+)?)", clean_lbl)
                    target_ex_num = ex_num_match.group(1) if ex_num_match else None
                    for idx, (c, ch, b) in enumerate(all_chunks):
                        text_ascii = c.text.translate(bn_to_ascii)
                        found_exs = re.findall(r"(?:অনুশীলনী|exercise)\s*(\d+(?:\.\d+)?)", text_ascii, re.IGNORECASE)
                        if target_ex_num and target_ex_num in found_exs:
                            target_start_page = c.printed_page
                            for next_c, _, _ in all_chunks[idx + 1:]:
                                next_text_ascii = next_c.text.translate(bn_to_ascii)
                                next_exs = re.findall(r"(?:অনুশীলনী|exercise)\s*(\d+(?:\.\d+)?)", next_text_ascii, re.IGNORECASE)
                                if next_exs and any(e != target_ex_num for e in next_exs):
                                    target_end_page = next_c.printed_page - 1
                                    break
                            break

                if target_start_page is None:
                    for c, ch, b in all_chunks:
                        if re.search(r"(?:অনুশীলনী|exercise)", c.text, re.IGNORECASE):
                            target_start_page = c.printed_page
                            break

                candidate_chunks = []
                if target_start_page is not None:
                    end_p = target_end_page or all_chunks[-1][0].printed_page
                    candidate_chunks = [
                        (c, ch, b) for c, ch, b in all_chunks
                        if target_start_page <= c.printed_page <= end_p
                    ]
                else:
                    candidate_chunks = all_chunks

                best_hit = None
                best_snippet = ""
                best_score = -1

                pats = [
                    rf"(?:^|\s|[।|!|;|\(]){bn_q}\s*(?:[\.।\:\-\!|I]|নং|নম্বর|\b)",
                    rf"(?:^|\s|[।|!|;|\(]){question_no}\s*(?:[\.।\:\-\!|I]|no|number|\b)",
                ]

                for c, ch, b in candidate_chunks:
                    c_text = c.text
                    for pat in pats:
                        m = re.search(pat, c_text)
                        if m:
                            start_pos = max(0, m.start() - 20)
                            end_pos = min(len(c_text), m.end() + 250)
                            snippet = c_text[start_pos:end_pos].strip()
                            score = 100
                            if re.search(rf"{bn_q}\s*[\.।\:\-\!|I]", snippet) or re.search(rf"{question_no}\s*[\.।\:\-\!|I]", snippet):
                                score += 50
                            if "নম্বর" in snippet or "নং" in snippet or "অনুশীলনী" in snippet:
                                score += 20
                            if score > best_score:
                                best_score = score
                                best_hit = (c, ch, b)
                                best_snippet = snippet

                if best_hit:
                    c, ch, b = best_hit
                    ex_label_final = exercise_label or f"অনুশীলনী {ch.number}"
                    self.used_citations.append({
                        "chunk_id": str(c.id),
                        "book_title": b.title,
                        "chapter_title": f"{ex_label_final} (প্রশ্ন {question_no}{f' {subpart}' if subpart else ''})",
                        "chapter_number": ch.number,
                        "printed_page": c.printed_page,
                        "score": 1.0,
                    })
                    return {
                        "found": True,
                        "book_title": b.title,
                        "chapter_title": ch.title,
                        "exercise_label": ex_label_final,
                        "question_no": question_no,
                        "subpart": subpart or "",
                        "question_text": best_snippet,
                        "printed_page": c.printed_page,
                        "raw_chunk_text": c.text,
                    }

            return {
                "found": False,
                "reason": "question_not_found",
                "class_level": class_level,
                "subject": subject,
                "question_no": question_no,
                "message": f"অনুশীলনীর {question_no} নম্বর প্রশ্নটি সরাসরি পাওয়া যায়নি।",
            }

        from core.chat.exercise_safety import resolve_exercise_candidates

        # Extract items for safety gate check
        items_payload = [
            {
                "id": str(r[0].id),
                "exercise_label": r[0].exercise_label,
                "question_no": r[0].question_no,
                "subpart": r[0].subpart,
                "question_text": r[0].question_text,
                "printed_page": r[0].printed_page,
                "chapter_number": r[1].number,
                "chapter_title": r[1].title,
                "book_title": r[2].title,
            }
            for r in rows
        ]

        resolution = resolve_exercise_candidates(items_payload, exercise_label, question_no)

        if resolution["status"] == "ambiguous":
            return {
                "found": False,
                "disambiguate": True,
                "matching_exercises": resolution.get("distinct_labels", []),
                "candidates": resolution["candidates"],
                "message": resolution["message"],
            }

        if resolution["status"] == "not_found":
            return {
                "found": False,
                "reason": "question_not_found",
                "class_level": class_level,
                "subject": subject,
                "question_no": question_no,
                "message": resolution["message"],
            }

        ex_item, ch, b = rows[0]
        # Register authoritative citation
        self.used_citations.append({
            "chunk_id": str(ex_item.id),
            "book_title": b.title,
            "chapter_title": f"{ex_item.exercise_label} (প্রশ্ন {ex_item.question_no}{f' {ex_item.subpart}' if ex_item.subpart else ''})",
            "chapter_number": ch.number,
            "printed_page": ex_item.printed_page,
            "score": 1.0,
        })

        return {
            "found": True,
            "book_title": b.title,
            "chapter_title": ch.title,
            "exercise_label": ex_item.exercise_label,
            "question_no": ex_item.question_no,
            "subpart": ex_item.subpart,
            "question_text": ex_item.question_text,
            "printed_page": ex_item.printed_page,
            "answer_key": ex_item.answer_key,
        }

    async def _get_chapter_list(
        self, class_level: int, subject: str, medium: str
    ) -> dict[str, Any]:
        """Fetch ordered chapter list for the student's class textbook."""
        stmt = (
            select(Book)
            .where(
                Book.class_level == class_level,
                Book.subject == subject,
                Book.medium == medium,
            )
            .options(selectinload(Book.chapters))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        book = res.scalar_one_or_none()

        if not book:
            stmt_alt = (
                select(Book)
                .where(Book.class_level == class_level, Book.subject == subject)
                .options(selectinload(Book.chapters))
                .limit(1)
            )
            res_alt = await self.db.execute(stmt_alt)
            book = res_alt.scalar_one_or_none()

        if not book or not book.chapters:
            return {
                "class_level": class_level,
                "subject": subject,
                "total_chapters": 0,
                "chapters": [],
                "message": f"No indexed textbook found for Class {class_level} {subject}.",
            }

        sorted_chapters = sorted(book.chapters, key=lambda c: (c.order_index, c.number))
        return {
            "class_level": class_level,
            "book_title": book.title,
            "subject": subject,
            "total_chapters": len(sorted_chapters),
            "last_chapter": {
                "number": sorted_chapters[-1].number,
                "title": sorted_chapters[-1].title,
                "printed_page_start": sorted_chapters[-1].printed_page_start,
                "printed_page_end": sorted_chapters[-1].printed_page_end,
                "is_last_chapter": True,
            },
            "chapters": [
                {
                    "number": ch.number,
                    "title": ch.title,
                    "printed_page_start": ch.printed_page_start,
                    "printed_page_end": ch.printed_page_end,
                    "order_index": ch.order_index,
                }
                for ch in sorted_chapters
            ],
        }

    async def _search_textbook(
        self,
        query: str,
        class_level: int,
        medium: str,
        subject: str | None,
        chapter: str | None,
        top_k: int,
    ) -> dict[str, Any]:
        """Search textbook chunks with metadata scoping."""
        from core.common.config import settings
        from rag.embedding import get_embedding_provider
        from rag.vector_store import PgVectorStore

        store = PgVectorStore(self.db)
        chapter_number: int | None = None
        if chapter:
            try:
                chapter_number = int(chapter)
            except ValueError:
                pass

        filters: dict[str, Any] = {
            "class_level": class_level,
        }
        if subject:
            filters["subject"] = subject
        if chapter_number:
            filters["chapter_number"] = chapter_number

        # If embedding provider cannot load or is mock outside tests, fail loudly
        if settings.EMBEDDING_PROVIDER.lower() in ("mock", "test"):
            if getattr(settings, "ENVIRONMENT", "development") not in ("test", "development") and os.getenv("TESTING") != "true":
                logger.critical("Mock embeddings are strictly forbidden in production. Vector search disabled.")
                return {
                    "found": False,
                    "status": "error",
                    "error": "Mock embeddings forbidden in production.",
                    "message": "পাঠ্যবই অনুসন্ধানে কারিগরি ত্রুটি হয়েছে। বইটি সরাসরি যাচাই করা সম্ভব হয়নি।",
                }

        try:
            provider = get_embedding_provider()
            query_vector = await provider.embed_query(query)
            hits = await store.search_hybrid(
                query_text=query,
                query_vector=query_vector,
                limit=top_k,
                filters=filters,
            )
        except Exception as ex:
            logger.critical("Embedding model or vector retrieval failed: %s. Never falling back to mock.", ex, exc_info=True)
            return {
                "found": False,
                "status": "error",
                "error": f"Vector search failure: {str(ex)}",
                "message": "পাঠ্যবই অনুসন্ধানে কারিগরি ত্রুটি হয়েছে। বইটি সরাসরি যাচাই করা সম্ভব হয়নি।",
            }

        results = []
        for h in hits:
            self.used_citations.append({
                "chunk_id": str(h.chunk_id),
                "book_title": h.book_title,
                "chapter_title": h.chapter_title,
                "chapter_number": h.chapter_number,
                "printed_page": h.printed_page,
                "score": round(float(h.score), 4),
            })
            results.append({
                "book_title": h.book_title,
                "chapter_title": h.chapter_title,
                "printed_page": h.printed_page,
                "text": getattr(h, "text", getattr(h, "snippet", "")),
                "score": round(float(h.score), 4),
            })

        return {
            "found": len(results) > 0,
            "query": query,
            "class_level": class_level,
            "subject": subject,
            "total_matches": len(results),
            "passages": results,
        }

    async def _get_page(
        self, class_level: int, medium: str, subject: str, printed_page: int
    ) -> dict[str, Any]:
        """Retrieve chunk text by exact printed page number."""
        stmt = (
            select(Chunk, Chapter, Book)
            .join(Chapter, Chunk.chapter_id == Chapter.id)
            .join(Book, Chunk.book_id == Book.id)
            .where(
                Book.class_level == class_level,
                Book.subject == subject,
                Chunk.printed_page == printed_page,
            )
            .limit(1)
        )
        res = await self.db.execute(stmt)
        row = res.first()

        if not row:
            return {
                "class_level": class_level,
                "subject": subject,
                "printed_page": printed_page,
                "found": False,
                "message": f"Page {printed_page} not found in Class {class_level} {subject}.",
            }

        chunk, chapter, book = row
        self.used_citations.append({
            "chunk_id": str(chunk.id),
            "book_title": book.title,
            "chapter_title": chapter.title,
            "chapter_number": chapter.number,
            "printed_page": chunk.printed_page,
            "score": 1.0,
        })

        return {
            "class_level": class_level,
            "book_title": book.title,
            "chapter_title": chapter.title,
            "printed_page": chunk.printed_page,
            "found": True,
            "text": chunk.text,
        }

    async def _get_concepts(
        self, class_level: int, medium: str, concept_or_topic: str
    ) -> dict[str, Any]:
        """Retrieve concept definitions and guided answer hints."""
        stmt = (
            select(Concept, Chapter, Book)
            .join(Chapter, Concept.chapter_id == Chapter.id)
            .join(Book, Chapter.book_id == Book.id)
            .where(
                Book.class_level == class_level,
                Concept.title.ilike(f"%{concept_or_topic}%"),
            )
            .limit(3)
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        results = []
        for c, ch, b in rows:
            results.append({
                "concept": c.title,
                "kind": c.kind,
                "chapter_title": ch.title,
                "book_title": b.title,
            })

        return {
            "concept_or_topic": concept_or_topic,
            "class_level": class_level,
            "matches": results,
        }
