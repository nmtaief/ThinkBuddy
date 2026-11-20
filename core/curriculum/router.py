"""API routes for curriculum module: textbooks, chapters, and educational concepts."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.database import get_db_session
from core.curriculum.models import Book, Chapter, Chunk
from core.curriculum.schemas import (
    BookListResponse,
    BookSummary,
    ChapterDetailResponse,
    ChapterListResponse,
    ChapterSummary,
    ConceptSummary,
)

router = APIRouter(prefix="", tags=["Curriculum"])


@router.get("/books", response_model=BookListResponse)
async def list_books(
    class_level: int | None = Query(default=None, description="Class level filter (e.g. 6, 7, 8)"),
    subject: str | None = Query(default=None, description="Subject filter (e.g. math, science)"),
    medium: str | None = Query(default=None, description="Medium of instruction ('bn', 'en')"),
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> BookListResponse:
    """Retrieve list of curriculum textbooks filtered by class, subject, and medium."""
    stmt = (
        select(Book, func.count(Chapter.id).label("chapters_count"))
        .outerjoin(Chapter, Chapter.book_id == Book.id)
        .group_by(Book.id)
        .order_by(Book.class_level.asc(), Book.subject.asc())
    )

    if class_level is not None:
        stmt = stmt.where(Book.class_level == class_level)
    if subject is not None:
        stmt = stmt.where(Book.subject == subject.lower())
    if medium is not None:
        stmt = stmt.where(Book.medium == medium.lower())

    result = await db.execute(stmt)
    rows = result.fetchall()

    items = [
        BookSummary(
            id=book.id,
            title=book.title,
            class_level=book.class_level,
            subject=book.subject,
            medium=book.medium,
            edition=book.edition,
            chapters_count=count,
        )
        for book, count in rows
    ]

    return BookListResponse(items=items, total=len(items))


@router.get("/books/{book_id}", response_model=BookSummary)
async def get_book(
    book_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> BookSummary:
    """Get metadata for a specific curriculum textbook."""
    stmt = (
        select(Book, func.count(Chapter.id).label("chapters_count"))
        .outerjoin(Chapter, Chapter.book_id == Book.id)
        .where(Book.id == book_id)
        .group_by(Book.id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BOOK_NOT_FOUND", "message": "Textbook not found."},
        )

    book, count = row
    return BookSummary(
        id=book.id,
        title=book.title,
        class_level=book.class_level,
        subject=book.subject,
        medium=book.medium,
        edition=book.edition,
        chapters_count=count,
    )


@router.get("/books/{book_id}/chapters", response_model=ChapterListResponse)
async def get_book_chapters(
    book_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ChapterListResponse:
    """Get ordered list of chapters for a given curriculum textbook."""
    # Ensure book exists
    stmt_book = select(Book.id).where(Book.id == book_id)
    res_book = await db.execute(stmt_book)
    if not res_book.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BOOK_NOT_FOUND", "message": "Textbook not found."},
        )

    stmt_ch = (
        select(Chapter)
        .where(Chapter.book_id == book_id)
        .order_by(Chapter.order_index.asc(), Chapter.number.asc())
    )
    res_ch = await db.execute(stmt_ch)
    chapters = res_ch.scalars().all()

    items = [
        ChapterSummary(
            id=ch.id,
            book_id=ch.book_id,
            number=ch.number,
            title=ch.title,
            printed_page_start=ch.printed_page_start,
            printed_page_end=ch.printed_page_end,
            order_index=ch.order_index,
        )
        for ch in chapters
    ]

    return ChapterListResponse(items=items, total=len(items))


@router.get("/chapters/{chapter_id}", response_model=ChapterDetailResponse)
async def get_chapter_detail(
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ChapterDetailResponse:
    """Get chapter details including educational concepts and chunk counts."""
    stmt_ch = (
        select(Chapter)
        .options(selectinload(Chapter.book), selectinload(Chapter.concepts))
        .where(Chapter.id == chapter_id)
    )
    res_ch = await db.execute(stmt_ch)
    chapter = res_ch.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CHAPTER_NOT_FOUND", "message": "Chapter not found."},
        )

    # Count chunks in chapter
    stmt_chunk_count = select(func.count(Chunk.id)).where(Chunk.chapter_id == chapter_id)
    res_count = await db.execute(stmt_chunk_count)
    chunks_count = res_count.scalar_one() or 0

    concepts_list = [
        ConceptSummary(
            id=c.id,
            chapter_id=c.chapter_id,
            title=c.title,
            kind=c.kind,
        )
        for c in chapter.concepts
    ]

    return ChapterDetailResponse(
        id=chapter.id,
        book_id=chapter.book_id,
        book_title=chapter.book.title,
        number=chapter.number,
        title=chapter.title,
        printed_page_start=chapter.printed_page_start,
        printed_page_end=chapter.printed_page_end,
        order_index=chapter.order_index,
        concepts=concepts_list,
        chunks_count=chunks_count,
    )


@router.get("/curriculum/subjects")
async def get_curriculum_subjects(
    class_level: int = Query(default=8, ge=6, le=10, description="Class level (6-10)"),
    group: str = Query(default="general", description="Group (general, science, humanities, business_studies)"),
) -> list[dict[str, Any]]:
    """Retrieve official NCTB subjects catalog with metadata for class and group."""
    from core.curriculum.nctb_subjects import get_subjects_for_class_and_group

    subjects = get_subjects_for_class_and_group(class_level, group)
    return [
        {
            "slug": s.slug,
            "name_bn": s.name_bn,
            "name_en": s.name_en,
            "class_level": s.class_level,
            "group": s.group,
            "total_chapters": s.total_chapters,
            "base_difficulty": s.base_difficulty,
            "is_stem": s.is_stem,
            "recommended_min_weekly_minutes": s.recommended_min_weekly_minutes,
            "chapters": [
                {
                    "number": ch.number,
                    "title_bn": ch.title_bn,
                    "title_en": ch.title_en,
                    "estimated_study_hours": ch.estimated_study_hours,
                    "is_hard": ch.is_hard,
                }
                for ch in s.chapters
            ],
        }
        for s in subjects
    ]
