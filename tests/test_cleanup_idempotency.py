"""Unit tests for expired idempotency records cleanup background task."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.models import User
from core.chat.models import ChatIdempotencyRecord, ChatSession
from workers.cleanup_tasks import cleanup_expired_idempotency_records


from core.common.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_cleanup_expired_idempotency_records() -> None:
    async with AsyncSessionLocal() as fastsession:
        now = datetime.now(UTC)

        # Create student and fastsession
        student = User(
            id=uuid.uuid4(),
            auth_provider="phone",
            auth_uid=f"phone_{uuid.uuid4().hex[:8]}",
            role="student",
            display_name="Test Student",
            locale="bn",
            status="active",
        )
        fastsession.add(student)
        await fastsession.flush()

        chat_session = ChatSession(
            id=uuid.uuid4(),
            student_id=student.id,
            is_active=True,
            subject="science",
        )
        fastsession.add(chat_session)
        await fastsession.flush()

        # 1. Active record (expires in 24 hours)
        active_rec = ChatIdempotencyRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            session_id=chat_session.id,
            idempotency_key="key_active_123",
            response_payload={"answer": "hello active"},
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        fastsession.add(active_rec)

        # 2. Expired record (expired 1 hour ago)
        expired_rec1 = ChatIdempotencyRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            session_id=chat_session.id,
            idempotency_key="key_expired_456",
            response_payload={"answer": "hello expired 1"},
            created_at=now - timedelta(days=2),
            expires_at=now - timedelta(hours=1),
        )
        fastsession.add(expired_rec1)

        # 3. Expired record (expired 2 days ago)
        expired_rec2 = ChatIdempotencyRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            session_id=chat_session.id,
            idempotency_key="key_expired_789",
            response_payload={"answer": "hello expired 2"},
            created_at=now - timedelta(days=3),
            expires_at=now - timedelta(days=1),
        )
        fastsession.add(expired_rec2)
        await fastsession.commit()

        # Run cleanup
        purged = await cleanup_expired_idempotency_records(db=fastsession)
        assert purged == 2

        # Verify active record is still intact
        remaining = await fastsession.execute(
            select(ChatIdempotencyRecord).where(ChatIdempotencyRecord.student_id == student.id)
        )
        records = remaining.scalars().all()
        assert len(records) == 1
        assert records[0].idempotency_key == "key_active_123"

