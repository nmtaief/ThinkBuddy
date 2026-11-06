"""Pydantic schemas for parental consent, data exports, and deletion lifecycle."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ParentalConsentRequest(BaseModel):
    version: str = Field(default="1.0", description="Terms and Privacy Policy consent version (e.g. '1.0')")
    consented: bool = Field(default=True, description="Explicit affirmative parental consent granted")
    terms_hash: str | None = Field(default=None, description="SHA-256 fingerprint of the presented consent terms")


class ParentalConsentResponse(BaseModel):
    status: str = Field(default="granted", description="Consent status ('granted' or 'withdrawn')")
    version: str = Field(..., description="Active consent version")
    terms_hash: str = Field(..., description="SHA-256 digest of consented legal text")
    consented_at: datetime = Field(..., description="Timestamp when consent was recorded")
    parent_id: uuid.UUID = Field(..., description="Unique identifier of consenting parent")


class ParentalConsentStatusResponse(BaseModel):
    has_consent: bool = Field(..., description="Whether valid parental consent is currently recorded")
    version: str | None = Field(default=None, description="Current recorded consent version")
    terms_hash: str | None = Field(default=None, description="Recorded consent terms hash")
    current_terms_hash: str = Field(..., description="Active system consent terms hash")
    reconsent_required: bool = Field(default=False, description="True if legal text updated and re-consent needed")
    consented_at: datetime | None = Field(default=None, description="Timestamp of recorded consent")
    withdrawn_at: datetime | None = Field(default=None, description="Timestamp of consent withdrawal if applicable")


class ConsentVersionDetailResponse(BaseModel):
    version: str = Field(..., description="Consent legal terms version (e.g. 'v1.0')")
    text_bn: str = Field(..., description="Full legal disclosure text in Bengali")
    text_en: str = Field(..., description="Full legal disclosure text in English")
    terms_hash: str = Field(..., description="Cryptographic SHA-256 fingerprint of full composite terms")
    effective_at: datetime = Field(..., description="Timestamp when version became effective")


class WithdrawConsentRequest(BaseModel):
    reason: str | None = Field(default=None, description="Optional explanation for withdrawing consent")


class WithdrawConsentResponse(BaseModel):
    status: str = Field(default="withdrawn", description="Consent status updated to withdrawn")
    parent_id: uuid.UUID
    withdrawn_at: datetime
    message: str = Field(..., description="Confirmation notice in Bangla and English")


class ChatTopicSummaryItem(BaseModel):
    topic: str = Field(..., description="Curriculum concept or topic title")
    book_title: str = Field(..., description="Textbook title")
    chapter_title: str = Field(..., description="Textbook chapter title")
    chapter_number: int | None = Field(default=None, description="Chapter index")
    message_count: int = Field(..., description="Aggregated query count for this topic")
    last_active_at: datetime = Field(..., description="Timestamp of most recent interaction")


class StudentExportPayload(BaseModel):
    student_id: uuid.UUID
    display_name: str
    class_level: int
    medium: str
    group: str | None = None
    school: str | None = None
    daily_minutes: int
    study_setups: list[dict[str, Any]] = Field(default_factory=list)
    mastery_summary: dict[str, Any] = Field(default_factory=dict)
    revision_items_count: int = 0
    quiz_attempts_count: int = 0
    quiz_attempts_summary: list[dict[str, Any]] = Field(default_factory=list)
    chat_topics: list[ChatTopicSummaryItem] = Field(
        default_factory=list,
        description="Strictly topic-level aggregated summaries; raw transcripts are excluded per Rule 15.",
    )


class FamilyDataExportPayload(BaseModel):
    family_id: uuid.UUID
    family_name: str
    owner_parent_id: uuid.UUID
    created_at: datetime
    requester_id: uuid.UUID
    members: list[dict[str, Any]]
    students: list[StudentExportPayload]
    parental_consents: list[dict[str, Any]]
    exported_at: datetime


class FamilyDataExportResponse(BaseModel):
    export_id: uuid.UUID
    family_id: uuid.UUID
    download_url: str = Field(..., description="Short-lived signed download URL (15 minutes TTL)")
    expires_at: datetime = Field(..., description="Export availability expiration timestamp (7 days)")
    exported_at: datetime
    data: FamilyDataExportPayload


class RequestAccountDeletionBody(BaseModel):
    confirmation: str = Field(
        ...,
        description="Explicit confirmation keyword; must be 'DELETE' or 'মুছে ফেলুন'",
    )
    reason: str | None = Field(default=None, description="Optional deletion feedback")


class AccountDeletionResponse(BaseModel):
    deletion_id: uuid.UUID
    target_type: str = Field(..., description="'user' or 'family'")
    target_id: uuid.UUID
    status: str = Field(default="pending_grace_period")
    grace_period_days: int = Field(default=14)
    requested_at: datetime
    scheduled_purge_at: datetime
    message: str


class CancelDeletionResponse(BaseModel):
    deletion_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    status: str = Field(default="cancelled")
    message: str


class PurgeJobReport(BaseModel):
    purged_accounts: int = 0
    purged_families: int = 0
    revoked_sessions: int = 0
    revoked_push_tokens: int = 0
    cleared_cache_keys: int = 0
    deleted_s3_objects: int = 0
    deleted_notifications: int = 0
    deleted_learning_signals: int = 0
    deleted_shadow_runs: int = 0
    anonymized_audit_records: int = 0
    failed_user_ids: list[str] = Field(default_factory=list)
    executed_at: datetime
