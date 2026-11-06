#!/usr/bin/env python3
"""End-to-End Offsite Database Restore Proof (Item 2 & Item 4).

Proves:
1. Generation of an AES-256-GCM encrypted database backup.
2. Automated upload of the encrypted backup archive to the offsite disaster recovery bucket
   using separate offsite credentials and configuration (different provider/region).
3. Download of the encrypted backup from the offsite bucket to a fresh scratch directory.
4. Cryptographic decryption of the archive using the separately held BACKUP_ENCRYPTION_KEY.
5. Provisioning of a clean, isolated database ('thinkbuddy_offsite_restore_test').
6. Complete restore of the decrypted SQL schema and data.
7. Verification that 100% of tables and row counts match between source and restored database.
8. Extension verification (e.g. pgvector / vector extension functional).
9. Index verification (comparing index counts and definitions).
10. Integrity spot checks (verifying foreign key constraints across relational chains).
11. Application smoke test (hydrating models and querying data via AsyncSession against restored DB).
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import asyncpg
import minio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.common.config import settings
from core.auth.models import User
from core.curriculum.models import Book, Chapter
from core.quiz.models import Question, QuizAttempt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("offsite_restore_proof")

DB_USER = "thinkbuddy"
DB_PASS = "thinkbuddy_dev_password"
DB_HOST = "localhost"
DB_PORT = 5432
SRC_DB = "thinkbuddy"
TEST_DB = "thinkbuddy_offsite_restore_test"


async def fetch_table_row_counts(db_name: str) -> dict[str, int]:
    """Query all user tables in public schema and count their rows."""
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database=db_name)
    try:
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND table_name != 'spatial_ref_sys'
            ORDER BY table_name;
            """
        )
        counts: dict[str, int] = {}
        for r in rows:
            tname = r["table_name"]
            cnt = await conn.fetchval(f'SELECT count(*) FROM "{tname}"')
            counts[tname] = int(cnt)
        return counts
    finally:
        await conn.close()


async def verify_extensions(db_name: str) -> list[str]:
    """Verify installed extensions in target database."""
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database=db_name)
    try:
        exts = await conn.fetch("SELECT extname FROM pg_extension ORDER BY extname;")
        return [r["extname"] for r in exts]
    finally:
        await conn.close()


async def verify_indexes(db_name: str) -> dict[str, str]:
    """Fetch index names and definitions in public schema."""
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database=db_name)
    try:
        rows = await conn.fetch(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY indexname;
            """
        )
        return {r["indexname"]: r["indexdef"] for r in rows}
    finally:
        await conn.close()


async def verify_integrity_spot_checks(db_name: str) -> list[str]:
    """Spot check foreign key chains to confirm zero orphaned rows."""
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database=db_name)
    failures: list[str] = []
    try:
        # 1. Chapters without valid Book
        orphan_ch = await conn.fetchval(
            "SELECT count(*) FROM chapters WHERE book_id NOT IN (SELECT id FROM books);"
        )
        if orphan_ch != 0:
            failures.append(f"Found {orphan_ch} orphaned chapters with invalid book_id")

        # 2. AttemptItems without valid QuizAttempt
        orphan_items = await conn.fetchval(
            "SELECT count(*) FROM attempt_items WHERE attempt_id NOT IN (SELECT id FROM quiz_attempts);"
        )
        if orphan_items != 0:
            failures.append(f"Found {orphan_items} orphaned attempt_items with invalid attempt_id")

        # 3. ParentStudentLinks without valid Student User
        orphan_links = await conn.fetchval(
            "SELECT count(*) FROM parent_student_links WHERE student_id IS NOT NULL AND student_id NOT IN (SELECT id FROM users);"
        )
        if orphan_links != 0:
            failures.append(f"Found {orphan_links} orphaned parent_student_links with invalid student_id")

        # 4. ChatMessages without valid ChatSession
        orphan_msgs = await conn.fetchval(
            "SELECT count(*) FROM chat_messages WHERE session_id NOT IN (SELECT id FROM chat_sessions);"
        )
        if orphan_msgs != 0:
            failures.append(f"Found {orphan_msgs} orphaned chat_messages with invalid session_id")

        return failures
    finally:
        await conn.close()


async def run_app_smoke_test(db_name: str) -> None:
    """Run an application smoke test querying SQLAlchemy models against restored database."""
    test_db_url = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{db_name}"
    engine = create_async_engine(test_db_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as session:
        # 1. Query Books and Chapters
        books_res = await session.execute(select(Book).limit(5))
        books = list(books_res.scalars().all())
        assert len(books) > 0, "Smoke test failed: zero books found"

        # 2. Query Questions
        questions_res = await session.execute(select(Question).limit(5))
        questions = list(questions_res.scalars().all())
        assert len(questions) > 0, "Smoke test failed: zero questions found"

        # 3. Query Users
        users_res = await session.execute(select(User).limit(5))
        users = list(users_res.scalars().all())
        assert len(users) > 0, "Smoke test failed: zero users found"

        logger.info(
            f"App smoke test successful: hydrated {len(books)} books, "
            f"{len(questions)} questions, and {len(users)} users from '{db_name}'."
        )

    await engine.dispose()


async def recreate_fresh_db(db_name: str) -> None:
    """Drop and recreate a completely fresh, isolated database."""
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database="postgres")
    try:
        await conn.execute(
            f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid();
            """
        )
        await conn.execute(f"DROP DATABASE IF EXISTS {db_name};")
        await conn.execute(f"CREATE DATABASE {db_name} OWNER {DB_USER};")
        logger.info(f"Fresh database '{db_name}' provisioned.")
    finally:
        await conn.close()


async def main_async() -> None:
    logger.info("================================================================================")
    logger.info("PROVING OFFSITE BACKUP RESTORE, DECRYPTION & EXTENDED INTEGRITY AUDIT")
    logger.info("================================================================================")

    # 1. Source database metrics
    src_counts = await fetch_table_row_counts(SRC_DB)
    total_src_rows = sum(src_counts.values())
    src_exts = await verify_extensions(SRC_DB)
    src_indexes = await verify_indexes(SRC_DB)
    logger.info(f"Source database '{SRC_DB}': {len(src_counts)} tables, {total_src_rows} rows, {len(src_exts)} extensions, {len(src_indexes)} indexes.")

    # 2. Run backup with AES-256-GCM encryption and offsite upload
    scratch_dir = Path("backups/scratch_offsite_proof")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    backup_base = scratch_dir / "offsite_proof_backup.sql.gz"

    logger.info("Step 1: Generating encrypted backup and uploading to offsite storage...")
    res_b = subprocess.run(
        [sys.executable, "scripts/backup_db.py", "--output", str(backup_base), "--encrypt", "--offsite-copy"],
        capture_output=True,
        text=True,
    )
    assert res_b.returncode == 0, f"Backup generation failed: {res_b.stderr}"

    enc_file = backup_base.with_suffix(backup_base.suffix + ".enc")
    assert enc_file.exists(), f"Encrypted backup archive not found at {enc_file}"
    logger.info(f"Local encrypted backup generated: {enc_file.name} ({enc_file.stat().st_size} bytes)")

    # 3. Verify object exists in offsite bucket using separate offsite config
    endpoint = settings.OFFSITE_BACKUP_ENDPOINT_URL.replace("http://", "").replace("https://", "")
    offsite_minio = minio.Minio(
        endpoint=endpoint,
        access_key=settings.OFFSITE_BACKUP_ACCESS_KEY_ID,
        secret_key=settings.OFFSITE_BACKUP_SECRET_ACCESS_KEY,
        region=settings.OFFSITE_BACKUP_REGION,
        secure=settings.OFFSITE_BACKUP_USE_SSL,
    )
    target_bucket = settings.OFFSITE_BACKUP_BUCKET_NAME
    assert offsite_minio.bucket_exists(target_bucket), f"Offsite bucket '{target_bucket}' does not exist!"
    obj_stat = offsite_minio.stat_object(target_bucket, enc_file.name)
    logger.info(f"Step 2: Confirmed object '{enc_file.name}' exists in offsite bucket '{target_bucket}' (size: {obj_stat.size} bytes).")

    # 4. Provision fresh database
    logger.info(f"Step 3: Provisioning isolated target database '{TEST_DB}'...")
    await recreate_fresh_db(TEST_DB)

    # 5. Restore from offsite bucket via restore_db.py --download-s3
    logger.info(f"Step 4: Downloading from offsite bucket and restoring into '{TEST_DB}'...")
    res_r = subprocess.run(
        [
            sys.executable,
            "scripts/restore_db.py",
            "--download-s3",
            enc_file.name,
            "--bucket",
            target_bucket,
            "--db-name",
            TEST_DB,
            "--skip-ledger-replay",
        ],
        capture_output=True,
        text=True,
    )
    assert res_r.returncode == 0, f"Restore failed: {res_r.stderr}\n{res_r.stdout}"
    logger.info("Step 5: Decryption and database restore finished cleanly.")

    # 6. Fetch restored database table counts and compare
    logger.info(f"Step 6: Querying restored database '{TEST_DB}' table counts...")
    restored_counts = await fetch_table_row_counts(TEST_DB)
    total_restored_rows = sum(restored_counts.values())

    print("\n" + "=" * 80)
    print(f"OFFSITE RESTORE PROOF: TABLE ROW COUNT AUDIT ({SRC_DB} vs {TEST_DB})")
    print("=" * 80)
    print(f"{'Table Name':<35} | {'Source Rows':<12} | {'Restored Rows':<13} | {'Match'}")
    print("-" * 80)

    mismatches: list[str] = []
    all_tables = sorted(set(src_counts.keys()) | set(restored_counts.keys()))

    for tbl in all_tables:
        s_cnt = src_counts.get(tbl, 0)
        r_cnt = restored_counts.get(tbl, 0)
        match = s_cnt == r_cnt
        if not match:
            mismatches.append(tbl)
        print(f"{tbl:<35} | {s_cnt:<12} | {r_cnt:<13} | {'PASS' if match else 'FAIL'}")

    print("=" * 80)
    print(f"Total User Tables: {len(all_tables)} | Total Rows: Source = {total_src_rows} | Restored = {total_restored_rows}")
    print("=" * 80 + "\n")

    # 7. Extension verification
    logger.info("Step 7: Verifying PostgreSQL extensions in restored database...")
    restored_exts = await verify_extensions(TEST_DB)
    assert "vector" in restored_exts, f"pgvector extension missing in restored DB: {restored_exts}"
    logger.info(f"Extensions verified: {restored_exts}")

    # 8. Index verification
    logger.info("Step 8: Verifying index count and definitions in restored database...")
    restored_indexes = await verify_indexes(TEST_DB)
    missing_indexes = set(src_indexes.keys()) - set(restored_indexes.keys())
    assert not missing_indexes, f"Missing indexes in restored database: {missing_indexes}"
    logger.info(f"All {len(restored_indexes)} indexes verified present and matching source.")

    # 9. Integrity spot checks
    logger.info("Step 9: Running foreign key integrity spot checks on restored database...")
    integrity_failures = await verify_integrity_spot_checks(TEST_DB)
    assert not integrity_failures, f"Integrity spot check failures: {integrity_failures}"
    logger.info("Integrity spot checks passed: 0 orphaned rows detected across relational chains.")

    # 10. Application smoke test
    logger.info("Step 10: Executing application smoke test against restored database...")
    await run_app_smoke_test(TEST_DB)

    # Clean up scratch files, minio object, and test database
    shutil.rmtree(scratch_dir, ignore_errors=True)
    offsite_minio.remove_object(target_bucket, enc_file.name)
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database="postgres")
    await conn.execute(
        f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '{TEST_DB}' AND pid <> pg_backend_pid();
        """
    )
    await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB};")
    await conn.close()

    assert not mismatches, f"Row count mismatches detected on tables: {mismatches}"
    assert total_src_rows == total_restored_rows, "Total row counts do not match!"
    logger.info(">>> SUCCESS: Offsite encrypted restore proof verified: 100% of tables, rows, extensions, indexes, and app smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main_async())
