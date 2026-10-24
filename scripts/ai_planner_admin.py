"""Administrative CLI tool for managing AI Planner Integration (P06a).

Provides CLI operations for:
- Viewing operational status, circuit breaker health, and rollout configuration
- Resetting circuit breaker state
- Toggling global kill switch
- Updating class band rollout

Per Standing Rule 15 and Milestone P06a: All actions write immutable records to the audit_log table.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.audit.models import AuditLog
from core.common.config import settings
from core.common.database import AsyncSessionLocal
from core.planner.provider import _global_ai_circuit_breaker


async def show_status() -> None:
    """Print current AI planner operational status."""
    is_open = not _global_ai_circuit_breaker.can_execute_sync()
    cb_state = "OPEN" if is_open else "CLOSED"

    print("=" * 70)
    print("THINKBUDDY AI PLANNER ADMINISTRATIVE STATUS (P06a)")
    print("=" * 70)
    print(f"Global Kill Switch (Enabled): {settings.AI_PLANNER_ENABLED}")
    print(f"Shadow Mode:                  {settings.AI_PLANNER_SHADOW_MODE}")
    print(f"Service URL:                  {settings.AI_PLANNER_URL}")
    print(f"Enabled Class Bands:          {settings.AI_PLANNER_ENABLED_CLASS_BANDS}")
    print(f"Circuit Breaker State:        {cb_state}")
    print(f"Circuit Breaker Threshold:    {settings.AI_PLANNER_CIRCUIT_BREAKER_FAILURES} failures")
    print(f"Circuit Breaker Reset Period: {settings.AI_PLANNER_CIRCUIT_BREAKER_RESET_SECONDS}s")
    print(f"Contract Version:             ai-planner/v1.0")
    print("=" * 70)


async def reset_breaker(admin_id: uuid.UUID) -> None:
    """Force reset circuit breaker to CLOSED and record in audit log."""
    await _global_ai_circuit_breaker.reset()

    async with AsyncSessionLocal() as session:
        audit = AuditLog(
            actor_id=admin_id,
            action="ai_planner.cli_circuit_breaker_reset",
            target_type="system_config",
            target_id=str(admin_id),
            meta={"admin_id": str(admin_id), "at": datetime.now(UTC).isoformat()},
        )
        session.add(audit)
        await session.commit()

    print("[SUCCESS] Circuit breaker force reset to CLOSED. Audit record written.")


async def toggle_kill_switch(admin_id: uuid.UUID, enabled: bool) -> None:
    """Toggle global kill switch and record in audit log."""
    old_val = settings.AI_PLANNER_ENABLED
    settings.AI_PLANNER_ENABLED = enabled

    async with AsyncSessionLocal() as session:
        audit = AuditLog(
            actor_id=admin_id,
            action="ai_planner.cli_toggle_kill_switch",
            target_type="system_config",
            target_id=str(admin_id),
            meta={
                "old_enabled": old_val,
                "new_enabled": enabled,
                "admin_id": str(admin_id),
                "at": datetime.now(UTC).isoformat(),
            },
        )
        session.add(audit)
        await session.commit()

    print(f"[SUCCESS] AI Planner kill switch set to {enabled} (was {old_val}). Audit record written.")


async def set_rollout(admin_id: uuid.UUID, class_bands: list[str]) -> None:
    """Update active class bands and record in audit log."""
    old_bands = list(settings.AI_PLANNER_ENABLED_CLASS_BANDS)
    settings.AI_PLANNER_ENABLED_CLASS_BANDS = class_bands

    async with AsyncSessionLocal() as session:
        audit = AuditLog(
            actor_id=admin_id,
            action="ai_planner.cli_set_rollout_bands",
            target_type="system_config",
            target_id=str(admin_id),
            meta={
                "old_class_bands": old_bands,
                "new_class_bands": class_bands,
                "admin_id": str(admin_id),
                "at": datetime.now(UTC).isoformat(),
            },
        )
        session.add(audit)
        await session.commit()

    print(f"[SUCCESS] AI Planner rollout updated to: {class_bands}. Audit record written.")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Planner Administrative CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status command
    subparsers.add_parser("status", help="Show operational status of AI Planner")

    # reset-breaker command
    reset_parser = subparsers.add_parser("reset-breaker", help="Reset circuit breaker to CLOSED")
    reset_parser.add_argument("--admin-id", type=uuid.UUID, default=uuid.uuid4())

    # toggle-kill-switch command
    toggle_parser = subparsers.add_parser("toggle-kill-switch", help="Toggle global kill switch")
    toggle_parser.add_argument("--enabled", choices=["true", "false"], required=True)
    toggle_parser.add_argument("--admin-id", type=uuid.UUID, default=uuid.uuid4())

    # set-rollout command
    rollout_parser = subparsers.add_parser("set-rollout", help="Set enabled rollout class bands")
    rollout_parser.add_argument("--class-bands", nargs="+", required=True)
    rollout_parser.add_argument("--admin-id", type=uuid.UUID, default=uuid.uuid4())

    args = parser.parse_args()

    if args.command == "status":
        asyncio.run(show_status())
    elif args.command == "reset-breaker":
        asyncio.run(reset_breaker(args.admin_id))
    elif args.command == "toggle-kill-switch":
        asyncio.run(toggle_kill_switch(args.admin_id, args.enabled == "true"))
    elif args.command == "set-rollout":
        asyncio.run(set_rollout(args.admin_id, args.class_bands))


if __name__ == "__main__":
    main()
