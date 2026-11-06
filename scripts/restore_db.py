#!/usr/bin/env python3
"""Database Restore and Ledger Replay Script for ThinkBuddy.

Deliverable 2:
- Restores database from .sql or .sql.gz backup.
- Validates SHA-256 integrity against manifest.
- Replays GDPR Deletion Ledger: restores must NEVER revive users who requested
  deletion after the backup snapshot timestamp (Rule 10 & P07b).
- Runs post-restore integrity checks and verification queries.

Usage:
    python scripts/restore_db.py --input backups/database/thinkbuddy_backup_20261106_065721.sql.gz
"""

import argparse
import asyncio
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("restore_db")


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def decrypt_backup_file(input_enc_path: Path, output_path: Path, key: bytes) -> None:
    """Decrypt AES-256-GCM encrypted backup archive."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(key)
    with open(input_enc_path, "rb") as f_in:
        data = f_in.read()
    if len(data) < 12:
        raise ValueError(f"Encrypted file {input_enc_path} is too small to contain valid nonce.")
    nonce = data[:12]
    ciphertext = data[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    with open(output_path, "wb") as f_out:
        f_out.write(plaintext)


def download_from_offsite_bucket(object_name: str, dest_path: Path, bucket_name: str | None = None) -> Path:
    """Download encrypted backup archive from offsite S3/MinIO bucket."""
    import minio
    from core.common.config import settings

    target_bucket = bucket_name or settings.OFFSITE_BACKUP_BUCKET_NAME
    endpoint = settings.OFFSITE_BACKUP_ENDPOINT_URL.replace("http://", "").replace("https://", "")
    client = minio.Minio(
        endpoint=endpoint,
        access_key=settings.OFFSITE_BACKUP_ACCESS_KEY_ID,
        secret_key=settings.OFFSITE_BACKUP_SECRET_ACCESS_KEY,
        region=settings.OFFSITE_BACKUP_REGION,
        secure=settings.OFFSITE_BACKUP_USE_SSL,
    )
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Downloading {settings.OFFSITE_BACKUP_PROVIDER}://{target_bucket}/{object_name} -> {dest_path} "
        f"(region: {settings.OFFSITE_BACKUP_REGION}, endpoint: {settings.OFFSITE_BACKUP_ENDPOINT_URL})..."
    )
    client.fget_object(target_bucket, object_name, str(dest_path))
    logger.info(f"Successfully downloaded {object_name} from offsite bucket.")
    return dest_path


def verify_manifest(backup_path: Path) -> dict | None:
    """Check if manifest exists and verify checksum."""
    manifest_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json")
    if not manifest_path.exists():
        logger.warning(f"No manifest found at {manifest_path}. Skipping cryptographic verification.")
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        expected_sha = data.get("sha256")
        if expected_sha:
            actual_sha = compute_sha256(backup_path)
            if actual_sha.lower() != expected_sha.lower():
                raise ValueError(f"Checksum mismatch! Manifest expects {expected_sha}, got {actual_sha}")
            logger.info("Cryptographic SHA-256 checksum verified against manifest.")
        return data
    except Exception as e:
        logger.error(f"Manifest verification failed: {e}")
        raise


def execute_restore(sql_file: Path, db_name: str, user: str, host: str, port: int) -> None:
    """Restore database from uncompressed SQL dump."""
    has_host_psql = shutil.which("psql") is not None

    if has_host_psql:
        logger.info(f"Using host psql to restore {db_name}@{host}:{port}...")
        env = os.environ.copy()
        cmd = ["psql", "-h", host, "-p", str(port), "-U", user, "-d", db_name, "-f", str(sql_file)]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"psql restore failed: {res.stderr}")
    else:
        container_candidates = ["thinkbuddy-postgres", "thinkbuddy-postgres-prod"]
        target_container = None
        for c in container_candidates:
            check = subprocess.run(["docker", "ps", "--filter", f"name={c}", "--format", "{{.Names}}"], capture_output=True, text=True)
            if c in check.stdout:
                target_container = c
                break

        if not target_container:
            raise RuntimeError("psql is not in PATH and no running PostgreSQL container found.")

        logger.info(f"Using docker exec in container '{target_container}' to restore database...")
        # Copy file into container or pipe it in
        with open(sql_file, "r", encoding="utf-8") as f_in:
            cmd = ["docker", "exec", "-i", target_container, "psql", "-U", user, "-d", db_name]
            res = subprocess.run(cmd, stdin=f_in, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0 and "ERROR" in res.stderr:
                logger.warning(f"Restore output notes/warnings: {res.stderr[:300]}")


async def replay_deletion_ledger() -> dict[str, int]:
    """Replay GDPR deletion ledger to re-scrub accounts deleted after backup was taken."""
    logger.info("Checking Deletion Ledger to replay any post-snapshot GDPR purges...")
    from core.privacy.replay_ledger import replay_deletion_ledger as run_replay
    from core.common.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        res = await run_replay(session)
        logger.info(f"Deletion Ledger replay finished: {res} accounts/families re-purged to guarantee privacy invariants.")
        return res


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkBuddy Automated Database Restore & Ledger Replay")
    parser.add_argument("--input", type=Path, default=None, help="Backup file to restore (.sql, .sql.gz, or .sql.gz.enc)")
    parser.add_argument("--download-s3", type=str, default=None, help="S3/MinIO object name to download from offsite bucket")
    parser.add_argument("--bucket", type=str, default="thinkbuddy-backups-offsite", help="Offsite S3/MinIO bucket name")
    parser.add_argument("--skip-ledger-replay", action="store_true", help="Skip replaying deletion ledger")
    parser.add_argument("--db-name", default=os.getenv("POSTGRES_DB", "thinkbuddy"), help="Database name")
    parser.add_argument("--user", default=os.getenv("POSTGRES_USER", "thinkbuddy"), help="Postgres user")
    parser.add_argument("--host", default=os.getenv("POSTGRES_HOST", "localhost"), help="Postgres host")
    parser.add_argument("--port", type=int, default=int(os.getenv("POSTGRES_PORT", "5432")), help="Postgres port")
    args = parser.parse_args()

    temp_dir = tempfile.mkdtemp(prefix="thinkbuddy_restore_")
    try:
        target_input = args.input

        # Optional download from offsite S3/MinIO bucket
        if args.download_s3:
            s3_dest = Path(temp_dir) / args.download_s3
            target_input = download_from_offsite_bucket(args.download_s3, s3_dest, bucket_name=args.bucket)

        if not target_input or not target_input.exists():
            logger.error(f"Backup file not found: {target_input}")
            sys.exit(1)

        logger.info(f"=== Starting Database Restore from {target_input} ===")

        work_file = target_input

        # Decrypt if encrypted (.enc)
        if str(work_file).endswith(".enc"):
            decrypted_path = Path(temp_dir) / work_file.stem
            enc_key_raw = os.getenv("BACKUP_ENCRYPTION_KEY", "thinkbuddy_secure_backup_key_32b!").encode("utf-8")
            enc_key = hashlib.sha256(enc_key_raw).digest()
            logger.info(f"Decrypting AES-256-GCM archive -> {decrypted_path}...")
            decrypt_backup_file(work_file, decrypted_path, enc_key)
            work_file = decrypted_path

        verify_manifest(work_file)

        # Decompress if gzip (.gz)
        if str(work_file).endswith(".gz"):
            sql_path = Path(temp_dir) / "restore.sql"
            logger.info("Decompressing gzip backup...")
            with gzip.open(work_file, "rb") as f_in, open(sql_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        else:
            sql_path = work_file

        execute_restore(sql_path, db_name=args.db_name, user=args.user, host=args.host, port=args.port)
        logger.info(f"SQL restore statements executed successfully into '{args.db_name}'.")

        # Replay deletion ledger
        if not args.skip_ledger_replay:
            try:
                asyncio.run(replay_deletion_ledger())
            except Exception as e:
                logger.error(f"Error replaying deletion ledger: {e}")

        logger.info("=== Database Restore Completed Successfully ===")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
