"""Curriculum and content ingestion pipeline.

Reads validated Knowledge Factory JSONL manifest files, validates quality, generates
multilingual embeddings, computes full-text tsvector indexes, and persists into Postgres.

Features:
- Idempotent: re-running does not duplicate chunks
- Resumable: tracks already ingested chunks per book/page; recovers seamlessly after interruptions
- Quality-gated: chunks failing validation are saved with retrievable=False and rejection reasons
- Batch-tracked: records stats and execution status in ingest_batches table
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from core.common.database import AsyncSessionLocal
from core.curriculum.models import Book, Chapter, Chunk, Concept, IngestBatch
from rag.embedding import EmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)

REJECTION_FLAGS = {"corrupted_ocr", "truncated", "profanity", "unreadable"}


@dataclass
class IngestResult:
    batch_id: uuid.UUID
    book_id: uuid.UUID
    total_manifest_chunks: int
    newly_ingested: int
    already_existing: int
    unretrievable_chunks: int
    status: str


class CurriculumImporter:
    """Imports Knowledge Factory JSONL manifest into PostgreSQL + pgvector storage."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        min_ocr_quality: float = 0.70,
    ) -> None:
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.min_ocr_quality = min_ocr_quality

    async def import_manifest(
        self,
        manifest_path: str | Path,
        batch_id: uuid.UUID | None = None,
        resume: bool = True,
    ) -> IngestResult:
        """Parse and import a Knowledge Factory JSONL manifest file."""
        path = Path(manifest_path)
        if not path.is_file():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        lines = [
            line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        if not lines:
            raise ValueError(f"Manifest file is empty: {manifest_path}")

        # Record 1 must be book definition
        header_data = json.loads(lines[0])
        if header_data.get("type") != "book":
            raise ValueError("First line of manifest must be of type 'book'")

        book_info = header_data["book"]
        chapters_info = header_data.get("chapters", [])
        concepts_info = header_data.get("concepts", [])

        # Parse chunk lines
        chunk_lines = [
            json.loads(line) for line in lines[1:] if json.loads(line).get("type") == "chunk"
        ]

        async with AsyncSessionLocal() as session:
            # 1. Upsert Book record
            book_id = uuid.UUID(str(book_info["id"]))
            stmt_book = select(Book).where(Book.id == book_id)
            res_book = await session.execute(stmt_book)
            existing_book = res_book.scalar_one_or_none()

            if not existing_book:
                book = Book(
                    id=book_id,
                    title=book_info["title"],
                    class_level=int(book_info["class_level"]),
                    subject=book_info["subject"],
                    medium=book_info.get("medium", "bn"),
                    edition=str(book_info.get("edition", "2024")),
                    source_uri=book_info.get("source_uri"),
                )
                session.add(book)
            else:
                existing_book.title = book_info["title"]
                existing_book.class_level = int(book_info["class_level"])
                existing_book.subject = book_info["subject"]
                existing_book.medium = book_info.get("medium", "bn")
                existing_book.edition = str(book_info.get("edition", "2024"))
                existing_book.source_uri = book_info.get("source_uri")

            await session.flush()

            # 2. Upsert Chapters
            for ch in chapters_info:
                ch_id = uuid.UUID(str(ch["id"]))
                stmt_ch = select(Chapter).where(Chapter.id == ch_id)
                res_ch = await session.execute(stmt_ch)
                existing_ch = res_ch.scalar_one_or_none()

                if not existing_ch:
                    chapter = Chapter(
                        id=ch_id,
                        book_id=book_id,
                        number=int(ch["number"]),
                        title=ch["title"],
                        printed_page_start=int(ch["printed_page_start"]),
                        printed_page_end=int(ch["printed_page_end"]),
                        order_index=int(ch.get("order_index", ch["number"])),
                    )
                    session.add(chapter)
                else:
                    existing_ch.number = int(ch["number"])
                    existing_ch.title = ch["title"]
                    existing_ch.printed_page_start = int(ch["printed_page_start"])
                    existing_ch.printed_page_end = int(ch["printed_page_end"])
                    existing_ch.order_index = int(ch.get("order_index", ch["number"]))

            await session.flush()

            # 3. Upsert Concepts
            for cp in concepts_info:
                cp_id = uuid.UUID(str(cp["id"]))
                stmt_cp = select(Concept).where(Concept.id == cp_id)
                res_cp = await session.execute(stmt_cp)
                existing_cp = res_cp.scalar_one_or_none()

                if not existing_cp:
                    concept = Concept(
                        id=cp_id,
                        chapter_id=uuid.UUID(str(cp["chapter_id"])),
                        title=cp["title"],
                        kind=cp.get("kind", "concept"),
                    )
                    session.add(concept)

            await session.flush()

            # 4. Ingest Batch tracking
            actual_batch_id = batch_id or uuid.uuid4()
            stmt_batch = select(IngestBatch).where(IngestBatch.id == actual_batch_id)
            res_batch = await session.execute(stmt_batch)
            batch = res_batch.scalar_one_or_none()

            if not batch:
                batch = IngestBatch(
                    id=actual_batch_id,
                    source_manifest=str(path),
                    status="in_progress",
                    stats={
                        "total_chunks": len(chunk_lines),
                        "ingested_chunks": 0,
                        "skipped_chunks": 0,
                        "unretrievable_chunks": 0,
                    },
                )
                session.add(batch)
            else:
                batch.status = "resumed"

            await session.commit()

            # 5. Check already ingested chunks if resuming
            already_imported_indices: set[int] = set()
            if resume:
                stmt_existing = select(Chunk.chunk_index).where(Chunk.book_id == book_id)
                res_existing = await session.execute(stmt_existing)
                already_imported_indices = {row[0] for row in res_existing.fetchall()}

            newly_ingested = 0
            already_existing = 0
            unretrievable = 0

            # 6. Process chunks in pages / batches
            pending_records: list[dict[str, Any]] = []

            for item in chunk_lines:
                idx = int(item["chunk_index"])
                if idx in already_imported_indices:
                    already_existing += 1
                    continue

                # Validate quality and flags
                flags: list[str] = list(item.get("validation_flags", []))
                ocr_q = float(item.get("ocr_quality", 1.0))
                retrievable = True

                if ocr_q < self.min_ocr_quality:
                    flags.append("low_ocr_quality")
                    retrievable = False

                if any(f in REJECTION_FLAGS for f in flags):
                    retrievable = False

                if not retrievable:
                    unretrievable += 1

                pending_records.append(
                    {
                        "id": uuid.UUID(str(item.get("id", uuid.uuid4()))),
                        "book_id": book_id,
                        "chapter_id": uuid.UUID(str(item["chapter_id"])),
                        "concept_id": uuid.UUID(str(item["concept_id"]))
                        if item.get("concept_id")
                        else None,
                        "ingest_batch_id": actual_batch_id,
                        "chunk_index": idx,
                        "text": item["text"].strip(),
                        "text_original": item.get("text_original"),
                        "language": item.get("language", "bn"),
                        "printed_page": int(item["printed_page"]),
                        "pdf_page_index": int(item["pdf_page_index"]),
                        "ocr_quality": ocr_q,
                        "validation_flags": flags,
                        "retrievable": retrievable,
                        "embedding_model": self.embedding_provider.model_name,
                    }
                )

            # 7. Generate embeddings in batches for new chunks
            if pending_records:
                texts_to_embed = [r["text"] for r in pending_records]
                embeddings = await self.embedding_provider.embed_documents(texts_to_embed)

                for r, emb in zip(pending_records, embeddings, strict=True):
                    r["embedding"] = emb

                # 8. Persist chunks in database (with idempotent upsert on conflict)
                for rec in pending_records:
                    stmt_insert = (
                        insert(Chunk)
                        .values(
                            id=rec["id"],
                            book_id=rec["book_id"],
                            chapter_id=rec["chapter_id"],
                            concept_id=rec["concept_id"],
                            ingest_batch_id=rec["ingest_batch_id"],
                            chunk_index=rec["chunk_index"],
                            text=rec["text"],
                            text_original=rec["text_original"],
                            language=rec["language"],
                            printed_page=rec["printed_page"],
                            pdf_page_index=rec["pdf_page_index"],
                            ocr_quality=rec["ocr_quality"],
                            validation_flags=rec["validation_flags"],
                            retrievable=rec["retrievable"],
                            embedding_model=rec["embedding_model"],
                            embedding=rec["embedding"],
                            tsv=func.to_tsvector("simple", rec["text"]),
                        )
                        .on_conflict_do_update(
                            constraint="uq_chunks_book_chunk_index",
                            set_={
                                "text": rec["text"],
                                "printed_page": rec["printed_page"],
                                "pdf_page_index": rec["pdf_page_index"],
                                "ocr_quality": rec["ocr_quality"],
                                "validation_flags": rec["validation_flags"],
                                "retrievable": rec["retrievable"],
                                "embedding": rec["embedding"],
                                "tsv": func.to_tsvector("simple", rec["text"]),
                            },
                        )
                    )
                    await session.execute(stmt_insert)
                    newly_ingested += 1

            # 9. Update IngestBatch record to completed
            stmt_update_batch = select(IngestBatch).where(IngestBatch.id == actual_batch_id)
            res_final = await session.execute(stmt_update_batch)
            final_batch = res_final.scalar_one()

            final_batch.status = "completed"
            final_batch.stats = {
                "total_chunks": len(chunk_lines),
                "ingested_chunks": newly_ingested,
                "already_existing": already_existing,
                "unretrievable_chunks": unretrievable,
            }
            await session.commit()

            logger.info(
                "Ingestion completed for book %s: %d newly ingested, %d skipped, %d unretrievable",
                book_id,
                newly_ingested,
                already_existing,
                unretrievable,
            )

            return IngestResult(
                batch_id=actual_batch_id,
                book_id=book_id,
                total_manifest_chunks=len(chunk_lines),
                newly_ingested=newly_ingested,
                already_existing=already_existing,
                unretrievable_chunks=unretrievable,
                status="completed",
            )
