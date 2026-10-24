"""CLI tool to seed holiday calendar from a user-provided file.

Rule B.7: 'Seed the holiday calendar only from a file I provide, marked unverified.
Do not invent dates.'
Rule C.8: 'Admin holiday and policy changes follow draft, impact preview, then publish.
Drafts never affect plans.'

Usage:
    python scripts/seed_holidays.py --file path/to/holidays.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

from core.audit.models import AuditLog
from core.common.database import AsyncSessionLocal
from core.planner.models import Holiday

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def seed_holidays_from_file(file_path: Path) -> int:
    if not file_path.exists():
        logger.error("Holiday calendar seed file '%s' does not exist.", file_path)
        sys.exit(1)

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to parse holiday JSON file: %s", exc)
        sys.exit(1)

    if not isinstance(data, list):
        logger.error("Holiday seed file root must be a JSON array of holiday objects.")
        sys.exit(1)

    if not data:
        logger.warning("Holiday seed file is empty. No holidays imported.")
        return 0

    imported_count = 0
    async with AsyncSessionLocal() as session:
        for item in data:
            s_date = date.fromisoformat(item["start_date"])
            e_date = date.fromisoformat(item["end_date"])
            name = item["name"]
            h_type = item.get("holiday_type", "national")
            blackout = bool(item.get("study_blackout", False))
            obs_key = item.get("observance_key")

            h = Holiday(
                start_date=s_date,
                end_date=e_date,
                name=name,
                holiday_type=h_type,
                study_blackout=blackout,
                observance_key=obs_key,
                verified=False,  # Strictly marked unverified per Req B.7
                status="draft",  # Drafts never affect plans per Req C.8
                version=1,
            )
            session.add(h)
            imported_count += 1

        await session.flush()

        audit = AuditLog(
            actor_id=None,
            action="holiday.cli_seed",
            target_type="holiday_calendar",
            target_id=str(file_path),
            meta={"count": imported_count, "verified": False, "status": "draft"},
        )
        session.add(audit)
        await session.commit()

    logger.info(
        "Successfully seeded %d holiday calendar entries (all marked unverified and draft).",
        imported_count,
    )
    return imported_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed ThinkBuddy holiday calendar strictly from a user-provided file."
    )
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="Path to user-provided JSON holiday file containing array of holiday objects",
    )
    args = parser.parse_args()
    asyncio.run(seed_holidays_from_file(args.file))


if __name__ == "__main__":
    main()
