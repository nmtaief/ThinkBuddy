"""FastAPI router for Parental Consent, Family Data Export, Account Deletion, and Data Purge (P07b)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user, require_role
from core.auth.models import User
from core.auth.tokens import decode_access_jwt
from core.common.database import get_db_session
from core.privacy.purge import execute_data_purge
from core.privacy.schemas import (
    AccountDeletionResponse,
    CancelDeletionResponse,
    FamilyDataExportResponse,
    ParentalConsentRequest,
    ParentalConsentResponse,
    ParentalConsentStatusResponse,
    PurgeJobReport,
    RequestAccountDeletionBody,
)
from core.privacy.service import PrivacyService

router = APIRouter(tags=["Privacy & Data Management"])


def extract_token_iat(authorization: str | None) -> int | None:
    """Helper to extract token issuance timestamp (iat) from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_jwt(token)
        return payload.get("iat")
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Parental Consent Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/parents/consent",
    response_model=ParentalConsentResponse,
    status_code=status.HTTP_200_OK,
)
async def record_parental_consent(
    payload: ParentalConsentRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ParentalConsentResponse:
    """Record verified parental consent for the authenticated parent."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await PrivacyService.record_parent_consent(
        db=db,
        parent=current_user,
        payload=payload,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.get(
    "/parents/consent",
    response_model=ParentalConsentStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_parental_consent_status(
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ParentalConsentStatusResponse:
    """Fetch current recorded parental consent status."""
    return await PrivacyService.get_parent_consent_status(db, current_user)


# -----------------------------------------------------------------------------
# Family Data Export Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/parents/me/export",
    response_model=FamilyDataExportResponse,
    status_code=status.HTTP_200_OK,
)
async def export_family_data_get(
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FamilyDataExportResponse:
    """Retrieve complete JSON family data export with topic-level chat summaries only (Rule 15)."""
    return await PrivacyService.export_family_data(db, current_user)


@router.post(
    "/parents/me/export",
    response_model=FamilyDataExportResponse,
    status_code=status.HTTP_200_OK,
)
async def export_family_data_post(
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FamilyDataExportResponse:
    """Trigger and retrieve family data export (POST variant)."""
    return await PrivacyService.export_family_data(db, current_user)


# -----------------------------------------------------------------------------
# Account & Family Deletion Lifecycle Endpoints (with Grace Period)
# -----------------------------------------------------------------------------


@router.post(
    "/users/me/delete",
    response_model=AccountDeletionResponse,
    status_code=status.HTTP_200_OK,
)
async def request_user_deletion(
    payload: RequestAccountDeletionBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> AccountDeletionResponse:
    """Schedule user account deletion. Requires recent re-authentication and grants 14-day grace period."""
    iat = extract_token_iat(authorization)
    return await PrivacyService.request_user_deletion(
        db=db,
        caller=current_user,
        payload=payload,
        auth_iat=iat,
    )


@router.post(
    "/users/me/cancel-deletion",
    response_model=CancelDeletionResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_user_deletion(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> CancelDeletionResponse:
    """Cancel pending account deletion during the 14-day grace period."""
    return await PrivacyService.cancel_user_deletion(db, current_user)


@router.post(
    "/families/{family_id}/delete",
    response_model=AccountDeletionResponse,
    status_code=status.HTTP_200_OK,
)
async def request_family_deletion(
    family_id: uuid.UUID,
    payload: RequestAccountDeletionBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> AccountDeletionResponse:
    """Schedule family deletion. Students are strictly forbidden (HTTP 403 STUDENT_CANNOT_DELETE_FAMILY)."""
    iat = extract_token_iat(authorization)
    return await PrivacyService.request_family_deletion(
        db=db,
        family_id=family_id,
        caller=current_user,
        payload=payload,
        auth_iat=iat,
    )


@router.post(
    "/families/{family_id}/cancel-deletion",
    response_model=CancelDeletionResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_family_deletion(
    family_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("parent", "admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> CancelDeletionResponse:
    """Cancel pending family deletion during the 14-day grace period."""
    return await PrivacyService.cancel_family_deletion(db, family_id, current_user)


# -----------------------------------------------------------------------------
# Admin Purge Maintenance Endpoint
# -----------------------------------------------------------------------------


@router.post(
    "/admin/privacy/purge",
    response_model=PurgeJobReport,
    status_code=status.HTTP_200_OK,
)
async def trigger_privacy_purge_job(
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurgeJobReport:
    """Admin endpoint to execute permanent data purge for records past their 14-day grace period."""
    return await execute_data_purge(db)
