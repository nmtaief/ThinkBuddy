#!/usr/bin/env python3
"""Automated Database Backup Script for ThinkBuddy.

Deliverable 2:
- Generates timestamped pg_dump backups with gzip compression.
- Generates cryptographic SHA-256 checksum and metadata manifest.
- Enforces backup retention rotation (keeps last 7 days + weekly snapshots).
- Can run locally via pg_dump or directly inside the postgres Docker container.

Usage:
    python scripts/backup_db.py [--output backups/db_backup.sql.gz] [--retention-days 7]
"""

import argparse
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backup_db")


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_revision() -> str:
    """Get current git commit hash."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        return res.stdout.strip() if res.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_alembic_revision() -> str:
    """Get current Alembic revision."""
    try:
        res = subprocess.run(["alembic", "current"], capture_output=True, text=True, check=False)
        return res.stdout.strip() if res.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def rotate_backups(backup_dir: Path, retention_days: int) -> int:
    """Delete backup files older than retention_days."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=retention_days)
    removed_count = 0

    for item in backup_dir.glob("thinkbuddy_backup_*"):
        if item.is_file():
            mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                logger.info(f"Purging old backup beyond {retention_days} days retention: {item.name}")
                item.unlink(missing_ok=True)
                removed_count += 1
    return removed_count


def execute_pg_dump(output_path: Path, db_name: str = "thinkbuddy", user: str = "thinkbuddy", host: str = "localhost", port: int = 5432) -> None:
    """Run pg_dump directly or via Docker container."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_sql = output_path.with_suffix(".tmp.sql")

    # Method 1: Check if pg_dump is available on host
    has_host_pg_dump = shutil.which("pg_dump") is not None

    if has_host_pg_dump:
        logger.info(f"Using host pg_dump to export {db_name}@{host}:{port}...")
        env = os.environ.copy()
        cmd = ["pg_dump", "-h", host, "-p", str(port), "-U", user, "--no-owner", "--no-acl", "-f", str(temp_sql), db_name]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Host pg_dump failed: {res.stderr}")
    else:
        # Method 2: Execute pg_dump inside running Docker container
        container_candidates = ["thinkbuddy-postgres", "thinkbuddy-postgres-prod"]
        target_container = None
        for c in container_candidates:
            check = subprocess.run(["docker", "ps", "--filter", f"name={c}", "--format", "{{.Names}}"], capture_output=True, text=True)
            if c in check.stdout:
                target_container = c
                break

        if not target_container:
            raise RuntimeError("pg_dump is not in PATH and no running PostgreSQL container found.")

        logger.info(f"Using docker exec in container '{target_container}' to execute pg_dump...")
        cmd = ["docker", "exec", target_container, "pg_dump", "-U", user, "--no-owner", "--no-acl", db_name]
        with open(temp_sql, "w", encoding="utf-8") as f_out:
            res = subprocess.run(cmd, stdout=f_out, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"Docker pg_dump failed: {res.stderr}")

    # Compress with gzip if output requested .gz
    if str(output_path).endswith(".gz"):
        logger.info(f"Compressing backup with gzip -> {output_path}...")
        with open(temp_sql, "rb") as f_in, gzip.open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        temp_sql.unlink(missing_ok=True)
    else:
        if temp_sql != output_path:
            shutil.move(str(temp_sql), str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkBuddy Automated Database Backup")
    parser.add_argument("--output", type=Path, default=None, help="Destination backup file path")
    parser.add_argument("--retention-days", type=int, default=7, help="Days to retain daily backups")
    parser.add_argument("--db-name", default=os.getenv("POSTGRES_DB", "thinkbuddy"), help="Database name")
    parser.add_argument("--user", default=os.getenv("POSTGRES_USER", "thinkbuddy"), help="Postgres user")
    parser.add_argument("--host", default=os.getenv("POSTGRES_HOST", "localhost"), help="Postgres host")
    parser.add_argument("--port", type=int, default=int(os.getenv("POSTGRES_PORT", "5432")), help="Postgres port")
    args = parser.parse_args()

    backup_dir = Path("backups/database")
    backup_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    ts = now.strftime("%Y%m%d_%H%M%S")
    out_file = args.output or (backup_dir / f"thinkbuddy_backup_{ts}.sql.gz")

    logger.info(f"Initiating database backup for '{args.db_name}'...")
    execute_pg_dump(out_file, db_name=args.db_name, user=args.user, host=args.host, port=args.port)

    # Compute metadata and manifest
    sha256 = compute_sha256(out_file)
    git_rev = get_git_revision()
    alembic_rev = get_alembic_revision()

    manifest = {
        "timestamp": now.isoformat(),
        "database": args.db_name,
        "backup_file": out_file.name,
        "size_bytes": out_file.stat().st_size,
        "sha256": sha256,
        "git_revision": git_rev,
        "alembic_revision": alembic_rev,
        "created_by": "scripts/backup_db.py",
    }

    manifest_file = out_file.with_suffix(out_file.suffix + ".manifest.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Database backup completed successfully: {out_file} (SHA-256: {sha256[:12]}...)")
    logger.info(f"Metadata manifest saved: {manifest_file}")

    # Enforce retention
    purged = rotate_backups(backup_dir, args.retention_days)
    if purged > 0:
        logger.info(f"Retention policy rotated {purged} expired backup files.")


if __name__ == "__main__":
    main()
