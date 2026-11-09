"""CLI tool for creating or promoting administrative users.

Usage:
    python scripts/create_admin.py --phone +8801700000099 \
        --email admin@thinkbuddy.internal --name "System Admin"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
import uuid

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.families.models  # noqa: F401
from sqlalchemy import select

from core.audit.models import AuditLog
from core.auth.models import User
from core.common.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def create_or_promote_admin(phone: str, email: str, name: str) -> None:
    async with AsyncSessionLocal() as session:
        # Check if user exists by phone or email
        stmt = select(User).where((User.phone == phone) | (User.email == email))
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if user:
            old_role = user.role
            user.role = "admin"
            user.status = "active"
            if name:
                user.display_name = name
            action = "user.promote_admin"
            logger.info(
                "Promoting existing user %s (%s) from '%s' to 'admin'.",
                user.id,
                user.phone,
                old_role,
            )
            meta = {"old_role": old_role, "new_role": "admin", "promoted": True}
        else:
            user = User(
                id=uuid.uuid4(),
                auth_provider="system",
                auth_uid=f"system:{phone}",
                phone=phone,
                email=email,
                role="admin",
                display_name=name or "Administrator",
                status="active",
            )
            session.add(user)
            action = "user.create_admin"
            logger.info("Creating new admin user %s (%s).", user.id, phone)
            meta = {"role": "admin", "created": True}

        await session.flush()

        audit = AuditLog(
            actor_id=user.id,
            action=action,
            target_type="user",
            target_id=str(user.id),
            meta=meta,
        )
        session.add(audit)
        await session.commit()
        logger.info(
            "Admin user successfully configured: ID=%s, Phone=%s, Role=admin", user.id, user.phone
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote ThinkBuddy admin user.")
    parser.add_argument("--phone", required=True, help="E.164 phone number, e.g. +8801700000099")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--name", default="Admin", help="Display name")

    args = parser.parse_args()
    asyncio.run(create_or_promote_admin(args.phone, args.email, args.name))


if __name__ == "__main__":
    main()
