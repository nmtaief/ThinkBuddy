"""Disaster recovery utility: Replay deletion ledger against restored databases.

Ensures accounts and families deleted after snapshot point-in-time are not resurrected.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.models import User
from core.common.database import get_db_session
from core.families.models import Family
from core.privacy.models import AccountDeletion, DeletionLedger
from core.privacy.purge import execute_data_purge

logger = logging.getLogger("thinkbuddy.privacy.replay_ledger")


async def replay_deletion_ledger(db: AsyncSession) -> dict[str, int]:
    """Inspect all active users and families and re-purge any that appear in deletion_ledger."""
    # 1. Fetch all ledger hashes
    stmt_ledger = select(DeletionLedger.user_id_hash, DeletionLedger.target_type)
    ledger_records = (await db.execute(stmt_ledger)).all()
    user_hashes = {h for h, t in ledger_records if t == "user"}
    family_hashes = {h for h, t in ledger_records if t == "family"}

    repurged_users = 0
    repurged_families = 0

    # 2. Check active users
    stmt_users = select(User).where(User.status != "purged")
    users = (await db.execute(stmt_users)).scalars().all()
    for user in users:
        u_hash = hashlib.sha256(str(user.id).encode("utf-8")).hexdigest()
        if u_hash in user_hashes:
            logger.warning(f"Replay ledger detected resurrected user {user.id}; executing immediate purge.")
            # Create synthetic immediate deletion record to execute purge
            deletion = AccountDeletion(
                user_id=user.id,
                target_type="user",
                status="pending_grace_period",
                scheduled_purge_at=user.created_at,  # Immediate purge
            )
            db.add(deletion)
            await db.flush()
            repurged_users += 1

    # 3. Check active families
    stmt_fams = select(Family)
    families = (await db.execute(stmt_fams)).scalars().all()
    for fam in families:
        f_hash = hashlib.sha256(str(fam.id).encode("utf-8")).hexdigest()
        if f_hash in family_hashes:
            logger.warning(f"Replay ledger detected resurrected family {fam.id}; executing immediate purge.")
            deletion = AccountDeletion(
                user_id=fam.owner_parent_id,
                family_id=fam.id,
                target_type="family",
                status="pending_grace_period",
                scheduled_purge_at=fam.created_at,  # Immediate purge
            )
            db.add(deletion)
            await db.flush()
            repurged_families += 1

    await db.commit()

    if repurged_users > 0 or repurged_families > 0:
        await execute_data_purge(db)

    return {"repurged_users": repurged_users, "repurged_families": repurged_families}


if __name__ == "__main__":
    async def _main():
        async for session in get_db_session():
            res = await replay_deletion_ledger(session)
            print(f"Deletion ledger replay complete: {res}")
            break

    asyncio.run(_main())

