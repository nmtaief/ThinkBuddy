#!/usr/bin/env python3
"""Single-command Staging/Production Deployment and Rollback Script for ThinkBuddy.

Deliverable 1 & Acceptance:
- Staging deploys from CI with one command and rolls back cleanly on failure.
- Automates: Pre-flight checks -> Pre-deploy DB snapshot -> Image build ->
  Alembic migration -> Health check probe -> Rollback on error.

Usage:
    python scripts/deploy_staging.py [--env staging|production] [--rollback] [--snapshot-only]
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("deploy")


def run_cmd(cmd: list[str] | str, check: bool = True, capture: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
    """Execute a system command securely."""
    shell = isinstance(cmd, str)
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    logger.info(f"Executing: {cmd_str}")
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    res = subprocess.run(cmd, shell=shell, check=False, capture_output=capture, text=True, env=proc_env)
    if check and res.returncode != 0:
        err_msg = res.stderr.strip() if res.stderr else f"Command failed with exit code {res.returncode}"
        logger.error(f"Command failed: {cmd_str} -> {err_msg}")
        raise RuntimeError(err_msg)
    return res


def create_pre_deploy_snapshot(backup_dir: Path) -> Path:
    """Take a timestamped PostgreSQL pre-deploy database snapshot."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    snapshot_path = backup_dir / f"pre_deploy_snapshot_{ts}.sql"
    logger.info(f"Creating pre-deploy database snapshot at: {snapshot_path}")

    # Use backup script
    backup_cmd = [sys.executable, "scripts/backup_db.py", "--output", str(snapshot_path)]
    run_cmd(backup_cmd, check=True)
    logger.info(f"Pre-deploy snapshot successfully created: {snapshot_path}")
    return snapshot_path


def verify_staging_health(base_url: str = "http://localhost:8000", max_attempts: int = 12) -> bool:
    """Probe health endpoints to verify container and routing health post-deploy."""
    import urllib.request
    import json

    logger.info(f"Probing health endpoints at {base_url}...")
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(f"{base_url}/healthz")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    # Also probe client config endpoint
                    config_req = urllib.request.Request(
                        f"{base_url}/v1/client/config",
                        headers={"X-Client-Platform": "android", "X-Client-Form-Factor": "phone", "X-App-Version": "1.0.0"},
                    )
                    with urllib.request.urlopen(config_req, timeout=5) as cfg_resp:
                        if cfg_resp.status == 200:
                            cfg_body = json.loads(cfg_resp.read().decode())
                            logger.info(f"Health checks passed on attempt {attempt}/{max_attempts}. Config version: {cfg_body.get('client_config_version')}")
                            return True
        except Exception as e:
            logger.warning(f"Health check attempt {attempt}/{max_attempts} failed: {e}")
        time.sleep(5)
    return False


def execute_rollback(
    snapshot_path: Path | None,
    prev_compose_file: str = "docker-compose.yml",
    destructive_failure: bool = False,
) -> None:
    """Execute clean automated rollback on deploy failure.

    Policy (Item 4):
    - Primary: Redeploy previous application image with backward-compatible schema (expand-and-contract).
    - Snapshot restore: Reserved strictly for destructive data corruption failures.
    """
    logger.error("Initiating automated deployment rollback...")
    try:
        # 1. Stop failed deployment containers
        logger.info("Stopping failed deployment containers...")
        run_cmd("docker compose -f docker-compose.prod.yml down", check=False)

        # 2. Prefer redeploying previous image with expand-and-contract
        if destructive_failure and snapshot_path and snapshot_path.exists():
            logger.warning(f"Destructive data corruption failure: Restoring DB state from pre-deploy snapshot: {snapshot_path}")
            restore_cmd = [sys.executable, "scripts/restore_db.py", "--input", str(snapshot_path), "--skip-reauth-check"]
            run_cmd(restore_cmd, check=False)
        else:
            logger.info("Non-destructive deployment issue: Relying on expand-and-contract backward-compatible schema.")

        # 3. Restart previous stable container stack
        logger.info(f"Redeploying previous stable container stack: {prev_compose_file}")
        run_cmd(f"docker compose -f {prev_compose_file} up -d", check=True)
        logger.info("Rollback completed successfully. Previous stable container image is active.")
    except Exception as rb_err:
        logger.critical(f"FATAL: Rollback procedure encountered an error: {rb_err}")
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkBuddy Staging/Production Deployment and Rollback")
    parser.add_argument("--env", choices=["staging", "production"], default="staging", help="Target environment")
    parser.add_argument("--rollback", action="store_true", help="Trigger explicit rollback of last deployment")
    parser.add_argument("--snapshot-only", action="store_true", help="Only take a pre-deploy database snapshot")
    parser.add_argument("--compose-file", default="docker-compose.prod.yml", help="Compose file to use")
    args = parser.parse_args()

    backup_dir = Path("backups/snapshots")

    if args.rollback:
        execute_rollback(None, prev_compose_file="docker-compose.yml")
        return

    if args.snapshot_only:
        create_pre_deploy_snapshot(backup_dir)
        return

    logger.info(f"=== Starting ThinkBuddy {args.env.upper()} Deployment ===")
    snapshot_path = None
    try:
        # Step 1: Pre-flight snapshot
        snapshot_path = create_pre_deploy_snapshot(backup_dir)

        # Step 2: Build / pull updated container images
        logger.info(f"Building updated container images using {args.compose_file}...")
        run_cmd(f"docker compose -f {args.compose_file} build", check=True)

        # Step 3: Run database migrations
        logger.info("Running Alembic database migrations: alembic upgrade head...")
        run_cmd("alembic upgrade head", check=True)

        # Step 4: Deploy containers
        logger.info(f"Starting services with {args.compose_file}...")
        run_cmd(f"docker compose -f {args.compose_file} up -d", check=True)

        # Step 5: Post-deployment synthetic health check probe
        is_healthy = verify_staging_health(base_url="http://localhost:8000")
        if not is_healthy:
            raise RuntimeError("Post-deployment health checks failed to report healthy status within timeout window.")

        logger.info(f"=== ThinkBuddy {args.env.upper()} Deployment Succeeded ===")
    except Exception as e:
        logger.error(f"Deployment failed with error: {e}")
        execute_rollback(snapshot_path, prev_compose_file="docker-compose.yml")
        sys.exit(1)


if __name__ == "__main__":
    main()

