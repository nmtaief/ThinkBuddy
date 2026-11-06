"""Authorization and ownership policy enforcement across all ThinkBuddy services.

Enforces Rule 9 from GEMINI.md:
'Authorization on every route. Use role checks plus ownership checks
(a parent can only access linked students; a student only their own data).'
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.database import get_db_session
from core.families.models import ParentStudentLink


async def can_access_student(
    user: User,
    student_id: uuid.UUID,
    session: AsyncSession,
) -> bool:
    """Evaluate whether the given user is authorized to read or manage student data."""
    # 1. Students can only access their own data
    if user.role == "student":
        return user.id == student_id

    # 2. Parents can only access active, verified linked students
    if user.role == "parent":
        stmt = select(ParentStudentLink).where(
            ParentStudentLink.parent_id == user.id,
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == "active",
            ParentStudentLink.revoked_at.is_(None),
        )
        result = await session.execute(stmt)
        active_link = result.scalar_one_or_none()
        return active_link is not None

    # 3. Admins have system-level access
    if user.role == "admin":
        return True

    # 4. Teachers disabled by default in beta
    return False


async def check_student_access(
    student_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Dependency enforcing student data ownership; raises 403 if unauthorized."""
    if user.role == "student" and getattr(user, "has_parental_consent", True) is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CONSENT_WITHDRAWN",
                "message": "Parental consent is required to process minor student data. Processing is suspended.",
            },
        )
    has_access = await can_access_student(user, student_id, session)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_STUDENT_ACCESS",
                "message": "You do not have permission to access this student's data.",
            },
        )
    return user
