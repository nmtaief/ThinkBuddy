#!/usr/bin/env python3
"""Database Fresh Restore Proof & Row Count Verification (Item 4).

Proves:
1. Automated pg_dump backup execution.
2. Fresh database creation ('thinkbuddy_restore_test') in PostgreSQL container.
3. Full restore from backup file.
4. Introspection and row count comparison across all schema tables.
5. Verification that 100% of row counts match exactly.
"""

import gzip
import logging
import subprocess
import sys
from pathlib import Path
import asyncpg
import asyncio

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restore_proof")

DB_USER = "thinkbuddy"
DB_PASS = "thinkbuddy_dev_password"
DB_HOST = "localhost"
DB_PORT = 5432
SRC_DB = "thinkbuddy"
TEST_DB = "thinkbuddy_restore_test"


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


async def recreate_test_db() -> None:
    """Drop and recreate fresh test database."""
    conn = await asyncpg.connect(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database="postgres")
    try:
        # Terminate active connections to test db
        await conn.execute(
            f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{TEST_DB}' AND pid <> pg_backend_pid();
            """
        )
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB};")
        await conn.execute(f"CREATE DATABASE {TEST_DB} OWNER {DB_USER};")
        logger.info(f"Fresh database '{TEST_DB}' created.")
    finally:
        await conn.close()


def restore_backup_into_test_db(backup_path: Path) -> None:
    """Execute psql inside container or locally to restore the backup."""
    logger.info(f"Restoring backup {backup_path.name} into '{TEST_DB}'...")
    container = "thinkbuddy-postgres"

    # Extract sql if gzipped
    if str(backup_path).endswith(".gz"):
        uncompressed_sql = backup_path.with_suffix("")
        with gzip.open(backup_path, "rb") as f_in, open(uncompressed_sql, "wb") as f_out:
            f_out.write(f_in.read())
        target_sql = uncompressed_sql
    else:
        target_sql = backup_path

    # Restore via docker exec
    with open(target_sql, "r", encoding="utf-8") as f_sql:
        cmd = ["docker", "exec", "-i", container, "psql", "-U", DB_USER, "-d", TEST_DB]
        res = subprocess.run(cmd, stdin=f_sql, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"Restore output warnings/errors: {res.stderr[:300]}")

    if target_sql != backup_path:
        target_sql.unlink(missing_ok=True)
    logger.info("Database restore operation complete.")


async def main_async() -> None:
    logger.info("=== Starting Database Fresh Restore Verification ===")

    # 1. Fetch source database table counts
    logger.info(f"Capturing table row counts from source database '{SRC_DB}'...")
    src_counts = await fetch_table_row_counts(SRC_DB)
    total_src_rows = sum(src_counts.values())
    logger.info(f"Source database has {len(src_counts)} tables and {total_src_rows} total rows.")

    # 2. Run fresh backup
    backup_file = Path("backups/database/restore_proof_backup.sql.gz")
    logger.info(f"Generating backup via scripts/backup_db.py -> {backup_file}...")
    res_b = subprocess.run([sys.executable, "scripts/backup_db.py", "--output", str(backup_file)], capture_output=True, text=True)
    assert res_b.returncode == 0, f"Backup failed: {res_b.stderr}"

    # 3. Drop and recreate fresh database
    await recreate_test_db()

    # 4. Restore into fresh test database
    restore_backup_into_test_db(backup_file)

    # 5. Fetch restored database table counts
    logger.info(f"Capturing table row counts from restored database '{TEST_DB}'...")
    restored_counts = await fetch_table_row_counts(TEST_DB)
    total_restored_rows = sum(restored_counts.values())

    # 6. Compare row counts
    print("\n" + "=" * 80)
    print("DATABASE RESTORE PROOF: TABLE ROW COUNT COMPARISON")
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
    print(f"Total Rows: Source = {total_src_rows} | Restored = {total_restored_rows}")
    print("=" * 80 + "\n")

    # Cleanup test DB and temp backup file
    backup_file.unlink(missing_ok=True)
    backup_file.with_suffix(backup_file.suffix + ".manifest.json").unlink(missing_ok=True)
    enc_file = backup_file.with_suffix(backup_file.suffix + ".enc")
    enc_file.unlink(missing_ok=True)

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
    logger.info("[SUCCESS] Database restore proof verified: 100% of tables and rows restored identically.")


if __name__ == "__main__":
    asyncio.run(main_async())
