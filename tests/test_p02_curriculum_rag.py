"""Acceptance and integration tests for P02: Curriculum & Ingestion (Knowledge Factory -> DB).

Verifies:
1. Manifest ingestion into real Postgres + pgvector database
2. Idempotency: re-running manifest import does not duplicate chunks
3. Resumability: interrupted ingestion resumes seamlessly without orphaned records
4. Quality gating: chunks failing validation or low OCR quality are saved as retrievable=False
   and excluded from hybrid search
5. Strict separation of printed_page and pdf_page_index (Rule 8)
6. Hybrid vector + lexical retrieval for Bangla and English
7. Curriculum read endpoints (/v1/books, /v1/books/{id}, /v1/books/{id}/chapters, /v1/chapters/{id})
8. Retrieval evaluation harness with threshold gate for CI
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from core.common.database import AsyncSessionLocal
from core.curriculum.models import Chunk
from rag.embedding import get_embedding_provider
from rag.ingest import CurriculumImporter
from rag.vector_store import PgVectorStore
from scripts.eval_retrieval import run_evaluation

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-curriculum-001",
    "Accept-Language": "bn",
}

SAMPLE_MANIFEST_PATH = Path("tests/data/sample_manifest.jsonl")
EVAL_DATASET_PATH = Path("tests/data/retrieval_eval_dataset.json")


@pytest.fixture(autouse=True)
async def setup_curriculum_data() -> None:
    """Ensure sample textbook curriculum is ingested before tests run."""
    importer = CurriculumImporter()
    await importer.import_manifest(SAMPLE_MANIFEST_PATH, resume=True)


# =============================================================================
# 1. Ingestion & Idempotency Tests
# =============================================================================
@pytest.mark.asyncio
async def test_idempotent_import_does_not_duplicate_chunks() -> None:
    """Verify that re-importing the same manifest does not duplicate books or chunks."""
    async with AsyncSessionLocal() as session:
        # Count chunks initially
        stmt_count = select(func.count(Chunk.id))
        res_initial = await session.execute(stmt_count)
        initial_chunk_count = res_initial.scalar_one()
        assert initial_chunk_count == 8

    # Re-run import of the exact same manifest
    importer = CurriculumImporter()
    res = await importer.import_manifest(SAMPLE_MANIFEST_PATH, resume=True)

    # All 8 chunks should be recognized as existing, 0 newly ingested
    assert res.already_existing == 8
    assert res.newly_ingested == 0
    assert res.status == "completed"

    async with AsyncSessionLocal() as session:
        res_after = await session.execute(stmt_count)
        after_chunk_count = res_after.scalar_one()
        assert after_chunk_count == initial_chunk_count


@pytest.mark.asyncio
async def test_importer_resumes_after_interruption(tmp_path: Path) -> None:
    """Verify that if an ingestion job terminates halfway, restarting resumes correctly."""
    # Create partial manifest with 2 chunks
    book_id = uuid.uuid4()
    ch_id = uuid.uuid4()
    partial_manifest = tmp_path / "partial_manifest.jsonl"

    header = {
        "type": "book",
        "book": {
            "id": str(book_id),
            "title": "বিজ্ঞানী ভাবনা",
            "class_level": 8,
            "subject": "science",
            "medium": "bn",
            "edition": "2024",
        },
        "chapters": [
            {
                "id": str(ch_id),
                "number": 1,
                "title": "মহাকর্ষ ও অভিকর্ষ",
                "printed_page_start": 1,
                "printed_page_end": 15,
                "order_index": 1,
            }
        ],
    }
    chunk1 = {
        "type": "chunk",
        "id": str(uuid.uuid4()),
        "book_id": str(book_id),
        "chapter_id": str(ch_id),
        "chunk_index": 1,
        "text": "মহাবিশ্বের প্রতিটি বস্তু একে অপরকে নিজের দিকে আকর্ষণ করে। এই আকর্ষণ বলকে মহাকর্ষ বল বলে।",
        "printed_page": 2,
        "pdf_page_index": 4,
        "ocr_quality": 0.99,
        "validation_flags": ["clean"],
    }
    chunk2 = {
        "type": "chunk",
        "id": str(uuid.uuid4()),
        "book_id": str(book_id),
        "chapter_id": str(ch_id),
        "chunk_index": 2,
        "text": "নিউটনের মহাকর্ষ সূত্রানুসারে দুটি বস্তুর মধ্যবর্তী আকর্ষণ বল তাদের ভরের গুণফলের সমানুপাতিক।",
        "printed_page": 3,
        "pdf_page_index": 5,
        "ocr_quality": 0.98,
        "validation_flags": ["clean"],
    }
    chunk3 = {
        "type": "chunk",
        "id": str(uuid.uuid4()),
        "book_id": str(book_id),
        "chapter_id": str(ch_id),
        "chunk_index": 3,
        "text": "অভিকর্ষজ ত্বরণ g এর মান ভূপৃষ্ঠে আদর্শ মান হিসেবে ৯.৮ মিটার/সেকেন্ড^২ ধরা হয়।",
        "printed_page": 5,
        "pdf_page_index": 7,
        "ocr_quality": 0.97,
        "validation_flags": ["clean"],
    }

    # Step 1: Simulate first run interrupted after chunk 1 & 2
    partial_manifest.write_text(
        json.dumps(header) + "\n" + json.dumps(chunk1) + "\n" + json.dumps(chunk2) + "\n",
        encoding="utf-8",
    )
    importer = CurriculumImporter()
    res1 = await importer.import_manifest(partial_manifest, resume=True)
    assert res1.newly_ingested == 2

    # Step 2: Full manifest is run with chunk 3 added
    partial_manifest.write_text(
        json.dumps(header)
        + "\n"
        + json.dumps(chunk1)
        + "\n"
        + json.dumps(chunk2)
        + "\n"
        + json.dumps(chunk3)
        + "\n",
        encoding="utf-8",
    )
    res2 = await importer.import_manifest(partial_manifest, resume=True)
    assert res2.already_existing == 2
    assert res2.newly_ingested == 1
    assert res2.total_manifest_chunks == 3

    # Clean up test book
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM books WHERE id = :id"), {"id": str(book_id)})
        await session.commit()


# =============================================================================
# 2. Quality Gating & Exclusion Tests
# =============================================================================
@pytest.mark.asyncio
async def test_invalid_chunks_excluded_from_retrieval() -> None:
    """Verify low OCR quality or flagged chunks are retrievable=False and excluded from search."""
    async with AsyncSessionLocal() as session:
        # Check DB flags for chunk 7 (low OCR) and chunk 8 (truncated)
        res_chunks = await session.execute(
            select(Chunk.chunk_index, Chunk.retrievable, Chunk.validation_flags)
            .where(Chunk.chunk_index.in_([7, 8]))
            .order_by(Chunk.chunk_index)
        )
        rows = res_chunks.fetchall()
        assert len(rows) == 2
        for idx, retrievable, flags in rows:
            assert retrievable is False
            if idx == 7:
                assert "low_ocr_quality" in flags or "low_ocr" in flags
            if idx == 8:
                assert "truncated" in flags

        # Execute hybrid search over low-quality text -> must not retrieve unretrievable chunks
        store = PgVectorStore(session)
        provider = get_embedding_provider()
        vec = await provider.embed_query("নষ্ট এবং অস্পষ্ট টেক্সট")
        hits = await store.search_hybrid(
            query_text="নষ্ট এবং অস্পষ্ট টেক্সট",
            query_vector=vec,
            limit=5,
        )
        # None of the retrieved hits should be chunk 7 or 8
        stmt_bad = select(Chunk.id).where(Chunk.chunk_index.in_([7, 8]))
        bad_ids = set((await session.execute(stmt_bad)).scalars().all())
        for hit in hits:
            assert hit.chunk_id not in bad_ids


# =============================================================================
# 3. Printed Page vs PDF Index Separation Tests (Rule 8)
# =============================================================================
@pytest.mark.asyncio
async def test_printed_page_vs_pdf_page_index_separation() -> None:
    """Verify printed_page and pdf_page_index are separate columns and printed_page is returned."""
    async with AsyncSessionLocal() as session:
        stmt = select(Chunk).where(Chunk.chunk_index == 1)
        res = await session.execute(stmt)
        chunk = res.scalar_one()

        # In sample manifest: printed_page is 2, pdf_page_index is 4
        assert chunk.printed_page == 2
        assert chunk.pdf_page_index == 4
        assert chunk.printed_page != chunk.pdf_page_index

        # In search results, citation must contain printed_page
        store = PgVectorStore(session)
        provider = get_embedding_provider()
        vec = await provider.embed_query("বর্গ ও বর্গমূল")
        hits = await store.search_hybrid("বর্গ ও বর্গমূল", vec, limit=3)
        assert len(hits) > 0
        hit = next(h for h in hits if h.printed_page == 2)
        assert hit.printed_page == 2
        assert hit.pdf_page_index == 4


# =============================================================================
# 4. Hybrid Retrieval Accuracy Tests (Bangla & English)
# =============================================================================
@pytest.mark.asyncio
async def test_hybrid_retrieval_bangla_and_english() -> None:
    """Verify hybrid search returns relevant chunks with citations for BN and EN queries."""
    async with AsyncSessionLocal() as session:
        store = PgVectorStore(session)
        provider = get_embedding_provider()

        # 1. Bangla query: Algebraic formulas
        q_bn = "বীজগণিতীয় সূত্রাবলি (a + b)^2 এর বিস্তার"
        v_bn = await provider.embed_query(q_bn)
        hits_bn = await store.search_hybrid(q_bn, v_bn, limit=3)
        assert len(hits_bn) > 0
        top_bn = hits_bn[0]
        assert top_bn.chapter_number == 2
        assert top_bn.printed_page in (20, 24)
        assert top_bn.score > 0.0

        # 2. English query: Linear equations
        q_en = "How to solve linear equations in algebra?"
        v_en = await provider.embed_query(q_en)
        hits_en = await store.search_hybrid(q_en, v_en, limit=3)
        assert len(hits_en) > 0
        top_en = hits_en[0]
        assert top_en.chapter_number == 2
        assert top_en.printed_page == 28
        assert "linear equations" in top_en.text.lower()


# =============================================================================
# 5. Curriculum Read APIs Tests
# =============================================================================
@pytest.mark.asyncio
async def test_curriculum_read_apis(gateway_client: AsyncClient) -> None:
    """Verify /v1/books, /v1/books/{id}, /v1/books/{id}/chapters, /v1/chapters/{id}."""
    # 1. Authenticate user to obtain token
    phone = f"+880155{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_auth.status_code == 200
    token = res_auth.json()["access_token"]
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # 2. List books
    res_books = await gateway_client.get(
        "/v1/books?class_level=7&subject=math", headers=auth_headers
    )
    assert res_books.status_code == 200
    books_data = res_books.json()
    assert books_data["total"] >= 1
    book = books_data["items"][0]
    assert book["class_level"] == 7
    assert book["subject"] == "math"
    assert book["chapters_count"] == 2
    book_id = book["id"]

    # 3. Get book detail
    res_single = await gateway_client.get(f"/v1/books/{book_id}", headers=auth_headers)
    assert res_single.status_code == 200
    assert res_single.json()["title"] == book["title"]

    # 4. Get chapters list
    res_chapters = await gateway_client.get(f"/v1/books/{book_id}/chapters", headers=auth_headers)
    assert res_chapters.status_code == 200
    ch_data = res_chapters.json()
    assert ch_data["total"] == 2
    ch1 = ch_data["items"][0]
    assert ch1["number"] == 1
    assert ch1["printed_page_start"] == 1
    ch1_id = ch1["id"]

    # 5. Get chapter detail (including educational concepts and chunk count)
    res_ch_detail = await gateway_client.get(f"/v1/chapters/{ch1_id}", headers=auth_headers)
    assert res_ch_detail.status_code == 200
    detail = res_ch_detail.json()
    assert detail["number"] == 1
    assert len(detail["concepts"]) >= 2
    assert detail["chunks_count"] >= 3
    assert any(c["title"] == "বর্গ ও বর্গমূলের ধারণা" for c in detail["concepts"])


# =============================================================================
# 6. Retrieval Evaluation Harness & Threshold Gate
# =============================================================================
@pytest.mark.asyncio
async def test_retrieval_evaluation_harness_threshold_gate() -> None:
    """Verify evaluation harness computes metrics and passes 80% accuracy threshold gate."""
    report = await run_evaluation(
        dataset_path=EVAL_DATASET_PATH,
        min_hit_rate=0.80,
        min_page_acc=0.80,
        top_k=5,
    )
    assert report["total_queries"] == 6
    assert report["hit_rate_5"] >= 0.80
    assert report["page_acc_5"] >= 0.80
    assert report["passed_gate"] is True
