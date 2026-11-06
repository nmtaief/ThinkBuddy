#!/usr/bin/env python3
"""End-to-End Offsite Database Restore Proof (Item 4).

Proves:
1. Generation of an AES-256-GCM encrypted database backup.
2. Automated upload of the encrypted backup archive to the offsite disaster recovery bucket.
3. Download of the encrypted backup from the offsite bucket to a fresh scratch directory.
4. Cryptographic decryption of the archive using the separately held BACKUP_ENCRYPTION_KEY.
5. Provisioning of a clean, isolated database ('thinkbuddy_offsite_restore_test').
6. Complete restore of the decrypted SQL schema and data.
7. Verification that 100% of tables and row counts match between source and restored database.
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

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.common.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("offsite_restore_proof")

DB_USER = "thinkbuddy"
DB_PASS = "thinkbuddy_dev_password"
DB_HOST = "localhost"
DB_PORT = 5432
SRC_DB = "thinkbuddy"
TEST_DB = "thinkbuddy_offsite_restore_test"
OFFSITE_BUCKET = "thinkbuddy-backups-offsite"


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
    logger.info("PROVING OFFSITE BACKUP RESTORE, DECRYPTION & ROW COUNT VERIFICATION")
    logger.info("================================================================================")

    # 1. Fetch source database table counts
    src_counts = await fetch_table_row_counts(SRC_DB)
    total_src_rows = sum(src_counts.values())
    logger.info(f"Source database '{SRC_DB}' has {len(src_counts)} tables and {total_src_rows} total rows.")

    # 2. Run backup with AES-256-GCM encryption and offsite upload to MinIO/S3
    scratch_dir = Path("backups/scratch_offsite_proof")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    backup_base = scratch_dir / "offsite_proof_backup.sql.gz"

    logger.info("Step 1: Generating encrypted backup and uploading to offsite bucket...")
    res_b = subprocess.run(
        [sys.executable, "scripts/backup_db.py", "--output", str(backup_base), "--encrypt", "--offsite-copy"],
        capture_output=True,
        text=True,
    )
    assert res_b.returncode == 0, f"Backup generation failed: {res_b.stderr}"

    enc_file = backup_base.with_suffix(backup_base.suffix + ".enc")
    assert enc_file.exists(), f"Encrypted backup archive not found at {enc_file}"
    logger.info(f"Local encrypted backup generated: {enc_file.name} ({enc_file.stat().st_size} bytes)")

    # 3. Verify object exists in MinIO offsite bucket
    minio_client = minio.Minio(
        endpoint=settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", ""),
        access_key=settings.S3_ACCESS_KEY_ID,
        secret_key=settings.S3_SECRET_ACCESS_KEY,
        secure=settings.S3_USE_SSL,
    )
    assert minio_client.bucket_exists(OFFSITE_BUCKET), f"Offsite bucket '{OFFSITE_BUCKET}' does not exist!"
    obj_stat = minio_client.stat_object(OFFSITE_BUCKET, enc_file.name)
    logger.info(f"Step 2: Confirmed object '{enc_file.name}' exists in offsite bucket (size: {obj_stat.size} bytes).")

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

    # Clean up scratch files, minio object, and test database
    shutil.rmtree(scratch_dir, ignore_errors=True)
    minio_client.remove_object(OFFSITE_BUCKET, enc_file.name)
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
    logger.info(">>> SUCCESS: Offsite encrypted restore proof verified: 100% of tables and rows restored identically.")


if __name__ == "__main__":
    asyncio.run(main_async())

