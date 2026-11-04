"""Families, student onboarding, and parent-student linking endpoints."""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.dependencies import require_role
from core.auth.models import User
from core.auth.tokens import hash_link_code
from core.common.config import settings
from core.common.database import get_db_session
from core.common.policy import check_student_access
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile

router = APIRouter(tags=["Families & Linking"])


def utcnow() -> datetime:
    return datetime.now(UTC)


def generate_link_code(length: int = 8) -> str:
    """Generate human-readable, cryptographically strong alphanumeric link code."""
    alphabet = string.ascii_uppercase + string.digits
    # Exclude ambiguous characters (0, O, 1, I)
    alphabet = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


# Request/Response models
class CreateFamilyRequest(BaseModel):
    name: str = Field(..., description="Family name (e.g. 'রহমান পরিবার' or 'Rahman Family')")


class FamilyResponse(BaseModel):
    id: uuid.UUID
    owner_parent_id: uuid.UUID
    name: str
    created_at: datetime


class AddChildRequest(BaseModel):
    display_name: str = Field(..., description="Student's name (Bangla or English)")
    class_level: int = Field(..., ge=6, le=12, description="Class level (6-12)")
    medium: str = Field(default="bn", description="Medium: bn or en")
    group: str | None = Field(
        default=None, description="Group for 9-12 (science, humanities, business_studies)"
    )
    optional_subject_ids: list[str] = Field(
        default_factory=list, description="Optional or 4th subject identifiers"
    )
    school: str | None = Field(default=None, description="School name")
    daily_minutes: int = Field(default=45, ge=0, le=600, description="Daily study target")


class AddChildResponse(BaseModel):
    student_id: uuid.UUID
    link_code: str
    link_id: uuid.UUID
    expires_at: datetime


class RedeemLinkRequest(BaseModel):
    link_code: str = Field(..., min_length=4, max_length=16, description="Alphanumeric link code")


class RedeemLinkResponse(BaseModel):
    status: str
    link_id: uuid.UUID
    parent_id: uuid.UUID
    family_id: uuid.UUID | None = None
    student_id: uuid.UUID


class LinkedStudentResponse(BaseModel):
    student_id: uuid.UUID
    display_name: str
    class_level: int
    medium: str
    group: str | None = None
    optional_subject_ids: list[str] = Field(default_factory=list)
    school: str | None = None
    daily_minutes: int
    link_id: uuid.UUID
    linked_at: datetime | None = None


@router.post("/families", response_model=FamilyResponse, status_code=status.HTTP_201_CREATED)
async def create_family(
    payload: CreateFamilyRequest,
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FamilyResponse:
    """Parent creates a new family unit."""
    family = Family(
        id=uuid.uuid4(),
        owner_parent_id=current_user.id,
        name=payload.name,
    )
    db.add(family)
    await db.flush()

    # Add owner parent as family member
    member = FamilyMember(
        id=uuid.uuid4(),
        family_id=family.id,
        user_id=current_user.id,
        relation="parent",
    )
    db.add(member)

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        actor_id=current_user.id,
        action="family.create",
        target_type="family",
        target_id=str(family.id),
        meta={"family_name": payload.name},
    )
    db.add(audit)
    await db.flush()

    return FamilyResponse(
        id=family.id,
        owner_parent_id=family.owner_parent_id,
        name=family.name,
        created_at=family.created_at,
    )


@router.post(
    "/families/{family_id}/students",
    response_model=AddChildResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_child_to_family(
    family_id: uuid.UUID,
    payload: AddChildRequest,
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request = None,
) -> AddChildResponse:
    """Parent adds a child profile, creating an expiring link code for the student to redeem."""
    # Verify parent owns or belongs to family
    stmt = select(Family).where(Family.id == family_id)
    result = await db.execute(stmt)
    family = result.scalar_one_or_none()

    if not family or (family.owner_parent_id != current_user.id and current_user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN_FAMILY_ACCESS", "message": "You do not own this family."},
        )

    # Verify parental consent is on record before processing child data
    if not current_user.has_parental_consent and current_user.role != "admin":
        enforce_gate = (not settings.is_local) or (request is not None and request.headers.get("x-enforce-consent", "").lower() == "true")
        if enforce_gate:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PARENTAL_CONSENT_REQUIRED",
                    "message": "Parental consent must be recorded before child data can be processed.",
                },
            )

    # Create student user and academic profile
    student_uid = f"student_{uuid.uuid4().hex[:12]}"
    student_user = User(
        id=uuid.uuid4(),
        auth_provider="family_invite",
        auth_uid=student_uid,
        role="student",
        display_name=payload.display_name,
        locale="bn" if payload.medium == "bn" else "en",
        status="active",
    )
    db.add(student_user)
    await db.flush()

    student_profile = StudentProfile(
        user_id=student_user.id,
        class_level=payload.class_level,
        group=payload.group,
        optional_subject_ids=payload.optional_subject_ids,
        medium=payload.medium,
        school=payload.school,
        daily_minutes=payload.daily_minutes,
    )
    db.add(student_profile)

    # Generate single-use expiring link code
    plain_link_code = generate_link_code(8)
    code_hash = hash_link_code(plain_link_code)
    expires_at = utcnow() + timedelta(hours=settings.LINK_CODE_EXPIRE_HOURS)

    link = ParentStudentLink(
        id=uuid.uuid4(),
        parent_id=current_user.id,
        student_id=student_user.id,
        family_id=family.id,
        status="pending",
        link_code_hash=code_hash,
        link_code_expires_at=expires_at,
    )
    db.add(link)

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        actor_id=current_user.id,
        action="family.add_student",
        target_type="student",
        target_id=str(student_user.id),
        meta={"class_level": payload.class_level, "family_id": str(family.id)},
    )
    db.add(audit)
    await db.flush()

    return AddChildResponse(
        student_id=student_user.id,
        link_code=plain_link_code,
        link_id=link.id,
        expires_at=expires_at,
    )


@router.post("/links/redeem", response_model=RedeemLinkResponse)
async def redeem_link_code(
    payload: RedeemLinkRequest,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RedeemLinkResponse:
    """Student redeems link code to establish active family link."""
    raw_code = payload.link_code.strip().upper()
    code_hash = hash_link_code(raw_code)

    stmt = select(ParentStudentLink).where(
        ParentStudentLink.link_code_hash == code_hash,
        ParentStudentLink.status == "pending",
        ParentStudentLink.link_code_expires_at > utcnow(),
    )
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_OR_EXPIRED_CODE",
                "message": "Link code is invalid, expired, or already used.",
            },
        )

    # Transfer academic profile configuration from parent setup to redeeming student
    placeholder_student_id = link.student_id
    if placeholder_student_id and placeholder_student_id != current_user.id:
        stmt_prof = select(StudentProfile).where(StudentProfile.user_id == placeholder_student_id)
        prof_res = await db.execute(stmt_prof)
        parent_config_prof = prof_res.scalar_one_or_none()

        if parent_config_prof:
            stmt_curr = select(StudentProfile).where(StudentProfile.user_id == current_user.id)
            curr_res = await db.execute(stmt_curr)
            curr_prof = curr_res.scalar_one_or_none()
            if curr_prof:
                curr_prof.class_level = parent_config_prof.class_level
                curr_prof.medium = parent_config_prof.medium
                curr_prof.school = parent_config_prof.school
                curr_prof.daily_minutes = parent_config_prof.daily_minutes
            else:
                new_prof = StudentProfile(
                    user_id=current_user.id,
                    class_level=parent_config_prof.class_level,
                    medium=parent_config_prof.medium,
                    school=parent_config_prof.school,
                    daily_minutes=parent_config_prof.daily_minutes,
                )
                db.add(new_prof)

    # Bind link to the redeeming student and activate
    link.status = "active"
    link.student_id = current_user.id
    link.consent_at = utcnow()
    link.link_code_hash = None  # Invalidate single-use code

    # Add student to family members
    if link.family_id:
        member = FamilyMember(
            id=uuid.uuid4(),
            family_id=link.family_id,
            user_id=current_user.id,
            relation="child",
        )
        db.add(member)

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        actor_id=current_user.id,
        action="family.link_redeemed",
        target_type="parent_student_link",
        target_id=str(link.id),
        meta={"parent_id": str(link.parent_id), "student_id": str(current_user.id)},
    )
    db.add(audit)
    await db.flush()

    return RedeemLinkResponse(
        status="active",
        link_id=link.id,
        parent_id=link.parent_id,
        family_id=link.family_id,
        student_id=current_user.id,
    )


@router.post("/links/{link_id}/revoke")
async def revoke_parent_student_link(
    link_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Parent revokes an active or pending student link, immediately cutting off access."""
    stmt = select(ParentStudentLink).where(ParentStudentLink.id == link_id)
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LINK_NOT_FOUND", "message": "Link not found."},
        )

    if link.parent_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_LINK_REVOCATION",
                "message": "You can only revoke your own links.",
            },
        )

    link.status = "revoked"
    link.revoked_at = utcnow()
    link.link_code_hash = None

    # Invalidate dashboard cache for student (Item 5)
    from core.parent.service import ParentService
    await ParentService.invalidate_student_dashboard_cache(link.student_id)

    # Token cleanup on parent link revocation (Item 3: shared devices)
    from core.devices.models import Device
    stmt_shared = (
        select(Device.push_token)
        .where(Device.user_id == link.student_id, Device.push_token.is_not(None))
    )
    res_shared = await db.execute(stmt_shared)
    student_tokens = [t for t in res_shared.scalars().all() if t]
    if student_tokens:
        await db.execute(
            update(Device)
            .where(Device.user_id == current_user.id, Device.push_token.in_(student_tokens))
            .values(push_token=None)
        )

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        actor_id=current_user.id,
        action="family.link_revoked",
        target_type="parent_student_link",
        target_id=str(link.id),
        meta={"student_id": str(link.student_id)},
    )
    db.add(audit)
    await db.flush()

    return {"status": "revoked", "link_id": link.id, "revoked_at": link.revoked_at}


@router.get("/parents/me/students", response_model=list[LinkedStudentResponse])
async def list_linked_students(
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[LinkedStudentResponse]:
    """Return all currently active linked children for the authenticated parent."""
    stmt = (
        select(ParentStudentLink, User, StudentProfile)
        .join(User, ParentStudentLink.student_id == User.id)
        .outerjoin(StudentProfile, User.id == StudentProfile.user_id)
        .where(
            ParentStudentLink.parent_id == current_user.id,
            ParentStudentLink.status == "active",
            ParentStudentLink.revoked_at.is_(None),
            User.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    students: list[LinkedStudentResponse] = []
    for link, student, profile in rows:
        students.append(
            LinkedStudentResponse(
                student_id=student.id,
                display_name=student.display_name,
                class_level=profile.class_level if profile else 7,
                medium=profile.medium if profile else "bn",
                group=profile.group if profile else None,
                optional_subject_ids=profile.optional_subject_ids if profile else [],
                school=profile.school if profile else None,
                daily_minutes=profile.daily_minutes if profile else 45,
                link_id=link.id,
                linked_at=link.consent_at or link.created_at,
            )
        )
    return students


@router.get("/students/{student_id}")
async def get_student_profile(
    student_id: uuid.UUID,
    _auth_user: Annotated[User, Depends(check_student_access)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Fetch student profile; requires ownership (student or active linked parent)."""
    stmt = (
        select(User, StudentProfile)
        .outerjoin(StudentProfile, User.id == StudentProfile.user_id)
        .where(User.id == student_id, User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Student record not found."},
        )

    user, profile = row
    return {
        "student_id": user.id,
        "display_name": user.display_name,
        "class_level": profile.class_level if profile else 7,
        "medium": profile.medium if profile else "bn",
        "group": profile.group if profile else None,
        "optional_subject_ids": profile.optional_subject_ids if profile else [],
        "school": profile.school if profile else None,
        "daily_minutes": profile.daily_minutes if profile else 45,
        "status": user.status,
    }
