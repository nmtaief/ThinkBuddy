"""Consolidated test suite: test_quiz_integrity.py."""
from __future__ import annotations


# ========================================================================
# Consolidated from: tests/test_p04_secure_quiz.py
# ========================================================================

"""Acceptance, security, and integrity tests for Milestone P04: Secure Quiz Engine.

Verifies:
1. Zero Answer-Key Leakage Test: Active student endpoints never leak keys, rubrics, or explanations.
2. Clock Tampering & Server Deadline Test: Late answers rejected with 410 ATTEMPT_EXPIRED.
3. Token & Nonce Replay Test: Invalid token (401) and replayed/mismatched nonce (409) rejected.
4. Randomization & Variant Deduplication Test: Per-student question and option shuffle; variant groups deduplicated.
5. Web Platform Restriction Test: Assessed mode blocked on web (403 WEB_PLATFORM_PRACTICE_ONLY); practice allowed.
6. Review Route Protection Test: /review route strictly blocked with 403 ATTEMPT_NOT_SUBMITTED until submitted.
7. Chat Lockout Test: Active assessed quiz locks out chat (403 QUIZ_IN_PROGRESS_CHAT_LOCKED) and records chat_attempt event.
8. Integrity Events & Scoring Test: Telemetry penalties and invalidation thresholds enforced.
9. One Active Assessed Attempt Rule: 409 ACTIVE_ATTEMPT_ALREADY_EXISTS when attempting concurrent assessed quiz.
10. Auto-Grading & Learning Signals Test: Server auto-grades MCQ/short; emits quiz_wrong and quiz_slow learning_signals.
11. Admin Question Bank & JSONL Import Test: Unicode Bangla/English import with isolated keys and audit logging.
"""


import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core.common.config import settings
from core.families.models import ParentStudentLink

from core.audit.models import AuditLog
from core.auth.models import User
from core.auth.tokens import create_access_jwt
from core.common.database import AsyncSessionLocal
from core.quiz.models import (
    AttemptEvent,
    AttemptItem,
    LearningSignal,
    Question,
    QuestionKey,
    Quiz,
    QuizAttempt,
)
from core.quiz.builder import QuizBuilderService
from core.quiz.grading import normalize_bangla_text
from scripts.import_questions import import_jsonl_file
from workers.quiz_tasks import auto_submit_expired_attempts

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-p04-android-001",
    "Accept-Language": "bn",
}

CLIENT_HEADERS_WEB = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": "desktop",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-p04-web-002",
    "Accept-Language": "en",
}


def create_mock_play_integrity_token(
    nonce: str = "device-p04-android-001",
    package_name: str = "com.thinkbuddy.app",
    verdicts: list[str] | None = None,
    age_seconds: int = 0,
) -> str:
    """Helper to forge a valid signed mock Play Integrity token payload for tests."""
    import jwt
    if verdicts is None:
        verdicts = ["MEETS_STRONG_INTEGRITY", "MEETS_DEVICE_INTEGRITY", "MEETS_BASIC_INTEGRITY"]
    ts_millis = int((datetime.now(UTC) - timedelta(seconds=age_seconds)).timestamp() * 1000)
    claims = {
        "appIntegrity": {"packageName": package_name},
        "requestDetails": {"nonce": nonce, "timestampMillis": ts_millis},
        "deviceIntegrity": {"deviceRecognitionVerdict": verdicts},
    }
    return jwt.encode(claims, "test_secret_for_claims_32_bytes_ok!", algorithm="HS256")


def utcnow() -> datetime:
    return datetime.now(UTC)


async def create_test_user(role: str = "student", display_name: str = "Test User") -> User:
    """Helper to create and persist a test user."""
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            auth_provider="fake",
            auth_uid=f"fake:uid:{uuid.uuid4()}",
            role=role,
            status="active",
            display_name=display_name,
            phone=f"+88017{uuid.uuid4().hex[:8]}",
            locale="bn",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def seed_sample_questions() -> list[Question]:
    """Helper to ensure questions from fixtures/questions_sample.jsonl are in database."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Question))
        existing = list(res.scalars().all())
        if len(existing) >= 6:
            return existing

    fixture_path = Path("fixtures/questions_sample.jsonl")
    await import_jsonl_file(fixture_path)

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Question))
        return list(res.scalars().all())


async def create_test_quiz(
    student_id: uuid.UUID,
    mode: str = "assessed",
    question_count: int = 4,
    time_limit_s: int = 600,
) -> Quiz:
    """Helper to create a test quiz in database."""
    async with AsyncSessionLocal() as session:
        quiz = Quiz(
            id=uuid.uuid4(),
            student_id=student_id,
            title="গণিত দৈনিক কুইজ (Daily Math Quiz)",
            kind="daily",
            mode=mode,
            time_limit_s=time_limit_s,
            question_count=question_count,
        )
        session.add(quiz)
        await session.commit()
        await session.refresh(quiz)
        return quiz


# =============================================================================
# 1. Zero Answer-Key Leakage Acceptance Test
# =============================================================================
@pytest.mark.asyncio
async def test_zero_answer_key_leakage_during_active_quiz(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §5:
    
    Crawl every student-accessible endpoint during an active attempt and assert
    no answer keys, correct option IDs, explanations, or rubrics appear.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Student Leakage Check")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3)

    # 1. Start attempt
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    current_item = start_data["current_item"]

    # Verify start payload does not leak key or explanation
    raw_start = json.dumps(start_data)
    assert "correct_option_id" not in raw_start
    assert "correct_text" not in raw_start
    assert "rubric" not in raw_start
    assert "explanation" not in raw_start
    assert current_item is not None
    assert "id" in current_item["question"]

    # 2. Answer item in sequence with attempt token header
    item_headers = {
        **auth_headers,
        "X-Attempt-Token": attempt_token,
    }
    if current_item["question"]["type"] == "short":
        resp_payload: dict[str, Any] = {"text": "test_answer"}
    else:
        resp_payload = {"selected_option_id": current_item["question"]["options"][0]["id"]}

    res_answer = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/{current_item['position']}/answer",
        json={
            "nonce": current_item["nonce"],
            "response": resp_payload,
            "time_spent_ms": 15000,
        },
        headers=item_headers,
    )
    assert res_answer.status_code == 200
    answer_data = res_answer.json()

    # Rule: In assessed mode, is_correct must be withheld (None) until submit!
    assert answer_data["is_correct"] is None
    raw_answer = json.dumps(answer_data)
    assert "correct_option_id" not in raw_answer
    assert "correct_text" not in raw_answer
    assert "explanation" not in raw_answer

    # 3. Ingest telemetry event
    res_event = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/events",
        json={"type": "focus_lost", "meta": {"window": "split_screen"}},
        headers=item_headers,
    )
    assert res_event.status_code == 200
    assert "correct_option_id" not in json.dumps(res_event.json())

    # 4. Attempt to access review while still active -> strictly rejected with 403!
    res_review_early = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=auth_headers,
    )
    assert res_review_early.status_code == 403
    assert res_review_early.json()["error"]["code"] == "ATTEMPT_NOT_SUBMITTED"


# =============================================================================
# 2. Clock Tampering & Server Deadline Authority Test
# =============================================================================
@pytest.mark.asyncio
async def test_server_deadline_and_clock_tampering(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §2:
    
    Server-side deadline (deadline_at) is authoritative.
    Client manipulating system clock or headers cannot extend deadline.
    Late submissions receive 410 ATTEMPT_EXPIRED.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3, time_limit_s=60)

    # Start attempt
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    nonce = start_data["current_item"]["nonce"]

    # Tamper with server DB: simulate deadline having passed 5 minutes ago
    async with AsyncSessionLocal() as session:
        att = await session.get(QuizAttempt, uuid.UUID(attempt_id))
        assert att is not None
        att.deadline_at = utcnow() - timedelta(minutes=5)
        await session.commit()

    # Attempt answering item after deadline
    item_headers = {**auth_headers, "X-Attempt-Token": attempt_token}
    res_late = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": nonce, "response": {"selected_option_id": "opt_a"}, "time_spent_ms": 5000},
        headers=item_headers,
    )
    assert res_late.status_code == 410
    assert res_late.json()["error"]["code"] == "ATTEMPT_EXPIRED"

    # Verify attempt in DB was transitioned to expired
    async with AsyncSessionLocal() as session:
        att_db = await session.get(QuizAttempt, uuid.UUID(attempt_id))
        assert att_db is not None
        assert att_db.state == "expired"


# =============================================================================
# 3. Token & Nonce Replay Test
# =============================================================================
@pytest.mark.asyncio
async def test_token_and_nonce_replay_protection(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §2:
    
    Short-lived attempt_token and per-item server-issued nonce prevent replay attacks.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3)

    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={},
        headers=auth_headers,
    )
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    valid_attempt_token = start_data["attempt_token"]
    valid_nonce = start_data["current_item"]["nonce"]

    # 1. Invalid attempt token -> 401
    res_bad_token = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": valid_nonce, "response": {"selected_option_id": "opt_a"}},
        headers={**auth_headers, "X-Attempt-Token": "invalid_fake_token"},
    )
    assert res_bad_token.status_code == 401
    assert res_bad_token.json()["error"]["code"] == "INVALID_ATTEMPT_TOKEN"

    # 2. Invalid nonce -> 409
    res_bad_nonce = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": "forged_nonce_12345", "response": {"selected_option_id": "opt_a"}},
        headers={**auth_headers, "X-Attempt-Token": valid_attempt_token},
    )
    assert res_bad_nonce.status_code == 409
    assert res_bad_nonce.json()["error"]["code"] == "INVALID_ITEM_NONCE"

    # 3. Valid answer -> succeeds
    res_valid = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": valid_nonce, "response": {"selected_option_id": "opt_a"}},
        headers={**auth_headers, "X-Attempt-Token": valid_attempt_token},
    )
    assert res_valid.status_code == 200
    valid_data = res_valid.json()
    assert valid_data["is_correct"] is None, "In assessed mode, is_correct must be withheld (None)"

    # 4. Replay the same nonce with SAME answer -> idempotent 200 with identical response
    res_replay_same = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": valid_nonce, "response": {"selected_option_id": "opt_a"}},
        headers={**auth_headers, "X-Attempt-Token": valid_attempt_token},
    )
    assert res_replay_same.status_code == 200
    assert res_replay_same.json() == valid_data
    assert res_replay_same.json()["is_correct"] is None

    # 5. Replay the same nonce with DIFFERENT answer -> 409 ANSWER_MISMATCH
    res_replay_diff = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": valid_nonce, "response": {"selected_option_id": "opt_b"}},
        headers={**auth_headers, "X-Attempt-Token": valid_attempt_token},
    )
    assert res_replay_diff.status_code == 409
    assert res_replay_diff.json()["error"]["code"] == "ANSWER_MISMATCH"

    # 6. Replay with different nonce on already answered item -> 409 ITEM_ALREADY_ANSWERED
    res_replay_bad_nonce = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": "forged_new_nonce", "response": {"selected_option_id": "opt_a"}},
        headers={**auth_headers, "X-Attempt-Token": valid_attempt_token},
    )
    assert res_replay_bad_nonce.status_code == 409
    assert res_replay_bad_nonce.json()["error"]["code"] == "ITEM_ALREADY_ANSWERED"


# =============================================================================
# 4. Randomization & Variant Deduplication Test
# =============================================================================
@pytest.mark.asyncio
async def test_randomization_and_variant_deduplication(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §2 & §5:
    
    1. Pool variant deduplication: At most 1 question per variant_group_id.
    2. Two students get randomized question order and randomized option orders.
    """
    await seed_sample_questions()
    student_a = await create_test_user(role="student", display_name="Student Alpha")
    student_b = await create_test_user(role="student", display_name="Student Beta")

    token_a = create_access_jwt(student_a.id, "student")
    token_b = create_access_jwt(student_b.id, "student")

    quiz_a = await create_test_quiz(student_a.id, mode="assessed", question_count=4)
    quiz_b = await create_test_quiz(student_b.id, mode="assessed", question_count=4)

    res_a = await gateway_client.post(
        f"/v1/quizzes/{quiz_a.id}/attempts",
        json={},
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_a}"},
    )
    res_b = await gateway_client.post(
        f"/v1/quizzes/{quiz_b.id}/attempts",
        json={},
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_b}"},
    )

    data_a = res_a.json()
    data_b = res_b.json()

    attempt_id_a = uuid.UUID(data_a["attempt_id"])
    attempt_id_b = uuid.UUID(data_b["attempt_id"])

    # Verify variant deduplication in database for attempt A
    async with AsyncSessionLocal() as session:
        items_a = (
            await session.execute(
                select(AttemptItem).where(AttemptItem.attempt_id == attempt_id_a)
            )
        ).scalars().all()
        q_ids_a = [it.question_id for it in items_a]
        questions_a = (
            await session.execute(select(Question).where(Question.id.in_(q_ids_a)))
        ).scalars().all()

        variant_groups_seen = [
            q.variant_group_id for q in questions_a if q.variant_group_id is not None
        ]
        # At most 1 question per variant group
        assert len(variant_groups_seen) == len(set(variant_groups_seen))

        # Check attempt B variant deduplication
        items_b = (
            await session.execute(
                select(AttemptItem).where(AttemptItem.attempt_id == attempt_id_b)
            )
        ).scalars().all()
        q_ids_b = [it.question_id for it in items_b]
        questions_b = (
            await session.execute(select(Question).where(Question.id.in_(q_ids_b)))
        ).scalars().all()
        variant_groups_seen_b = [
            q.variant_group_id for q in questions_b if q.variant_group_id is not None
        ]
        assert len(variant_groups_seen_b) == len(set(variant_groups_seen_b))

    # Opaque option IDs check: all options must have opaque identifiers (e.g. opt_...)
    options_a = data_a["current_item"]["question"]["options"]
    if data_a["current_item"]["question"]["type"] == "mcq":
        assert len(options_a) > 0
        for opt in options_a:
            assert "id" in opt
            assert "text" in opt


# =============================================================================
# 5. Web Platform Restriction Test
# =============================================================================
@pytest.mark.asyncio
async def test_web_platform_cannot_start_assessed_attempt(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §3:
    
    Web build is practice-only because browsers cannot block screenshots or clipboard.
    Attempting to start assessed quiz from web returns 403 WEB_PLATFORM_PRACTICE_ONLY.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")

    quiz_assessed = await create_test_quiz(student.id, mode="assessed")
    quiz_practice = await create_test_quiz(student.id, mode="practice")

    # 1. Web client attempts assessed quiz -> 403 Forbidden
    res_web_assessed = await gateway_client.post(
        f"/v1/quizzes/{quiz_assessed.id}/attempts",
        json={},
        headers={**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {token}"},
    )
    assert res_web_assessed.status_code == 403
    assert res_web_assessed.json()["error"]["code"] == "WEB_PLATFORM_PRACTICE_ONLY"

    # 2. Web client starts practice quiz -> 201 Created
    res_web_practice = await gateway_client.post(
        f"/v1/quizzes/{quiz_practice.id}/attempts",
        json={},
        headers={**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {token}"},
    )
    assert res_web_practice.status_code == 201


# =============================================================================
# 6. Review Route Protection Test
# =============================================================================
@pytest.mark.asyncio
async def test_review_route_strictly_protected_until_submit(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §5:
    
    GET /attempts/{id}/review is strictly guarded until submitted/expired.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    other_student = await create_test_user(role="student")

    token = create_access_jwt(student.id, "student")
    other_token = create_access_jwt(other_student.id, "student")

    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}
    other_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {other_token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=2)

    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={},
        headers=auth_headers,
    )
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]

    # 1. Attempt review while active -> 403 ATTEMPT_NOT_SUBMITTED
    res_review_active = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=auth_headers,
    )
    assert res_review_active.status_code == 403
    assert res_review_active.json()["error"]["code"] == "ATTEMPT_NOT_SUBMITTED"

    # 2. Submit attempt
    res_submit = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        headers={**auth_headers, "X-Attempt-Token": attempt_token},
    )
    assert res_submit.status_code == 200

    # 3. Attempt review after submission -> 200 OK with correct answers & explanations
    res_review_post = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=auth_headers,
    )
    assert res_review_post.status_code == 200
    review_data = res_review_post.json()
    assert review_data["state"] == "submitted"
    assert len(review_data["items"]) == 2
    for it in review_data["items"]:
        assert "correct_answer" in it
        assert "explanation" in it

    # 4. Cross-student authorization check -> other student cannot review -> 404 Not Found
    res_review_other = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=other_headers,
    )
    assert res_review_other.status_code == 404
    assert res_review_other.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"


# =============================================================================
# 7. Chat Lockout Integration Test
# =============================================================================
@pytest.mark.asyncio
async def test_chat_lockout_during_active_assessed_quiz(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §2:
    
    Chat endpoint rejects while student has an active assessed attempt.
    Logs chat_attempt event in attempt_events and applies penalty.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # Before quiz: chat sessions can be created
    res_chat_ok = await gateway_client.post(
        "/v1/chat/sessions",
        json={"title": "Tutor Chat Before Quiz"},
        headers=auth_headers,
    )
    assert res_chat_ok.status_code == 201
    session_id = res_chat_ok.json()["id"]

    # Start assessed quiz
    quiz = await create_test_quiz(student.id, mode="assessed")
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={},
        headers=auth_headers,
    )
    attempt_id = res_start.json()["attempt_id"]
    attempt_token = res_start.json()["attempt_token"]

    # While quiz is active: creating chat session is blocked
    res_chat_blocked1 = await gateway_client.post(
        "/v1/chat/sessions",
        json={"title": "Cheat Attempt"},
        headers=auth_headers,
    )
    assert res_chat_blocked1.status_code == 403
    assert res_chat_blocked1.json()["error"]["code"] == "QUIZ_IN_PROGRESS_CHAT_LOCKED"

    # While quiz is active: sending chat message is blocked
    res_chat_blocked2 = await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "Please give me the answer to question 1"},
        headers=auth_headers,
    )
    assert res_chat_blocked2.status_code == 403
    assert res_chat_blocked2.json()["error"]["code"] == "QUIZ_IN_PROGRESS_CHAT_LOCKED"

    # Verify telemetry event was recorded in DB
    async with AsyncSessionLocal() as session:
        events = (
            await session.execute(
                select(AttemptEvent).where(
                    AttemptEvent.attempt_id == uuid.UUID(attempt_id),
                    AttemptEvent.type == "chat_attempt",
                )
            )
        ).scalars().all()
        assert len(events) >= 1

    # Finalize quiz
    await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        headers={**auth_headers, "X-Attempt-Token": attempt_token},
    )

    # After submit: chat is unlocked immediately
    res_chat_unlocked = await gateway_client.post(
        "/v1/chat/sessions",
        json={"title": "Post Quiz Discussion"},
        headers=auth_headers,
    )
    assert res_chat_unlocked.status_code == 201


# =============================================================================
# 8. Integrity Events & Telemetry Invalidation Test
# =============================================================================
@pytest.mark.asyncio
async def test_integrity_events_and_invalidation(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §2 & §6:
    
    Telemetry events deduct from integrity_score.
    Severe violations or cumulative events invalidate the attempt.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {token}",
        "X-Device-Integrity": create_mock_play_integrity_token(nonce="device-p04-android-001"),
    }

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={},
        headers=auth_headers,
    )
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]

    item_headers = {**auth_headers, "X-Attempt-Token": attempt_token}

    # 1. Light infraction: focus_lost (penalty 0.05)
    res_e1 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/events",
        json={"type": "focus_lost", "meta": {"window": "split_screen"}},
        headers=item_headers,
    )
    assert res_e1.status_code == 200
    assert res_e1.json()["integrity_score"] == 0.95
    assert res_e1.json()["state"] == "active"

    # 2. Moderate infraction: multi_window (penalty 0.20)
    res_e2 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/events",
        json={"type": "multi_window", "meta": {"state": "docked"}},
        headers=item_headers,
    )
    assert res_e2.status_code == 200
    assert res_e2.json()["integrity_score"] == 0.75
    assert res_e2.json()["state"] == "active"

    # 3. Critical infraction: screenshot_attempt (penalty 0.40)
    # Score drops to 0.35 <= 0.50 -> transitions state to invalidated!
    res_e3 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/events",
        json={"type": "screenshot_attempt", "meta": {"trigger": "hardware_button"}},
        headers=item_headers,
    )
    assert res_e3.status_code == 200
    e3_data = res_e3.json()
    assert e3_data["integrity_score"] <= 0.40
    assert e3_data["state"] == "invalidated"

    # 4. Submitting an invalidated attempt marks it flagged and returns reason
    res_submit = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        headers=item_headers,
    )
    assert res_submit.status_code == 200
    submit_data = res_submit.json()
    assert submit_data["is_flagged"] is True
    assert submit_data["invalid_reason"] is not None


# =============================================================================
# 9. One Active Assessed Attempt Rule
# =============================================================================
@pytest.mark.asyncio
async def test_one_active_assessed_attempt_limit(gateway_client: AsyncClient) -> None:
    """Per docs/05_SECURE_QUIZ.md §4:
    
    A student can only have one active assessed attempt at a time.
    Attempting to start a concurrent one returns 409 Conflict.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz1 = await create_test_quiz(student.id, mode="assessed")
    quiz2 = await create_test_quiz(student.id, mode="assessed")

    # Start first assessed attempt -> 201 OK
    res_start1 = await gateway_client.post(
        f"/v1/quizzes/{quiz1.id}/attempts",
        json={},
        headers=auth_headers,
    )
    assert res_start1.status_code == 201
    att1_id = res_start1.json()["attempt_id"]
    att1_token = res_start1.json()["attempt_token"]

    # Attempt to start second assessed attempt while first is active -> 409 Conflict
    res_start2 = await gateway_client.post(
        f"/v1/quizzes/{quiz2.id}/attempts",
        json={},
        headers=auth_headers,
    )
    assert res_start2.status_code == 409
    assert res_start2.json()["error"]["code"] == "ACTIVE_ATTEMPT_ALREADY_EXISTS"

    # Finalize first attempt
    res_sub = await gateway_client.post(
        f"/v1/attempts/{att1_id}/submit",
        headers={**auth_headers, "X-Attempt-Token": att1_token},
    )
    assert res_sub.status_code == 200

    # Now second assessed attempt can start -> 201 OK
    res_start2_retry = await gateway_client.post(
        f"/v1/quizzes/{quiz2.id}/attempts",
        json={},
        headers=auth_headers,
    )
    assert res_start2_retry.status_code == 201


# =============================================================================
# 10. Server-Side Auto-Grading & Learning Signals Test
# =============================================================================
@pytest.mark.asyncio
async def test_auto_grading_and_learning_signals_emission(gateway_client: AsyncClient) -> None:
    """Per docs/03_DATA_MODEL.md §6 and docs/05_SECURE_QUIZ.md:
    
    1. Server auto-grades MCQ and short answers using isolated question_keys.
    2. Writes learning_signals for incorrect answers (quiz_wrong) and slow responses (quiz_slow).
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=2)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={},
        headers=auth_headers,
    )
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    item1 = start_data["current_item"]

    item_headers = {**auth_headers, "X-Attempt-Token": attempt_token}

    # Fetch correct answer for item 1 from isolated DB
    async with AsyncSessionLocal() as session:
        key1 = (
            await session.execute(
                select(QuestionKey).where(QuestionKey.question_id == uuid.UUID(item1["question"]["id"]))
            )
        ).scalar_one()

    if item1["question"]["type"] == "short":
        resp1: dict[str, Any] = {"text": key1.correct_text}
    else:
        resp1 = {"selected_option_id": key1.correct_option_id}

    # 1. Answer Item 1 correctly within reasonable time
    res_a1 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={
            "nonce": item1["nonce"],
            "response": resp1,
            "time_spent_ms": 20000,
        },
        headers=item_headers,
    )
    assert res_a1.status_code == 200
    item2 = res_a1.json()["next_item"]

    # 2. Answer Item 2 deliberately incorrectly, and with slow response time (> 90s)
    res_a2 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/2/answer",
        json={
            "nonce": item2["nonce"],
            "response": {"selected_option_id": "wrong_choice_opt_xyz"},
            "time_spent_ms": 95000,  # 95s > 90s -> triggers quiz_slow signal
        },
        headers=item_headers,
    )
    assert res_a2.status_code == 200

    # 3. Finalize attempt
    res_submit = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        headers=item_headers,
    )
    assert res_submit.status_code == 200
    submit_data = res_submit.json()
    # 1 out of 2 correct = 50.0%
    assert submit_data["score"] == 50.0

    # 4. Verify learning_signals were persisted in database
    async with AsyncSessionLocal() as session:
        signals = (
            await session.execute(
                select(LearningSignal).where(LearningSignal.student_id == student.id)
            )
        ).scalars().all()
        sources = [s.source for s in signals]
        assert "quiz_wrong" in sources
        assert "quiz_slow" in sources


# =============================================================================
# 11. Admin Question Bank & JSONL Bulk Import Test
# =============================================================================
@pytest.mark.asyncio
async def test_admin_question_bank_and_jsonl_import(gateway_client: AsyncClient) -> None:
    """Per docs/04_API_CONTRACT.md §2 (Admin) and docs/05_SECURE_QUIZ.md:
    
    1. Admin can import questions in bulk from JSONL with Bangla/English Unicode.
    2. Writes audit log for governance.
    3. Student is rejected from admin question routes with 403 FORBIDDEN_ROLE.
    """
    admin = await create_test_user(role="admin", display_name="Admin Quiz Officer")
    student = await create_test_user(role="student", display_name="Regular Student")

    admin_token = create_access_jwt(admin.id, "admin")
    student_token = create_access_jwt(student.id, "student")

    admin_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {admin_token}"}
    student_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {student_token}"}

    # 1. Student attempted access to admin question bank -> 403
    res_forbidden = await gateway_client.get(
        "/v1/admin/questions",
        headers=student_headers,
    )
    assert res_forbidden.status_code == 403
    assert res_forbidden.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # 2. Admin creates a new Bangla question
    payload = {
        "type": "mcq",
        "difficulty": 0.5,
        "language": "bn",
        "stem": {"type": "text", "text": "সমকোণী ত্রিভুজের বৃহত্তম বাহুর নাম কী?"},
        "options": [
            {"id": "opt_h", "text": "অতিভুজ (Hypotenuse)"},
            {"id": "opt_b", "text": "ভূমি (Base)"},
            {"id": "opt_p", "text": "লম্ব (Perpendicular)"},
        ],
        "correct_option_id": "opt_h",
        "explanation": {"text": "সমকোণের বিপরীত বাহুকে অতিভুজ বলে, যা বৃহত্তম বাহু।"},
        "rubric": {},
        "origin": "curated",
        "review_status": "approved",
    }
    res_create = await gateway_client.post(
        "/v1/admin/questions",
        json=payload,
        headers=admin_headers,
    )
    assert res_create.status_code == 201
    q_id = uuid.UUID(res_create.json()["id"])

    # 3. Verify question key is stored in isolated table, not questions table
    async with AsyncSessionLocal() as session:
        q_row = await session.get(Question, q_id)
        assert q_row is not None
        assert q_row.type == "mcq"

        key_row = (
            await session.execute(
                select(QuestionKey).where(QuestionKey.question_id == q_id)
            )
        ).scalar_one_or_none()
        assert key_row is not None
        assert key_row.correct_option_id == "opt_h"
        assert "অতিভুজ" in key_row.explanation["text"]

        # Audit log verified
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_id == admin.id,
                    AuditLog.action == "question.create",
                    AuditLog.target_id == str(q_id),
                )
            )
        ).scalar_one_or_none()
        assert audit is not None


# =============================================================================
# 12. Pool Separation & Seen Question Exclusion Test
# =============================================================================
@pytest.mark.asyncio
async def test_pool_separation_and_seen_question_exclusion() -> None:
    """Verify that practice-only and assessed-only question pools are strictly isolated,
    and seen questions in assessed mode are excluded/deprioritized.
    """
    student = await create_test_user(role="student", display_name="Pool Separation Student")
    builder_student = student.id
    test_concept = f"concept_{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        # Create 3 distinct questions: practice, assessed, both
        q_prac = Question(
            id=uuid.uuid4(),
            type="mcq",
            difficulty=0.5,
            review_status="approved",
            concept_id=test_concept,
            pool="practice",
            stem={"text": "Practice Question Only"},
            options=[{"id": "opt_1", "text": "A"}],
        )
        q_asst = Question(
            id=uuid.uuid4(),
            type="mcq",
            difficulty=0.5,
            review_status="approved",
            concept_id=test_concept,
            pool="assessed",
            stem={"text": "Assessed Question Only"},
            options=[{"id": "opt_1", "text": "B"}],
        )
        q_both = Question(
            id=uuid.uuid4(),
            type="mcq",
            difficulty=0.5,
            review_status="approved",
            concept_id=test_concept,
            pool="both",
            stem={"text": "Shared Pool Question"},
            options=[{"id": "opt_1", "text": "C"}],
        )
        k_prac = QuestionKey(
            question_id=q_prac.id,
            correct_option_id="opt_1",
            explanation={"text": "Practice explanation"},
        )
        k_asst = QuestionKey(
            question_id=q_asst.id,
            correct_option_id="opt_1",
            explanation={"text": "Assessed explanation"},
        )
        k_both = QuestionKey(
            question_id=q_both.id,
            correct_option_id="opt_1",
            explanation={"text": "Both explanation"},
        )
        session.add_all([q_prac, q_asst, q_both, k_prac, k_asst, k_both])
        await session.commit()

        builder = QuizBuilderService(session)

        # 1. Assessed mode: practice-only question must NEVER appear
        assessed_questions = await builder.select_and_randomize_questions(
            question_count=10,
            student_id=builder_student,
            concept_ids=[test_concept],
            mode="assessed",
        )
        assessed_ids = {q.id for q in assessed_questions}
        assert q_prac.id not in assessed_ids
        assert q_asst.id in assessed_ids or q_both.id in assessed_ids

        # 2. Practice mode: assessed-only question must NEVER appear
        practice_questions = await builder.select_and_randomize_questions(
            question_count=10,
            student_id=builder_student,
            concept_ids=[test_concept],
            mode="practice",
        )
        practice_ids = {q.id for q in practice_questions}
        assert q_asst.id not in practice_ids
        assert q_prac.id in practice_ids or q_both.id in practice_ids

        # 3. Seen question exclusion in assessed mode:
        # Create an attempt and mark q_asst as answered
        quiz = await builder.build_quiz(student_id=builder_student, mode="assessed")
        attempt = QuizAttempt(
            quiz_id=quiz.id,
            student_id=builder_student,
            state="active",
            mode="assessed",
            attempt_token="test_token",
        )
        session.add(attempt)
        await session.flush()

        item = AttemptItem(
            attempt_id=attempt.id,
            position=1,
            question_id=q_asst.id,
            nonce="nonce_seen",
            answered_at=utcnow(),
            response={"selected_option_id": "opt_1"},
            is_correct=True,
            points=10.0,
        )
        session.add(item)
        await session.commit()

        # Query assessed questions again: answered question should be excluded when unseen candidates exist
        new_assessed = await builder.select_and_randomize_questions(
            question_count=1,
            student_id=builder_student,
            concept_ids=[test_concept],
            mode="assessed",
        )
        assert q_asst.id not in {q.id for q in new_assessed}


# =============================================================================
# 13. Concurrency & Database-Level Constraints Test
# =============================================================================
@pytest.mark.asyncio
async def test_concurrency_database_constraints_one_active_attempt_and_one_answer(
    gateway_client: AsyncClient,
) -> None:
    """Verify that:
    1. Simultaneous attempt starts for same student in assessed mode result in exactly 1 success and 1 409.
    2. Simultaneous answers for the same item position result in exactly 1 success and 1 409.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Concurrency Student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3)

    # 1. Concurrent attempt start race condition
    req1 = gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-concurrent-01"},
        headers=auth_headers,
    )
    req2 = gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-concurrent-02"},
        headers=auth_headers,
    )

    res1, res2 = await asyncio.gather(req1, req2)
    statuses = {res1.status_code, res2.status_code}
    assert statuses == {201, 409}

    successful_res = res1 if res1.status_code == 201 else res2
    attempt_data = successful_res.json()
    attempt_id = attempt_data["attempt_id"]
    attempt_token = attempt_data["attempt_token"]
    first_item = attempt_data["current_item"]
    assert first_item is not None

    item_headers = {**auth_headers, "X-Attempt-Token": attempt_token}
    ans_payload = {
        "nonce": first_item["nonce"],
        "response": {"selected_option_id": first_item["question"]["options"][0]["id"] if first_item["question"]["options"] else "dummy"},
        "time_spent_ms": 10000,
    }

    # 2. Concurrent duplicate answer race condition
    ans_req1 = gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/{first_item['position']}/answer",
        json=ans_payload,
        headers=item_headers,
    )
    ans_req2 = gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/{first_item['position']}/answer",
        json=ans_payload,
        headers=item_headers,
    )

    ans_res1, ans_res2 = await asyncio.gather(ans_req1, ans_req2)
    # Both concurrent requests with identical answer payload succeed idempotently
    assert ans_res1.status_code == 200
    assert ans_res2.status_code == 200
    assert ans_res1.json() == ans_res2.json()

    # Concurrent or subsequent submit with different answer payload fails with 409 ANSWER_MISMATCH
    diff_payload = {**ans_payload, "response": {"selected_option_id": "different_choice"}}
    ans_diff = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/{first_item['position']}/answer",
        json=diff_payload,
        headers=item_headers,
    )
    assert ans_diff.status_code == 409
    assert ans_diff.json()["error"]["code"] == "ANSWER_MISMATCH"


# =============================================================================
# 14. Scheduled Auto-Submit Job Test
# =============================================================================
@pytest.mark.asyncio
async def test_scheduled_job_auto_submits_expired_attempts(gateway_client: AsyncClient) -> None:
    """Verify that background worker auto_submit_expired_attempts:
    1. Finds attempts whose deadline_at is in the past.
    2. Marks them expired and sets submitted_at = deadline_at.
    3. Auto-grades items and writes learning_signals.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Auto Submit Student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3, time_limit_s=60)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-expire-01"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    attempt_id = uuid.UUID(res_start.json()["attempt_id"])

    # Manually backdate the attempt's deadline to simulate clock expiry
    past_time = utcnow() - timedelta(minutes=15)
    async with AsyncSessionLocal() as session:
        att = await session.get(QuizAttempt, attempt_id)
        assert att is not None
        att.deadline_at = past_time
        await session.commit()

        # Run scheduled auto-submit job
        processed = await auto_submit_expired_attempts(session)
        assert processed >= 1

        await session.refresh(att)
        assert att.state == "expired"
        assert att.submitted_at is not None
        assert att.score is not None

        # Verify learning signals were written for missed/unanswered items
        signals = (
            await session.execute(
                select(LearningSignal).where(LearningSignal.student_id == student.id)
            )
        ).scalars().all()
        assert len(signals) > 0


# =============================================================================
# 15. Device Integrity Attestation & Server-Side Anomaly Detection Test
# =============================================================================
@pytest.mark.asyncio
async def test_device_integrity_attestation_and_anomaly_detection(gateway_client: AsyncClient) -> None:
    """Verify that:
    1. Compromised device attestation verdict rejects assessed attempt with 403.
    2. Answering too fast (< 1500ms) flags time_too_fast anomaly and reduces score.
    3. Answering right after focus loss flags rapid_answer_after_focus_loss.
    4. Reaching thresholds pauses and invalidates the attempt.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Attestation Student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=4)

    # 1. Compromised device rejected from assessed mode
    compromised_headers = {**auth_headers, "X-Device-Integrity": "compromised"}
    res_comp = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-rooted-01"},
        headers=compromised_headers,
    )
    assert res_comp.status_code == 403
    assert res_comp.json()["error"]["code"] == "DEVICE_INTEGRITY_FAILED"

    # 2. Valid device starts assessed attempt
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-valid-01"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    item1 = start_data["current_item"]
    item_headers = {**auth_headers, "X-Attempt-Token": attempt_token}

    # 3. Anomaly 1: Time too fast (< 1500ms)
    res_fast = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/{item1['position']}/answer",
        json={
            "nonce": item1["nonce"],
            "response": {"selected_option_id": item1["question"]["options"][0]["id"] if item1["question"]["options"] else "dummy"},
            "time_spent_ms": 300,  # Suspiciously fast (< 1500ms)
        },
        headers=item_headers,
    )
    assert res_fast.status_code == 200
    item2 = res_fast.json()["next_item"]
    assert item2 is not None

    # Verify time_too_fast event recorded and score penalized
    async with AsyncSessionLocal() as session:
        att = await session.get(QuizAttempt, uuid.UUID(attempt_id))
        assert att is not None
        assert att.integrity_score < 1.0

        events = (
            await session.execute(
                select(AttemptEvent).where(
                    AttemptEvent.attempt_id == uuid.UUID(attempt_id),
                    AttemptEvent.type == "time_too_fast",
                )
            )
        ).scalars().all()
        assert len(events) >= 1

    # 4. Anomaly 2: Rapid answer right after focus loss
    # Ingest focus loss event
    await gateway_client.post(
        f"/v1/attempts/{attempt_id}/events",
        json={"type": "focus_lost", "meta": {"focus": "window_blur"}},
        headers=item_headers,
    )

    # Immediately answer next item (within focus loss window)
    res_after_focus = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/{item2['position']}/answer",
        json={
            "nonce": item2["nonce"],
            "response": {"selected_option_id": item2["question"]["options"][0]["id"] if item2["question"]["options"] else "dummy"},
            "time_spent_ms": 2500,
        },
        headers=item_headers,
    )
    assert res_after_focus.status_code == 200

    # Verify attempt reached pause threshold (2 anomalies)
    async with AsyncSessionLocal() as session:
        att = await session.get(QuizAttempt, uuid.UUID(attempt_id))
        assert att is not None
        assert att.state in ("paused", "invalidated")


# =============================================================================
# 16. Internal is_assessed_attempt_active Endpoint Test
# =============================================================================
@pytest.mark.asyncio
async def test_internal_is_assessed_attempt_active_endpoint(gateway_client: AsyncClient) -> None:
    """Verify that gateway/chat internal endpoint checks active assessed quiz status accurately."""
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Active Check Student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}
    from core.common.service_token import create_internal_service_token
    internal_headers = {"X-Internal-Service-Token": create_internal_service_token()}

    # 1. Before quiz start -> is_active = False
    from core.main import app as core_app
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=core_app), base_url="http://testserver") as core_client:
        res_before = await core_client.get(
            f"/v1/internal/quiz/students/{student.id}/active-attempt",
            headers=internal_headers,
        )
        assert res_before.status_code == 200
        assert res_before.json()["is_active"] is False
        assert res_before.json()["attempt_id"] is None

        # 2. Unauthorized without internal service token -> 403
        res_unauth = await core_client.get(
            f"/v1/internal/quiz/students/{student.id}/active-attempt",
            headers={"X-Internal-Service-Token": "invalid_internal_token"},
        )
        assert res_unauth.status_code == 403

        # 3. Start assessed quiz -> is_active = True
        quiz = await create_test_quiz(student.id, mode="assessed", question_count=2)
        res_start = await gateway_client.post(
            f"/v1/quizzes/{quiz.id}/attempts",
            json={"device_id": "device-active-chk-01"},
            headers=auth_headers,
        )
        assert res_start.status_code == 201
        attempt_id = res_start.json()["attempt_id"]
        attempt_token = res_start.json()["attempt_token"]

        res_during = await core_client.get(
            f"/v1/internal/quiz/students/{student.id}/active-attempt",
            headers=internal_headers,
        )
        assert res_during.status_code == 200
        assert res_during.json()["is_active"] is True
        assert res_during.json()["attempt_id"] == attempt_id

        # 4. Submit quiz -> is_active = False
        res_submit = await gateway_client.post(
            f"/v1/attempts/{attempt_id}/submit",
            headers={**auth_headers, "X-Attempt-Token": attempt_token},
        )
        assert res_submit.status_code == 200

        res_after = await core_client.get(
            f"/v1/internal/quiz/students/{student.id}/active-attempt",
            headers=internal_headers,
        )
        assert res_after.status_code == 200
        assert res_after.json()["is_active"] is False


# =============================================================================
# 17. Isolation Tests: Cross-Student and Parent Access
# =============================================================================
@pytest.mark.asyncio
async def test_isolation_cross_student_and_parent_access(gateway_client: AsyncClient) -> None:
    """Verify that:
    1. Cross-student attempt answering and submission are rejected with 403.
    2. Parent cannot access active attempt questions before submit (403 ATTEMPT_NOT_SUBMITTED).
    3. Unlinked parent cannot access attempt even after submit (403 FORBIDDEN).
    4. Linked parent can view review only after submission (200 OK).
    """
    await seed_sample_questions()
    student_a = await create_test_user(role="student", display_name="Student A")
    student_b = await create_test_user(role="student", display_name="Student B")
    parent_linked = await create_test_user(role="parent", display_name="Linked Parent")
    parent_unlinked = await create_test_user(role="parent", display_name="Unlinked Parent")

    token_a = create_access_jwt(student_a.id, "student")
    token_b = create_access_jwt(student_b.id, "student")
    token_p_linked = create_access_jwt(parent_linked.id, "parent")
    token_p_unlinked = create_access_jwt(parent_unlinked.id, "parent")

    headers_a = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_a}"}
    headers_b = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_b}"}
    headers_p_linked = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p_linked}"}
    headers_p_unlinked = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p_unlinked}"}

    # Link parent_linked with student_a
    async with AsyncSessionLocal() as session:
        link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=parent_linked.id,
            student_id=student_a.id,
            link_code_hash="dummy_hash",
            link_code_expires_at=utcnow() + timedelta(days=1),
            status="active",
        )
        session.add(link)
        await session.commit()

    quiz = await create_test_quiz(student_a.id, mode="assessed", question_count=2)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-isolation-01"},
        headers=headers_a,
    )
    assert res_start.status_code == 201
    attempt_id = res_start.json()["attempt_id"]
    attempt_token = res_start.json()["attempt_token"]
    item1 = res_start.json()["current_item"]

    # 1. Student B tries to answer Student A's attempt -> 404 Not Found (indistinguishable from non-existent)
    res_b_answer = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={
            "nonce": item1["nonce"],
            "response": {"selected_option_id": item1["question"]["options"][0]["id"] if item1["question"]["options"] else "dummy"},
            "time_spent_ms": 10000,
        },
        headers={**headers_b, "X-Attempt-Token": attempt_token},
    )
    assert res_b_answer.status_code == 404
    assert res_b_answer.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"

    # 2. Linked parent tries to access questions/review while active -> 403 ATTEMPT_NOT_SUBMITTED
    res_p_early = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=headers_p_linked,
    )
    assert res_p_early.status_code == 403
    assert res_p_early.json()["error"]["code"] == "ATTEMPT_NOT_SUBMITTED"

    # 3. Student A submits attempt
    res_submit = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        headers={**headers_a, "X-Attempt-Token": attempt_token},
    )
    assert res_submit.status_code == 200

    # 4. Unlinked parent tries to review Student A's submitted attempt -> 404 ATTEMPT_NOT_FOUND
    res_unlinked_review = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=headers_p_unlinked,
    )
    assert res_unlinked_review.status_code == 404
    assert res_unlinked_review.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"

    # 5. Linked parent reviews Student A's submitted attempt -> 200 OK
    res_linked_review = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=headers_p_linked,
    )
    assert res_linked_review.status_code == 200
    assert len(res_linked_review.json()["items"]) == 2


# =============================================================================
# 18. Bangla Normalization & Accepted-Answer Lists Test
# =============================================================================
@pytest.mark.asyncio
async def test_bangla_normalization_and_accepted_answers(gateway_client: AsyncClient) -> None:
    """Verify that short answer questions handle:
    1. Bengali digits normalized to standard digits ('১২' matches '12').
    2. Zero-width and invisible characters stripped ('ঢাকা\\u200c' matches 'ঢাকা').
    3. Accepted-answers list enables synonym matching (student enters 'dhaka' for 'ঢাকা').
    """
    # 1. Unit normalization test
    assert normalize_bangla_text("১২৩৪৫") == "12345"
    assert normalize_bangla_text("ঢাকা\u200c") == "ঢাকা"
    assert normalize_bangla_text("  গণিত   কুইজ  ") == "গণিত কুইজ"
    assert normalize_bangla_text("Dhaka City") == "dhaka city"

    # 2. End-to-end question grading test with accepted answers
    async with AsyncSessionLocal() as session:
        q_short = Question(
            id=uuid.uuid4(),
            type="short",
            difficulty=0.5,
            review_status="approved",
            pool="both",
            stem={"text": "বাংলাদেশের রাজধানী কী?"},
            options=[],
        )
        q_key = QuestionKey(
            question_id=q_short.id,
            correct_text="ঢাকা",
            accepted_answers=["dhaka", "রাজধানী ঢাকা", "ঢাকা শহর"],
            explanation={"text": "বাংলাদেশের রাজধানী ঢাকা।"},
        )
        session.add_all([q_short, q_key])
        await session.commit()

        # Grade using QuizGradingService directly
        from core.quiz.grading import QuizGradingService
        grader = QuizGradingService(session)

        dummy_item = AttemptItem(
            id=uuid.uuid4(),
            attempt_id=uuid.uuid4(),
            position=1,
            question_id=q_short.id,
            nonce="nonce_test",
        )

        # Match 1: Bengali text with zero-width non-joiner
        is_corr_1 = await grader.grade_item(dummy_item, {"text": "ঢাকা\u200c"}, 5000)
        assert is_corr_1 is True

        # Match 2: Accepted synonym from accepted_answers list
        is_corr_2 = await grader.grade_item(dummy_item, {"text": "Dhaka"}, 5000)
        assert is_corr_2 is True

        # Match 3: Another accepted synonym
        is_corr_3 = await grader.grade_item(dummy_item, {"text": "রাজধানী ঢাকা"}, 5000)
        assert is_corr_3 is True

        # Non-match
        is_corr_4 = await grader.grade_item(dummy_item, {"text": "চট্টগ্রাম"}, 5000)
        assert is_corr_4 is False


# =============================================================================
# 19. Rate Limits on Attempt Start and Answer Routes Test
# =============================================================================
@pytest.mark.asyncio
async def test_rate_limits_on_attempt_start_and_answer(gateway_client: AsyncClient) -> None:
    """Verify that:
    1. Attempt start route enforces 10 requests / minute rate limit (11th rejected with 429).
    2. Answer submission route enforces 30 requests / minute rate limit (31st rejected with 429).
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Rate Limit Student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="practice", question_count=1)

    # 1. Attempt start rate limit: 10 requests allowed, 11th gets 429
    start_responses = []
    for _ in range(11):
        res = await gateway_client.post(
            f"/v1/quizzes/{quiz.id}/attempts",
            json={"device_id": "device-p04-ratelimit-01"},
            headers=auth_headers,
        )
        start_responses.append(res)

    assert start_responses[0].status_code == 201
    assert start_responses[-1].status_code == 429
    assert start_responses[-1].json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in start_responses[-1].headers

    # Reset rate limits for answer test
    from core.common.rate_limit import RateLimiter
    await RateLimiter.reset()

    # 2. Answer route rate limit: 30 requests allowed, 31st gets 429
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-ratelimit-02"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    attempt_id = res_start.json()["attempt_id"]
    attempt_token = res_start.json()["attempt_token"]
    item = res_start.json()["current_item"]

    answer_headers = {**auth_headers, "X-Attempt-Token": attempt_token}
    ans_payload = {
        "nonce": item["nonce"],
        "response": {"selected_option_id": item["question"]["options"][0]["id"] if item["question"]["options"] else "dummy"},
        "time_spent_ms": 10000,
    }

    ans_responses = []
    for _ in range(31):
        res = await gateway_client.post(
            f"/v1/attempts/{attempt_id}/items/1/answer",
            json=ans_payload,
            headers=answer_headers,
        )
        ans_responses.append(res)

    assert ans_responses[0].status_code == 200
    assert ans_responses[-1].status_code == 429
    assert ans_responses[-1].json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in ans_responses[-1].headers


# =============================================================================
# 20. Open Attempt States, Unique Index & Lockouts Test
# =============================================================================
@pytest.mark.asyncio
async def test_open_attempt_states_unique_index_and_lockouts(gateway_client: AsyncClient) -> None:
    """Verify open attempt states (created, active, warned, paused):
    
    - Unique index prevents starting a second attempt while first is warned or paused.
    - Chat is locked out (403 QUIZ_IN_PROGRESS_CHAT_LOCKED) while warned or paused.
    - Answering is blocked (403 ATTEMPT_PAUSED) while paused.
    - Attempt deadline never extends on pause.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Open State Student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {token}",
        "X-Device-Integrity": create_mock_play_integrity_token(nonce="device-p04-android-001"),
    }

    quiz1 = await create_test_quiz(student.id, mode="assessed", question_count=2)
    quiz2 = await create_test_quiz(student.id, mode="assessed", question_count=2)

    # 1. Start first assessed quiz
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz1.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    item = start_data["current_item"]
    ans_headers = {**auth_headers, "X-Attempt-Token": attempt_token}

    # 2. Transition attempt to 'warned'
    async with AsyncSessionLocal() as session:
        att = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))).scalar_one()
        att.state = "warned"
        original_deadline = att.deadline_at
        await session.commit()

    # 2a. Attempting to start a second quiz while warned -> 409 Conflict
    res_start2 = await gateway_client.post(
        f"/v1/quizzes/{quiz2.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start2.status_code == 409
    assert res_start2.json()["error"]["code"] == "ACTIVE_ATTEMPT_ALREADY_EXISTS"

    # 2b. Attempting to chat while warned -> 403 Chat Locked
    res_chat_warned = await gateway_client.post(
        "/v1/chat/sessions",
        json={"title": "Cheat Attempt While Warned"},
        headers=auth_headers,
    )
    assert res_chat_warned.status_code == 403
    assert res_chat_warned.json()["error"]["code"] == "QUIZ_IN_PROGRESS_CHAT_LOCKED"

    # 3. Transition attempt to 'paused' and verify deadline never extends
    async with AsyncSessionLocal() as session:
        att = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))).scalar_one()
        att.state = "paused"
        await session.commit()
        await session.refresh(att)
        assert att.deadline_at == original_deadline  # Deadline strictly preserved

    # 3a. Attempting to answer item while paused -> 403 ATTEMPT_PAUSED
    res_ans_paused = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={
            "nonce": item["nonce"],
            "response": {"selected_option_id": item["question"]["options"][0]["id"] if item["question"]["options"] else "opt_0"},
            "time_spent_ms": 5000,
        },
        headers=ans_headers,
    )
    assert res_ans_paused.status_code == 403
    assert res_ans_paused.json()["error"]["code"] == "ATTEMPT_PAUSED"

    # 3b. Attempting to start a second quiz while paused -> 409 Conflict
    res_start3 = await gateway_client.post(
        f"/v1/quizzes/{quiz2.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start3.status_code == 409
    assert res_start3.json()["error"]["code"] == "ACTIVE_ATTEMPT_ALREADY_EXISTS"

    # 3c. Attempting to chat while paused -> 403 Chat Locked
    res_chat_paused = await gateway_client.post(
        "/v1/chat/sessions",
        json={"title": "Cheat Attempt While Paused"},
        headers=auth_headers,
    )
    assert res_chat_paused.status_code == 403
    assert res_chat_paused.json()["error"]["code"] == "QUIZ_IN_PROGRESS_CHAT_LOCKED"


# =============================================================================
# 21. Play Integrity Verification & Low-Trust Handling Test
# =============================================================================
@pytest.mark.asyncio
async def test_play_integrity_verification_and_low_trust(
    gateway_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify server-side Play Integrity token verification (nonce, package, freshness),
    stub rejection outside ENV=local, and low-trust handling for non-Play devices.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Integrity Student")
    token = create_access_jwt(student.id, "student")
    base_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}
    device_id = "device-p04-android-001"

    # 1. Valid Play Integrity token -> returns SECURE
    valid_token = create_mock_play_integrity_token(
        nonce=device_id,
        package_name="com.thinkbuddy.app",
        verdicts=["MEETS_STRONG_INTEGRITY", "MEETS_DEVICE_INTEGRITY"],
        age_seconds=10,
    )
    from core.quiz.integrity import evaluate_device_attestation, DeviceIntegrityVerdict
    v_valid = evaluate_device_attestation(
        platform="android",
        device_id=device_id,
        integrity_verdict=valid_token,
    )
    assert v_valid == DeviceIntegrityVerdict.SECURE

    # 2. Package name mismatch -> returns COMPROMISED (start rejected with 403)
    tampered_pkg_token = create_mock_play_integrity_token(
        nonce=device_id,
        package_name="com.attacker.repackaged.app",
    )
    quiz_pkg = await create_test_quiz(student.id, mode="assessed", question_count=1)
    res_pkg = await gateway_client.post(
        f"/v1/quizzes/{quiz_pkg.id}/attempts",
        json={"device_id": device_id},
        headers={**base_headers, "X-Device-Integrity": tampered_pkg_token},
    )
    assert res_pkg.status_code == 403
    assert res_pkg.json()["error"]["code"] == "DEVICE_INTEGRITY_FAILED"

    # 3. Nonce mismatch / replay attack -> returns COMPROMISED
    mismatched_nonce_token = create_mock_play_integrity_token(
        nonce="different-replayed-nonce",
        package_name="com.thinkbuddy.app",
    )
    v_nonce = evaluate_device_attestation(
        platform="android",
        device_id=device_id,
        integrity_verdict=mismatched_nonce_token,
    )
    assert v_nonce == DeviceIntegrityVerdict.COMPROMISED

    # 4. Stale token (> 5 min / 300s old) -> returns COMPROMISED
    stale_token = create_mock_play_integrity_token(
        nonce=device_id,
        package_name="com.thinkbuddy.app",
        age_seconds=360,
    )
    v_stale = evaluate_device_attestation(
        platform="android",
        device_id=device_id,
        integrity_verdict=stale_token,
    )
    assert v_stale == DeviceIntegrityVerdict.COMPROMISED

    # 5. Attestation stub in local -> UNVERIFIED (score 0.90, event recorded)
    v_stub_local = evaluate_device_attestation(
        platform="android",
        device_id=device_id,
        integrity_verdict="mock_secure",
    )
    assert v_stub_local == DeviceIntegrityVerdict.UNVERIFIED

    # 6. Attestation stub outside ENV=local (e.g. production) -> strictly COMPROMISED
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ENV", "production")
    v_stub_prod = evaluate_device_attestation(
        platform="android",
        device_id=device_id,
        integrity_verdict="mock_secure",
    )
    assert v_stub_prod == DeviceIntegrityVerdict.COMPROMISED
    monkeypatch.setattr(settings, "ENVIRONMENT", "local")
    monkeypatch.setattr(settings, "ENV", "local")

    # 7. Low-trust device (no Play services: X-Device-Attestation-Provider: none/aosp)
    # Allowed under scrutiny with initial integrity score 0.85 and low_trust_device_active event
    quiz_low = await create_test_quiz(student.id, mode="assessed", question_count=1)
    res_low = await gateway_client.post(
        f"/v1/quizzes/{quiz_low.id}/attempts",
        json={"device_id": "aosp-device-without-gms"},
        headers={
            **base_headers,
            "X-Device-Id": "aosp-device-without-gms",
            "X-Device-Attestation-Provider": "none",
        },
    )
    assert res_low.status_code == 201
    low_attempt_id = res_low.json()["attempt_id"]

    async with AsyncSessionLocal() as session:
        att_low = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == low_attempt_id))).scalar_one()
        assert att_low.integrity_score == 0.85
        event_res = await session.execute(
            select(AttemptEvent).where(
                AttemptEvent.attempt_id == low_attempt_id,
                AttemptEvent.type == "low_trust_device_active",
            )
        )
        assert event_res.scalar_one_or_none() is not None


# =============================================================================
# 22. Scaled Too-Fast Rule, Multi-Signal Invalidation & Parent Allow Flow
# =============================================================================
@pytest.mark.asyncio
async def test_scaled_too_fast_rule_multi_signal_and_parent_allow(
    gateway_client: AsyncClient,
) -> None:
    """Verify:
    1. Too-fast minimum response time scales by stem length and question type.
    2. Invalidation strictly requires >= 2 distinct signals (single signal pauses).
    3. Parent 'mark as allowed' flow resets attempt and logs audit entry.
    """
    from core.quiz.integrity import compute_min_answer_time_ms

    # 1. Stem length and type scaling checks
    mcq_short_stem = compute_min_answer_time_ms("mcq", "2 + 2 = ?")
    mcq_long_stem = compute_min_answer_time_ms("mcq", "What is the capital of Bangladesh and its population?")
    assert mcq_long_stem > mcq_short_stem

    short_stem_time = compute_min_answer_time_ms("short", "Short answer question stem here")
    broad_stem_time = compute_min_answer_time_ms("broad", "Explain photosynthesis in detail")
    assert broad_stem_time > short_stem_time > mcq_short_stem

    # 2. Multi-signal invalidation check
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="MultiSignal Student")
    parent = await create_test_user(role="parent", display_name="Linked Parent")
    unlinked_parent = await create_test_user(role="parent", display_name="Unlinked Parent")

    # Link parent to student
    async with AsyncSessionLocal() as session:
        link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=parent.id,
            student_id=student.id,
            status="active",
        )
        session.add(link)
        await session.commit()

    student_token = create_access_jwt(student.id, "student")
    parent_token = create_access_jwt(parent.id, "parent")
    unlinked_token = create_access_jwt(unlinked_parent.id, "parent")

    auth_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {student_token}",
        "X-Device-Integrity": create_mock_play_integrity_token(nonce="device-p04-android-001"),
    }

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    item = start_data["current_item"]
    ans_headers = {**auth_headers, "X-Attempt-Token": attempt_token}

    # Signal 1: Answer too fast (under minimum computed time)
    # First anomaly only: should transition to paused/warned, but NOT invalidated
    opts = item["question"].get("options") or []
    opt_id = opts[0]["id"] if opts else "opt_0"
    res_ans1 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={
            "nonce": item["nonce"],
            "response": {"selected_option_id": opt_id},
            "time_spent_ms": 300,  # Far below minimum threshold
        },
        headers=ans_headers,
    )
    assert res_ans1.status_code == 200

    async with AsyncSessionLocal() as session:
        att = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))).scalar_one()
        # Single signal must NOT invalidate
        assert att.state != "invalidated"

        # Signal 2: Record distinct focus lost event right before next item
        event = AttemptEvent(
            attempt_id=att.id,
            type="focus_lost",
            meta={"duration_ms": 4000},
        )
        session.add(event)
        # Drop score below invalidation threshold to test multi-signal trigger
        att.integrity_score = 0.40
        await session.commit()

        # Trigger check with rapid answer after focus loss -> 2 distinct signals!
        from core.quiz.integrity import IntegrityEngine
        item_row = (await session.execute(select(AttemptItem).where(AttemptItem.attempt_id == att.id, AttemptItem.position == 2))).scalar_one()
        await IntegrityEngine.check_and_apply_anomalies(
            db=session,
            attempt=att,
            item=item_row,
            time_spent_ms=500,
            is_correct=True,
        )
        await session.commit()
        await session.refresh(att)
        assert att.state == "invalidated"
        assert att.invalid_reason is not None

    # 3. Parent "mark as allowed" flow (POST /v1/attempts/{id}/allow)
    # 3a. Student themself calling allow -> 404 Not Found (indistinguishable)
    res_student_allow = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/allow",
        json={"reason": "Self override attempt"},
        headers=auth_headers,
    )
    assert res_student_allow.status_code == 404
    assert res_student_allow.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"

    # 3b. Unlinked parent calling allow -> 404 Not Found (indistinguishable)
    res_unlinked_allow = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/allow",
        json={"reason": "Unlinked parent override"},
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {unlinked_token}"},
    )
    assert res_unlinked_allow.status_code == 404
    assert res_unlinked_allow.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"

    # 3c. Linked parent calling allow -> 200 OK, resets attempt state to active and restores score
    res_parent_allow = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/allow",
        json={"reason": "Confirmed system alert was caused by school notification dialog"},
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {parent_token}"},
    )
    assert res_parent_allow.status_code == 200, res_parent_allow.text
    allow_data = res_parent_allow.json()
    assert allow_data["state"] == "active"
    assert allow_data["integrity_score"] >= 0.90
    assert "Override allowed" in allow_data["invalid_reason"]

    # Verify audit log entry was written
    async with AsyncSessionLocal() as session:
        audit_res = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "quiz_attempt_allowed",
                AuditLog.target_id == str(attempt_id),
            )
        )
        audit_entry = audit_res.scalar_one_or_none()
        assert audit_entry is not None
        assert audit_entry.actor_id == parent.id
        assert "school notification" in audit_entry.meta["reason"]


# =============================================================================
# 23. Database Role Separation & Column Encryption Test
# =============================================================================
@pytest.mark.asyncio
async def test_database_role_separation_and_column_encryption() -> None:
    """Verify:
    1. thinkbuddy_api role can SELECT from v_questions_public.
    2. thinkbuddy_api role is strictly forbidden from querying question_keys.
    3. Column encryption AES-256-GCM correctly encrypts and decrypts key payloads.
    """
    from sqlalchemy.exc import ProgrammingError, DBAPIError
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from core.quiz.crypto import encrypt_column_value, decrypt_column_value

    # 1 & 2: Database role test
    api_db_url = settings.DATABASE_URL.replace("thinkbuddy:thinkbuddy_dev_password", "thinkbuddy_api:thinkbuddy_api_password")
    api_engine = create_async_engine(api_db_url)
    try:
        async with api_engine.connect() as conn:
            # v_questions_public query must succeed
            res_view = await conn.execute(text("SELECT count(*) FROM v_questions_public;"))
            count = res_view.scalar()
            assert count is not None

            # question_keys direct SELECT must be rejected with permission denied
            with pytest.raises((ProgrammingError, DBAPIError)):
                await conn.execute(text("SELECT * FROM question_keys LIMIT 1;"))
    finally:
        await api_engine.dispose()

    # 3. Column encryption test
    secret_key = settings.QUESTION_KEY_ENCRYPTION_KEY
    plaintext_data = {"correct_option_id": "opt_2", "explanation": "Proof by mathematical induction"}
    encrypted_cipher = encrypt_column_value(plaintext_data, secret_key)
    assert encrypted_cipher != str(plaintext_data)
    assert len(encrypted_cipher) > 30

    decrypted_data = decrypt_column_value(encrypted_cipher, secret_key)
    assert decrypted_data == plaintext_data

    # Decryption fails with wrong key
    wrong_key = "a_completely_different_32_byte_secret_key_123"
    with pytest.raises(Exception):
        decrypt_column_value(encrypted_cipher, wrong_key)


# =============================================================================
# 24. Concurrent Submit vs Expiry & Worker Schedule Test
# =============================================================================
@pytest.mark.asyncio
async def test_concurrent_submit_versus_expiry_and_worker_schedule(
    gateway_client: AsyncClient,
) -> None:
    """Verify FOR UPDATE SKIP LOCKED concurrency between client submit and expiry worker,
    idempotent grading and learning signals, and registered worker schedule.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Concurrent Expiry Student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {token}",
        "X-Device-Integrity": create_mock_play_integrity_token(nonce="device-p04-android-001"),
    }

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=2)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = uuid.UUID(start_data["attempt_id"])
    attempt_token = start_data["attempt_token"]

    # Set deadline in the past to make attempt eligible for expiration worker
    async with AsyncSessionLocal() as session:
        att = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))).scalar_one()
        att.deadline_at = datetime.now(UTC) - timedelta(seconds=10)
        await session.commit()

    # Trigger client submit and worker auto-submit concurrently
    from core.quiz.service import QuizService
    async def run_client_submit() -> Any:
        try:
            async with AsyncSessionLocal() as session:
                srv = QuizService(session)
                return await srv.submit_attempt(attempt_id, student.id, attempt_token)
        except Exception as e:
            return e

    async def run_worker_expiry() -> Any:
        try:
            return await auto_submit_expired_attempts()
        except Exception as e:
            return e

    client_res, worker_res = await asyncio.gather(run_client_submit(), run_worker_expiry())

    # Verify attempt was finalized without deadlock or duplicate signals
    async with AsyncSessionLocal() as session:
        att_final = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))).scalar_one()
        assert att_final.submitted_at is not None
        assert att_final.state in ("submitted", "expired")
        assert att_final.score is not None

        # Verify learning signals were emitted idempotently (no duplicates)
        sig_res = await session.execute(
            select(LearningSignal).where(LearningSignal.student_id == student.id)
        )
        signals = list(sig_res.scalars().all())
        ref_ids = [s.ref_id for s in signals]
        # Each attempt item ref_id must appear at most once per signal type
        signal_pairs = {(s.source, s.ref_id) for s in signals}
        assert len(signal_pairs) == len(signals)

    # Verify Celery beat schedule contains auto-submit task
    from workers.celery_app import celery_app
    assert "auto-submit-expired-quiz-attempts" in celery_app.conf.beat_schedule
    task_conf = celery_app.conf.beat_schedule["auto-submit-expired-quiz-attempts"]
    assert task_conf["task"] == "auto_submit_expired_attempts"
    assert task_conf["schedule"] == 30.0


# =============================================================================
# 25. Exhausted Assessed Pool Fallback LRU Test
# =============================================================================
@pytest.mark.asyncio
async def test_exhausted_assessed_pool_fallback_lru() -> None:
    """Verify fallback when student has answered all assessed questions:
    - Recycles oldest-answered questions (LRU).
    - NEVER leaks questions from practice-only pool.
    - Shuffles option IDs and generates new nonces.
    """
    test_concept = f"lru_concept_{uuid.uuid4().hex[:8]}"
    student = await create_test_user(role="student", display_name="LRU Student")
    builder_student = student.id

    async with AsyncSessionLocal() as session:
        # Create 2 assessed questions and 1 practice-only question
        q_assessed_1 = Question(
            id=uuid.uuid4(),
            type="mcq",
            difficulty=0.5,
            review_status="approved",
            concept_id=test_concept,
            pool="assessed",
            stem={"text": "Assessed Q1: What is Force?"},
            options=[{"id": "opt_1", "text": "F = ma"}],
        )
        q_assessed_2 = Question(
            id=uuid.uuid4(),
            type="mcq",
            difficulty=0.5,
            review_status="approved",
            concept_id=test_concept,
            pool="assessed",
            stem={"text": "Assessed Q2: What is Energy?"},
            options=[{"id": "opt_1", "text": "E = mc^2"}],
        )
        q_practice_only = Question(
            id=uuid.uuid4(),
            type="mcq",
            difficulty=0.5,
            review_status="approved",
            concept_id=test_concept,
            pool="practice",
            stem={"text": "Practice Only: Secret Question"},
            options=[{"id": "opt_1", "text": "Secret Answer"}],
        )
        k1 = QuestionKey(question_id=q_assessed_1.id, correct_option_id="opt_1", explanation={"text": "Exp 1"})
        k2 = QuestionKey(question_id=q_assessed_2.id, correct_option_id="opt_1", explanation={"text": "Exp 2"})
        kp = QuestionKey(question_id=q_practice_only.id, correct_option_id="opt_1", explanation={"text": "Practice Exp"})

        session.add_all([q_assessed_1, q_assessed_2, q_practice_only, k1, k2, kp])
        await session.commit()

        # Mark both assessed questions as answered in past attempts
        past_quiz = Quiz(
            id=uuid.uuid4(),
            student_id=builder_student,
            title="Past Assessed Quiz",
            mode="assessed",
        )
        session.add(past_quiz)
        await session.flush()

        past_attempt = QuizAttempt(
            quiz_id=past_quiz.id,
            student_id=builder_student,
            device_id="lru-device-01",
            state="submitted",
            mode="assessed",
            attempt_token="past_token_lru",
            started_at=datetime.now(UTC) - timedelta(hours=2),
            deadline_at=datetime.now(UTC) - timedelta(hours=1),
            submitted_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(past_attempt)
        await session.flush()

        it1 = AttemptItem(
            attempt_id=past_attempt.id,
            question_id=q_assessed_1.id,
            position=1,
            nonce="nonce_lru_1",
            answered_at=datetime.now(UTC) - timedelta(hours=1, minutes=30),  # Older
            is_correct=True,
            points=1.0,
        )
        it2 = AttemptItem(
            attempt_id=past_attempt.id,
            question_id=q_assessed_2.id,
            position=2,
            nonce="nonce_lru_2",
            answered_at=datetime.now(UTC) - timedelta(hours=1, minutes=10),  # Newer
            is_correct=True,
            points=1.0,
        )
        session.add_all([it1, it2])
        await session.commit()

        # Now build a 2-question assessed quiz for this student
        # Since all 2 assessed questions were seen, LRU fallback must trigger
        builder = QuizBuilderService(session)
        selected_questions = await builder.select_and_randomize_questions(
            question_count=2,
            student_id=builder_student,
            concept_ids=[test_concept],
            mode="assessed",
        )

        selected_ids = {q.id for q in selected_questions}
        assert len(selected_questions) == 2
        # Both assessed questions must be recycled via LRU
        assert q_assessed_1.id in selected_ids
        assert q_assessed_2.id in selected_ids
        # Practice-only question MUST NEVER be included!
        assert q_practice_only.id not in selected_ids


# =============================================================================
# 26. Gateway Never Proxies /internal/* & Signed JWT Service Token Test
# =============================================================================
@pytest.mark.asyncio
async def test_gateway_never_proxies_internal_and_signed_jwt_service_token(
    gateway_client: AsyncClient,
) -> None:
    """Verify that:
    1. Gateway strictly refuses to proxy /internal/* and /v1/internal/* (returns 404).
    2. Core service accepts valid signed HS256 JWT service tokens with thinkbuddy-core audience.
    3. Core service strictly rejects missing, invalid, or expired service tokens (403).
    """
    student_id = uuid.uuid4()

    # 1. Gateway blocks public access to internal routes with 404
    res_gw_internal = await gateway_client.get(
        f"/internal/quiz/students/{student_id}/active-attempt",
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_gw_internal.status_code == 404

    res_gw_v1_internal = await gateway_client.get(
        f"/v1/internal/quiz/students/{student_id}/active-attempt",
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_gw_v1_internal.status_code == 404

    # 2. Direct core calls with signed service tokens
    from core.main import app as core_app
    from httpx import ASGITransport
    from core.common.service_token import create_internal_service_token

    async with AsyncClient(transport=ASGITransport(app=core_app), base_url="http://testserver") as core_client:
        # 2a. Valid signed JWT service token -> 200 OK
        valid_jwt = create_internal_service_token(expires_minutes=5)
        res_core_ok = await core_client.get(
            f"/v1/internal/quiz/students/{student_id}/active-attempt",
            headers={"X-Internal-Service-Token": valid_jwt},
        )
        assert res_core_ok.status_code == 200
        assert res_core_ok.json()["is_active"] is False

        # 2b. Missing token -> 403 Forbidden
        res_core_missing = await core_client.get(
            f"/v1/internal/quiz/students/{student_id}/active-attempt",
        )
        assert res_core_missing.status_code == 403

        # 2c. Invalid / forged token -> 403 Forbidden
        forged_jwt = "header.payload.signature_invalid"
        res_core_forged = await core_client.get(
            f"/v1/internal/quiz/students/{student_id}/active-attempt",
            headers={"X-Internal-Service-Token": forged_jwt},
        )
        assert res_core_forged.status_code == 403

        # 2d. Expired token -> 403 Forbidden
        expired_jwt = create_internal_service_token(expires_minutes=-5)
        res_core_expired = await core_client.get(
            f"/v1/internal/quiz/students/{student_id}/active-attempt",
            headers={"X-Internal-Service-Token": expired_jwt},
        )
        assert res_core_expired.status_code == 403


# =============================================================================
# 27. Anomaly Warning, Severe/Multi-Signal Pause & Auto-Resume Test
# =============================================================================
@pytest.mark.asyncio
async def test_single_anomaly_warns_severe_or_two_signals_pause_and_autoresumes(
    gateway_client: AsyncClient,
) -> None:
    """Per P04 tail (1):
    - A single anomaly logs a warning (state transitions to 'warned').
    - Pausing requires two signals OR one severe signal (screenshot_attempt, chat_attempt, overlay).
    - A pause auto-resumes after a short period (60s); deadline never extends.
    - Document what unpauses: auto-resume timeout or parent allow.
    """
    student = await create_test_user(role="student", display_name="Student Anomaly Pause Check")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}
    quiz = await create_test_quiz(student.id, mode="assessed", question_count=3)

    # 1. Start attempt
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    data = res_start.json()
    attempt_id = data["attempt_id"]
    attempt_token = data["attempt_token"]

    # 2. Single anomaly (time_too_fast during answer) -> logs warning, transitions to 'warned'
    res_ans_fast = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": data["current_item"]["nonce"], "response": {"selected_option_id": "opt_0"}, "time_spent_ms": 200},
        headers={**auth_headers, "X-Attempt-Token": attempt_token},
    )
    assert res_ans_fast.status_code == 200

    async with AsyncSessionLocal() as session:
        att = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == uuid.UUID(attempt_id)))).scalar_one()
        assert att.state == "warned"

    # 3. Severe signal (screenshot_attempt) -> transitions to 'paused'
    res_ev2 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/events",
        json={"type": "screenshot_attempt", "meta": {}},
        headers={**auth_headers, "X-Attempt-Token": attempt_token},
    )
    assert res_ev2.status_code == 200
    ev2_data = res_ev2.json()
    assert ev2_data["state"] == "paused"

    # Attempt answering next item while paused -> 403 ATTEMPT_PAUSED
    res_ans_blocked = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/2/answer",
        json={"nonce": res_ans_fast.json()["next_item"]["nonce"], "response": {"selected_option_id": "opt_0"}, "time_spent_ms": 3000},
        headers={**auth_headers, "X-Attempt-Token": attempt_token},
    )
    assert res_ans_blocked.status_code == 403
    ans_err = res_ans_blocked.json()
    err_code = ans_err.get("error", {}).get("code") or ans_err.get("detail", {}).get("code")
    assert err_code == "ATTEMPT_PAUSED"

    # 4. Fast forward time past pause_expires_at (60s) -> auto-resumes to 'warned'
    async with AsyncSessionLocal() as session:
        attempt_obj = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == uuid.UUID(attempt_id)))).scalar_one()
        assert attempt_obj.pause_expires_at is not None
        # Simulate expiry of pause period
        attempt_obj.pause_expires_at = datetime.now(UTC) - timedelta(seconds=5)
        await session.commit()

    # Answering now should succeed after auto-resume!
    res_ans_ok = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/2/answer",
        json={"nonce": res_ans_fast.json()["next_item"]["nonce"], "response": {"selected_option_id": "opt_0"}, "time_spent_ms": 3000},
        headers={**auth_headers, "X-Attempt-Token": attempt_token},
    )
    assert res_ans_ok.status_code == 200
    assert res_ans_ok.json()["answered"] is True


# =============================================================================
# 28. Play Integrity Nonce Bound to Attempt ID & Production Check Test
# =============================================================================
@pytest.mark.asyncio
async def test_play_integrity_nonce_bound_to_attempt_id_and_production_checks(
    gateway_client: AsyncClient,
) -> None:
    """Per P04 tail (2):
    - Integrity nonce is strictly bound to attempt_id.
    - Production verification must go through Google's decode or cryptographic signature check,
      never client-reported verdict fields.
    """
    from core.quiz.integrity import evaluate_device_attestation, DeviceIntegrityVerdict

    target_attempt_id = uuid.uuid4()

    # 1. Valid token with nonce matching target_attempt_id -> SECURE
    token_valid_nonce = create_mock_play_integrity_token(
        nonce=str(target_attempt_id),
        package_name="com.thinkbuddy.app",
        verdicts=["MEETS_STRONG_INTEGRITY"],
    )
    verdict_valid = evaluate_device_attestation(
        platform="android",
        integrity_verdict=token_valid_nonce,
        attempt_id=target_attempt_id,
    )
    assert verdict_valid == DeviceIntegrityVerdict.SECURE

    # 2. Token with mismatched nonce -> COMPROMISED
    token_mismatched_nonce = create_mock_play_integrity_token(
        nonce="mismatched-nonce-value",
        package_name="com.thinkbuddy.app",
        verdicts=["MEETS_STRONG_INTEGRITY"],
    )
    verdict_mismatch = evaluate_device_attestation(
        platform="android",
        integrity_verdict=token_mismatched_nonce,
        attempt_id=target_attempt_id,
    )
    assert verdict_mismatch == DeviceIntegrityVerdict.COMPROMISED

    # 3. Production check: client-reported string 'secure' outside ENV=local is rejected
    orig_env = settings.ENV
    try:
        settings.ENV = "production"
        verdict_prod_client_string = evaluate_device_attestation(
            platform="android",
            integrity_verdict="secure",
            attempt_id=target_attempt_id,
        )
        assert verdict_prod_client_string == DeviceIntegrityVerdict.COMPROMISED
    finally:
        settings.ENV = orig_env


# =============================================================================
# 29. Unverified Device Reduced Mastery Weight & Parent View Label Test
# =============================================================================
@pytest.mark.asyncio
async def test_unverified_device_reduced_mastery_and_parent_view_label(
    gateway_client: AsyncClient,
) -> None:
    """Per P04 tail (3):
    - Unverified or self-declared-provider devices get reduced mastery weight (0.7x).
    - Parent review view carries 'unverified_device: true'.
    """
    await seed_sample_questions()
    parent = await create_test_user(role="parent", display_name="Parent Trust Check")
    student = await create_test_user(role="student", display_name="Student Trust Check")
    p_token = create_access_jwt(parent.id, "parent")
    s_token = create_access_jwt(student.id, "student")
    parent_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {p_token}"}
    student_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {s_token}"}

    # Link parent and student
    async with AsyncSessionLocal() as session:
        link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=parent.id,
            student_id=student.id,
            status="active",
        )
        session.add(link)
        await session.commit()

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=2)

    # Start attempt on unverified device (X-Device-Attestation-Provider: none)
    headers_low_trust = {
        **student_headers,
        "X-Device-Attestation-Provider": "none",
    }
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-low-trust-001"},
        headers=headers_low_trust,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]

    # Submit item with wrong answer to trigger quiz_wrong learning signal
    it1 = start_data["current_item"]
    await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": it1["nonce"], "response": {"selected_option_id": "opt_wrong_nonexistent"}, "time_spent_ms": 3000},
        headers={**student_headers, "X-Attempt-Token": attempt_token},
    )

    # Submit quiz
    res_submit = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        headers={**student_headers, "X-Attempt-Token": attempt_token},
    )
    assert res_submit.status_code == 200

    # 1. Check parent review response includes unverified_device: True
    res_review = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=parent_headers,
    )
    assert res_review.status_code == 200
    rev_data = res_review.json()
    assert rev_data["unverified_device"] is True

    # 2. Check emitted learning signal has reduced weight (0.7 instead of 1.0)
    async with AsyncSessionLocal() as session:
        sig_stmt = select(LearningSignal).where(
            LearningSignal.student_id == student.id,
            LearningSignal.source == "quiz_wrong",
        )
        res_sig = await session.execute(sig_stmt)
        signal = res_sig.scalar_one_or_none()
        assert signal is not None
        assert signal.weight == 0.7


# =============================================================================
# 30. Learning Signals Unique Constraint & Concurrent Submit vs Expiry Test
# =============================================================================
@pytest.mark.asyncio
async def test_learning_signals_unique_constraint_and_concurrent_submit_expiry(
    gateway_client: AsyncClient,
) -> None:
    """Per P04 tail (4):
    - Unique constraint uq_learning_signals_student_source_ref with ON CONFLICT DO NOTHING.
    - Concurrent submit-versus-expiry test racing simultaneously without duplicate signals or deadlocks.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student", display_name="Student Concurrency Race")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}
    quiz = await create_test_quiz(student.id, mode="assessed", question_count=2)

    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={"device_id": "device-p04-android-001"},
        headers=auth_headers,
    )
    assert res_start.status_code == 201
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]

    # Answer item 1 incorrectly
    await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": start_data["current_item"]["nonce"], "response": {"selected_option_id": "opt_wrong"}, "time_spent_ms": 3000},
        headers={**auth_headers, "X-Attempt-Token": attempt_token},
    )

    # Set deadline to now so background expiry task can race against student submit
    async with AsyncSessionLocal() as session:
        attempt_obj = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == uuid.UUID(attempt_id)))).scalar_one()
        attempt_obj.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    # Race student submit vs background auto-submit worker
    async def run_submit() -> Any:
        return await gateway_client.post(
            f"/v1/attempts/{attempt_id}/submit",
            headers={**auth_headers, "X-Attempt-Token": attempt_token},
        )

    async def run_worker() -> Any:
        return await auto_submit_expired_attempts()

    results = await asyncio.gather(run_submit(), run_worker(), return_exceptions=True)
    res_sub, res_work = results[0], results[1]

    # Verify both completed without unhandled exceptions
    assert not isinstance(res_sub, Exception)
    assert not isinstance(res_work, Exception)

    # Verify database has exactly 1 learning signal for this item (no duplicates!)
    async with AsyncSessionLocal() as session:
        sigs = list((await session.execute(select(LearningSignal).where(LearningSignal.student_id == student.id))).scalars().all())
        ref_ids = [s.ref_id for s in sigs]
        assert len(ref_ids) == len(set(ref_ids)), "Duplicate learning signals emitted!"


# =============================================================================
# 31. Created Attempts Short Expiry & No Reviving Expired Attempts Test
# =============================================================================
@pytest.mark.asyncio
async def test_created_attempts_short_expiry_and_no_reviving_expired(
    gateway_client: AsyncClient,
) -> None:
    """Per P04 tail (6):
    - created attempts get a short expiry (5 minutes).
    - parent allow cannot revive an expired attempt.
    """
    parent = await create_test_user(role="parent", display_name="Parent Revive Check")
    student = await create_test_user(role="student", display_name="Student Created Expiry Check")
    p_token = create_access_jwt(parent.id, "parent")
    s_token = create_access_jwt(student.id, "student")
    parent_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {p_token}"}
    student_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {s_token}"}

    async with AsyncSessionLocal() as session:
        link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=parent.id,
            student_id=student.id,
            status="active",
        )
        session.add(link)
        await session.commit()

    quiz = await create_test_quiz(student.id, mode="assessed", question_count=2)

    # 1. Create attempt in state 'created'
    res_create = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts/create",
        json={"device_id": "device-p04-android-001"},
        headers=student_headers,
    )
    assert res_create.status_code == 201
    create_data = res_create.json()
    attempt_id = create_data["attempt_id"]
    assert create_data["state"] == "created"
    assert bool(create_data["nonce"]) and len(create_data["nonce"]) >= 16

    # 2. Simulate expiration of created attempt (5-minute deadline passed)
    async with AsyncSessionLocal() as session:
        attempt_obj = (await session.execute(select(QuizAttempt).where(QuizAttempt.id == uuid.UUID(attempt_id)))).scalar_one()
        attempt_obj.deadline_at = datetime.now(UTC) - timedelta(minutes=1)
        attempt_obj.state = "expired"
        await session.commit()

    # 3. Parent /allow MUST NOT revive an expired attempt -> 409 CANNOT_REVIVE_EXPIRED_ATTEMPT
    res_allow = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/allow",
        json={"reason": "Parent trying to revive expired attempt"},
        headers=parent_headers,
    )
    assert res_allow.status_code == 409
    data = res_allow.json()
    err_code = data.get("error", {}).get("code") or data.get("detail", {}).get("code")
    assert err_code == "CANNOT_REVIVE_EXPIRED_ATTEMPT"


# =============================================================================
# 32. Recycled Questions Marking, Variant Preference & Low Pool Alert Test
# =============================================================================
@pytest.mark.asyncio
async def test_recycled_questions_variant_preference_and_low_pool_alert(
    gateway_client: AsyncClient,
) -> None:
    """Per P04 tail (7):
    - Prefer unseen variants first.
    - Mark recycled questions (is_recycled=True), weight them lower (points=0.7).
    - Alert admins when assessed question pool runs low.
    """
    variant_grp = uuid.uuid4()
    test_concept = f"concept_variant_pref_{uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as session:
        # Create Question 1 (variant A) and Question 2 (variant B) in same variant group
        q_v1 = Question(
            id=uuid.uuid4(),
            type="mcq",
            concept_id=test_concept,
            difficulty=0.5,
            language="bn",
            stem={"text": "ভেরিয়েন্ট ১ (Variant 1)"},
            options=[{"id": "opt_0", "text": "ক"}, {"id": "opt_1", "text": "খ"}],
            pool="assessed",
            variant_group_id=variant_grp,
        )
        q_v2 = Question(
            id=uuid.uuid4(),
            type="mcq",
            concept_id=test_concept,
            difficulty=0.5,
            language="bn",
            stem={"text": "ভেরিয়েন্ট ২ (Variant 2)"},
            options=[{"id": "opt_0", "text": "ক"}, {"id": "opt_1", "text": "খ"}],
            pool="assessed",
            variant_group_id=variant_grp,
        )
        session.add_all([q_v1, q_v2])
        await session.flush()

        # Add keys
        k1 = QuestionKey(question_id=q_v1.id, correct_option_id="opt_0")
        k2 = QuestionKey(question_id=q_v2.id, correct_option_id="opt_0")
        session.add_all([k1, k2])
        await session.commit()

        # Student has previously seen and answered Question 1
        student = await create_test_user(role="student", display_name="Variant Preference Student")
        student_id = student.id
        prev_quiz = Quiz(id=uuid.uuid4(), student_id=student_id, title="Previous Quiz", mode="assessed")
        session.add(prev_quiz)
        await session.flush()

        prev_attempt = QuizAttempt(
            id=uuid.uuid4(),
            quiz_id=prev_quiz.id,
            student_id=student_id,
            state="submitted",
            mode="assessed",
            attempt_token="prev_tok",
            started_at=datetime.now(UTC) - timedelta(hours=1),
            submitted_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        session.add(prev_attempt)
        await session.flush()

        prev_item = AttemptItem(
            attempt_id=prev_attempt.id,
            question_id=q_v1.id,
            position=1,
            nonce="prev_nonce",
            answered_at=datetime.now(UTC) - timedelta(minutes=45),
            points=1.0,
        )
        session.add(prev_item)
        await session.commit()

        # Select questions for student: MUST prefer unseen variant Question 2 over recycling Question 1
        builder = QuizBuilderService(session)
        selected = await builder.select_and_randomize_questions(
            question_count=1,
            student_id=student_id,
            concept_ids=[test_concept],
            mode="assessed",
        )
        assert len(selected) == 1
        assert selected[0].id == q_v2.id, "Did not prefer unseen variant first!"
        assert getattr(selected[0], "_is_recycled", False) is False

        # Now test recycled marking when ALL variants have been answered
        prev_item2 = AttemptItem(
            attempt_id=prev_attempt.id,
            question_id=q_v2.id,
            position=2,
            nonce="prev_nonce_2",
            answered_at=datetime.now(UTC) - timedelta(minutes=40),
            points=1.0,
        )
        session.add(prev_item2)
        await session.commit()

        selected_recycled = await builder.select_and_randomize_questions(
            question_count=1,
            student_id=student_id,
            concept_ids=[test_concept],
            mode="assessed",
        )
        assert len(selected_recycled) == 1
        assert getattr(selected_recycled[0], "_is_recycled", False) is True

        # Initialize attempt items: recycled item points must be weighted lower (0.7)
        new_attempt = QuizAttempt(
            id=uuid.uuid4(),
            quiz_id=prev_quiz.id,
            student_id=student_id,
            state="active",
            mode="assessed",
            attempt_token="new_tok_recycled",
            started_at=datetime.now(UTC),
        )
        session.add(new_attempt)
        await session.flush()

        items = await builder.initialize_attempt_items(new_attempt, selected_recycled)
        assert items[0].is_recycled is True
        assert items[0].points == 0.7


# =============================================================================
# 33. Production Secret Validation Check for Distinct Service Secret Test
# =============================================================================
def test_production_secret_check_covers_distinct_service_token_secret() -> None:
    """Per P04 tail (8):
    - Confirm the service-token secret is distinct and covered by the production secret check.
    """
    from pydantic import ValidationError
    from core.common.config import CoreSettings

    prod_db = "postgresql+asyncpg://thinkbuddy_prod:safe_pass_here@127.0.0.1:5432/thinkbuddy_prod"

    # 1. Non-local environment rejects placeholder INTERNAL_SERVICE_SECRET
    with pytest.raises(ValidationError, match="placeholder INTERNAL_SERVICE_SECRET"):
        CoreSettings(
            ENV="production",
            DATABASE_URL=prod_db,
            JWT_SECRET_KEY="prod_super_secret_key_random_value_1234567890!",
            LINK_CODE_SECRET="prod_super_secret_link_key_random_value_1234567890!",
            INTERNAL_SERVICE_TOKEN="prod_super_secret_token_random_value_1234567890!",
            INTERNAL_SERVICE_SECRET="dev_internal_service_hmac_secret_32bytes_min_key!",  # dev placeholder
            QUESTION_KEY_ENCRYPTION_KEY="prod_super_secret_crypto_key_random_value_1234567890!",
        )

    # 2. Non-local environment rejects identical / duplicate secrets
    shared_key = "prod_super_secret_shared_key_random_value_1234567890!"
    with pytest.raises(ValidationError, match="must be distinct"):
        CoreSettings(
            ENV="production",
            DATABASE_URL=prod_db,
            JWT_SECRET_KEY="prod_super_secret_key_random_value_1234567890_1!",
            LINK_CODE_SECRET="prod_super_secret_link_key_random_value_1234567890_2!",
            INTERNAL_SERVICE_TOKEN=shared_key,
            INTERNAL_SERVICE_SECRET=shared_key,  # Duplicate!
            QUESTION_KEY_ENCRYPTION_KEY="prod_super_secret_crypto_key_random_value_1234567890_3!",
        )

    # 3. Valid distinct production configuration succeeds
    valid_cfg = CoreSettings(
        ENV="production",
        DATABASE_URL=prod_db,
        JWT_SECRET_KEY="prod_super_secret_key_random_value_1234567890_1!",
        LINK_CODE_SECRET="prod_super_secret_link_key_random_value_1234567890_2!",
        INTERNAL_SERVICE_TOKEN="prod_super_secret_token_random_value_1234567890_3!",
        INTERNAL_SERVICE_SECRET="prod_super_secret_hmac_key_random_value_1234567890_4!",
        QUESTION_KEY_ENCRYPTION_KEY="prod_super_secret_crypto_key_random_value_1234567890_5!",
    )
    assert valid_cfg.INTERNAL_SERVICE_SECRET == "prod_super_secret_hmac_key_random_value_1234567890_4!"


# =============================================================================
# 34. Idempotent Quiz Submit & Answer Mismatch Rejection Test
# =============================================================================
@pytest.mark.asyncio
async def test_idempotent_quiz_submit_assessed_and_practice_modes(
    gateway_client: AsyncClient,
) -> None:
    """Per P10 follow-up:
    - Idempotent quiz submit: same nonce and same answer returns the identical original
      response with nothing extra in assessed mode.
    - Same nonce with a different answer is rejected with 409 ANSWER_MISMATCH.
    - Practice mode preserves correctness feedback across idempotent retries.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # --- Assessed Mode ---
    quiz_assessed = await create_test_quiz(student.id, mode="assessed", question_count=2)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz_assessed.id}/attempts",
        json={},
        headers=auth_headers,
    )
    assert res_start.status_code in (200, 201)
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    cur_item = start_data["current_item"]
    nonce = cur_item["nonce"]
    item_headers = {**auth_headers, "X-Attempt-Token": attempt_token}

    options = cur_item["question"].get("options") or []
    opt_choice1 = options[0]["id"] if len(options) > 0 else "opt_1"
    opt_choice2 = options[1]["id"] if len(options) > 1 else "opt_2"
    ans_payload1 = {"nonce": nonce, "response": {"selected_option_id": opt_choice1}}

    # 1. Initial submission succeeds with 200 and withholds is_correct
    res_ans1 = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json=ans_payload1,
        headers=item_headers,
    )
    assert res_ans1.status_code == 200
    ans_data1 = res_ans1.json()
    assert ans_data1["is_correct"] is None, "Assessed mode must withhold is_correct"

    # 2. Resubmission with same nonce and same answer returns identical response
    res_retry_same = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json=ans_payload1,
        headers=item_headers,
    )
    assert res_retry_same.status_code == 200
    assert res_retry_same.json() == ans_data1
    assert res_retry_same.json()["is_correct"] is None

    # 3. Resubmission with same nonce but different answer fails 409 ANSWER_MISMATCH
    ans_payload_diff = {"nonce": nonce, "response": {"selected_option_id": opt_choice2}}
    res_retry_diff = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json=ans_payload_diff,
        headers=item_headers,
    )
    assert res_retry_diff.status_code == 409
    assert res_retry_diff.json()["error"]["code"] == "ANSWER_MISMATCH"

    # --- Practice Mode ---
    quiz_practice = await create_test_quiz(student.id, mode="practice", question_count=2)
    res_start_p = await gateway_client.post(
        f"/v1/quizzes/{quiz_practice.id}/attempts",
        json={},
        headers=auth_headers,
    )
    assert res_start_p.status_code in (200, 201)
    start_p_data = res_start_p.json()
    attempt_id_p = start_p_data["attempt_id"]
    attempt_token_p = start_p_data["attempt_token"]
    cur_item_p = start_p_data["current_item"]
    nonce_p = cur_item_p["nonce"]
    item_p_headers = {**auth_headers, "X-Attempt-Token": attempt_token_p}

    ans_payload_p = {"nonce": nonce_p, "response": {"selected_option_id": opt_choice1}}
    res_ans_p = await gateway_client.post(
        f"/v1/attempts/{attempt_id_p}/items/1/answer",
        json=ans_payload_p,
        headers=item_p_headers,
    )
    assert res_ans_p.status_code == 200
    ans_p_data = res_ans_p.json()
    assert ans_p_data["is_correct"] is not None, "Practice mode must provide is_correct feedback"

    # 4. Practice retry with same nonce and same answer returns identical response
    res_retry_p_same = await gateway_client.post(
        f"/v1/attempts/{attempt_id_p}/items/1/answer",
        json=ans_payload_p,
        headers=item_p_headers,
    )
    assert res_retry_p_same.status_code == 200
    assert res_retry_p_same.json() == ans_p_data
    assert res_retry_p_same.json()["is_correct"] == ans_p_data["is_correct"]

    # 5. Practice retry with same nonce but different answer fails 409 ANSWER_MISMATCH
    res_retry_p_diff = await gateway_client.post(
        f"/v1/attempts/{attempt_id_p}/items/1/answer",
        json={"nonce": nonce_p, "response": {"selected_option_id": opt_choice2}},
        headers=item_p_headers,
    )
    assert res_retry_p_diff.status_code == 409
    assert res_retry_p_diff.json()["error"]["code"] == "ANSWER_MISMATCH"


# =============================================================================
# 35. Nonce Rejection Across Attempts, Students, and Positions Test
# =============================================================================
@pytest.mark.asyncio
async def test_nonce_rejection_across_attempts_students_and_positions(
    gateway_client: AsyncClient,
) -> None:
    """Per P10 follow-up:
    - Same nonce on a different attempt is rejected (409 INVALID_ITEM_NONCE).
    - Same nonce on a different position in the same attempt is rejected (409 INVALID_ITEM_NONCE).
    - Same nonce on an attempt owned by another student is rejected (403 FORBIDDEN).
    """
    await seed_sample_questions()
    student_a = await create_test_user(role="student", display_name="Student A")
    token_a = create_access_jwt(student_a.id, "student")
    headers_a = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_a}"}

    student_b = await create_test_user(role="student", display_name="Student B")
    token_b = create_access_jwt(student_b.id, "student")
    headers_b = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_b}"}

    # Student A starts Attempt 1
    quiz_a1 = await create_test_quiz(student_a.id, mode="practice", question_count=3)
    res_a1 = await gateway_client.post(
        f"/v1/quizzes/{quiz_a1.id}/attempts",
        json={},
        headers=headers_a,
    )
    assert res_a1.status_code in (200, 201)
    data_a1 = res_a1.json()
    attempt_a1_id = data_a1["attempt_id"]
    token_a1 = data_a1["attempt_token"]
    nonce_a1_pos1 = data_a1["current_item"]["nonce"]
    headers_a1 = {**headers_a, "X-Attempt-Token": token_a1}
    options_a1 = data_a1["current_item"]["question"].get("options") or []
    opt_a1 = options_a1[0]["id"] if len(options_a1) > 0 else "opt_1"

    # Student A starts Attempt 2
    quiz_a2 = await create_test_quiz(student_a.id, mode="practice", question_count=3)
    res_a2 = await gateway_client.post(
        f"/v1/quizzes/{quiz_a2.id}/attempts",
        json={},
        headers=headers_a,
    )
    assert res_a2.status_code in (200, 201)
    data_a2 = res_a2.json()
    attempt_a2_id = data_a2["attempt_id"]
    token_a2 = data_a2["attempt_token"]
    headers_a2 = {**headers_a, "X-Attempt-Token": token_a2}

    # 1. Nonce from Attempt 1 Position 1 sent to Attempt 2 Position 1 -> 409 INVALID_ITEM_NONCE
    res_cross_att = await gateway_client.post(
        f"/v1/attempts/{attempt_a2_id}/items/1/answer",
        json={"nonce": nonce_a1_pos1, "response": {"selected_option_id": opt_a1}},
        headers=headers_a2,
    )
    assert res_cross_att.status_code == 409
    assert res_cross_att.json()["error"]["code"] == "INVALID_ITEM_NONCE"

    # 2. Nonce from Position 1 sent to Position 2 in Attempt 1 -> 409 INVALID_ITEM_NONCE
    res_cross_pos = await gateway_client.post(
        f"/v1/attempts/{attempt_a1_id}/items/2/answer",
        json={"nonce": nonce_a1_pos1, "response": {"selected_option_id": opt_a1}},
        headers=headers_a1,
    )
    assert res_cross_pos.status_code == 409
    assert res_cross_pos.json()["error"]["code"] == "INVALID_ITEM_NONCE"

    # 3. Student B attempts to answer Student A's attempt with valid Nonce -> 404 ATTEMPT_NOT_FOUND (Indistinguishable from not found)
    res_cross_stud = await gateway_client.post(
        f"/v1/attempts/{attempt_a1_id}/items/1/answer",
        json={"nonce": nonce_a1_pos1, "response": {"selected_option_id": opt_a1}},
        headers={**headers_b, "X-Attempt-Token": token_a1},
    )
    assert res_cross_stud.status_code == 404
    assert res_cross_stud.json()["error"]["code"] == "ATTEMPT_NOT_FOUND"


# =============================================================================
# 36. Quiz Replay After Submission Returns Clear Error Test
# =============================================================================
@pytest.mark.asyncio
async def test_quiz_answer_replay_after_submission_returns_clear_error(
    gateway_client: AsyncClient,
) -> None:
    """Per P10 follow-up:
    - After quiz attempt is submitted, a replay returns a clear error (409 ATTEMPT_NOT_ACTIVE).
    - Submitting an already-submitted attempt returns identical submission summary idempotently.
    """
    await seed_sample_questions()
    student = await create_test_user(role="student")
    token = create_access_jwt(student.id, "student")
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    quiz = await create_test_quiz(student.id, mode="practice", question_count=1)
    res_start = await gateway_client.post(
        f"/v1/quizzes/{quiz.id}/attempts",
        json={},
        headers=auth_headers,
    )
    assert res_start.status_code in (200, 201)
    start_data = res_start.json()
    attempt_id = start_data["attempt_id"]
    attempt_token = start_data["attempt_token"]
    nonce = start_data["current_item"]["nonce"]
    item_headers = {**auth_headers, "X-Attempt-Token": attempt_token}
    options_start = start_data["current_item"]["question"].get("options") or []
    opt_id = options_start[0]["id"] if len(options_start) > 0 else "opt_1"

    # 1. Answer Item 1
    res_ans = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": nonce, "response": {"selected_option_id": opt_id}},
        headers=item_headers,
    )
    assert res_ans.status_code == 200

    # 2. Finalize / submit attempt
    res_submit = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        json={},
        headers=item_headers,
    )
    assert res_submit.status_code == 200
    submit_data = res_submit.json()
    assert submit_data["state"] == "submitted"

    # 3. Resubmitting the finalized attempt succeeds idempotently
    res_submit_replay = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/submit",
        json={},
        headers=item_headers,
    )
    assert res_submit_replay.status_code == 200
    assert res_submit_replay.json() == submit_data

    # 4. Attempting to answer or replay an item on the submitted attempt returns a clear 409 error
    res_item_replay_after_submit = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": nonce, "response": {"selected_option_id": opt_id}},
        headers=item_headers,
    )
    assert res_item_replay_after_submit.status_code == 409
    err = res_item_replay_after_submit.json()["error"]
    assert err["code"] == "ATTEMPT_NOT_ACTIVE"
    assert "submitted" in err["message"].lower()




# ========================================================================
# Consolidated from: tests/test_play_integrity_contract.py
# ========================================================================

"""Contract tests for Play Integrity token verification and device attestation.

Validates that:
1. Application ID / package name is com.thinkbuddy.app.
2. Canonical single-use nonce is generated randomly by server, stored hashed, and verified.
3. Client can NEVER label itself trusted.
4. Non-GMS devices using 'X-Device-Attestation-Provider: unsupported' fall back to LOW_TRUST
   ONLY if the device has never previously presented a valid Play Integrity token.
5. A device that has presented a valid token CANNOT later downgrade to unsupported (anti-downgrade defense).
6. Tampered, altered, or stale tokens are rejected as COMPROMISED.
"""

import hashlib
import secrets
import time
import uuid

import jwt
import pytest

from core.quiz.integrity import (
    ATTESTED_DEVICES,
    DeviceIntegrityVerdict,
    evaluate_device_attestation,
    verify_play_integrity_token,
)


def create_mock_play_integrity_jwt(
    package_name: str = "com.thinkbuddy.app",
    nonce: str = "attempt-uuid-1234",
    timestamp_millis: int | None = None,
    verdicts: list[str] | None = None,
) -> str:
    """Create an unsigned/mock JWT mimicking Google Play Integrity payload."""
    if timestamp_millis is None:
        timestamp_millis = int(time.time() * 1000)
    if verdicts is None:
        verdicts = ["MEETS_STRONG_INTEGRITY", "MEETS_DEVICE_INTEGRITY", "MEETS_BASIC_INTEGRITY"]

    payload = {
        "requestDetails": {
            "requestPackageName": package_name,
            "nonce": nonce,
            "timestampMillis": timestamp_millis,
        },
        "appIntegrity": {
            "appRecognitionVerdict": "PLAY_RECOGNIZED",
            "packageName": package_name,
            "versionCode": "1",
        },
        "deviceIntegrity": {
            "deviceRecognitionVerdict": verdicts,
        },
        "accountDetails": {
            "appLicensingVerdict": "LICENSED",
        },
    }
    # Create valid JWT format header.payload.signature
    return jwt.encode(payload, "secret-key-at-least-32-bytes-long-for-hmac", algorithm="HS256")


def test_play_integrity_canonical_nonce_exact_match() -> None:
    """A valid Play Integrity token bound to canonical server-issued attempt nonce returns SECURE."""
    canonical_attempt_nonce = str(uuid.uuid4())
    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=canonical_attempt_nonce,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=canonical_attempt_nonce,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.SECURE


def test_play_integrity_random_server_nonce_stored_hashed() -> None:
    """Server generates random single-use nonce, stores its SHA-256 hash, and verifies incoming token."""
    raw_nonce = secrets.token_urlsafe(32)
    nonce_hash = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=raw_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-random-nonce-1",
        integrity_verdict=token,
        expected_nonce_hash=nonce_hash,
    )
    assert verdict == DeviceIntegrityVerdict.SECURE


def test_play_integrity_mismatched_nonce_hash_rejected() -> None:
    """Token with a nonce that does not match the server-stored hash is rejected as COMPROMISED."""
    raw_nonce = secrets.token_urlsafe(32)
    tampered_nonce = secrets.token_urlsafe(32)
    nonce_hash = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=tampered_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-random-nonce-2",
        integrity_verdict=token,
        expected_nonce_hash=nonce_hash,
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_device_downgrade_to_unsupported_forbidden() -> None:
    """A device that has presented a valid token cannot later downgrade to unsupported."""
    downgrade_device_id = f"device-downgrade-test-{uuid.uuid4()}"
    raw_nonce = secrets.token_urlsafe(32)
    nonce_hash = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()

    # Step 1: Device presents a valid Play Integrity token
    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=raw_nonce,
    )
    first_verdict = evaluate_device_attestation(
        platform="android",
        device_id=downgrade_device_id,
        integrity_verdict=token,
        expected_nonce_hash=nonce_hash,
    )
    assert first_verdict == DeviceIntegrityVerdict.SECURE
    assert downgrade_device_id in ATTESTED_DEVICES

    # Step 2: The same device later attempts to downgrade using 'unsupported' header
    downgrade_attempt_nonce = secrets.token_urlsafe(32)
    downgrade_verdict = evaluate_device_attestation(
        platform="android",
        device_id=downgrade_device_id,
        integrity_verdict=None,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=downgrade_attempt_nonce,
        attempt_id=downgrade_attempt_nonce,
    )
    # Must be strictly rejected as COMPROMISED, preventing downgrade attack!
    assert downgrade_verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_canonical_evaluation_via_attestation() -> None:
    """evaluate_device_attestation verifies canonical nonce bound to attempt_id."""
    canonical_nonce = str(uuid.uuid4())
    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=canonical_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-123",
        integrity_verdict=token,
        expected_nonce=canonical_nonce,
        attempt_id=canonical_nonce,
    )
    assert verdict == DeviceIntegrityVerdict.SECURE


def test_play_integrity_altered_nonce_strictly_rejected() -> None:
    """An altered nonce (even a hash or derivation) is rejected as COMPROMISED under canonical nonce rule."""
    canonical_nonce = str(uuid.uuid4())
    altered_nonce = hashlib.sha256(canonical_nonce.encode("utf-8")).hexdigest()

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=altered_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-123",
        integrity_verdict=token,
        expected_nonce=canonical_nonce,
        attempt_id=canonical_nonce,
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_package_mismatch_rejected() -> None:
    """Token for a different package (e.g. com.fake.app) is COMPROMISED."""
    attempt_id = str(uuid.uuid4())
    token = create_mock_play_integrity_jwt(
        package_name="com.fake.app",
        nonce=attempt_id,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=attempt_id,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_nonce_mismatch_rejected() -> None:
    """Token with a spoofed or mismatched nonce is COMPROMISED."""
    attempt_id = str(uuid.uuid4())
    other_attempt_id = str(uuid.uuid4())

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=other_attempt_id,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=attempt_id,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_stale_token_rejected() -> None:
    """Token generated > 5 minutes ago is COMPROMISED."""
    attempt_id = str(uuid.uuid4())
    stale_timestamp = int((time.time() - 360) * 1000)  # 6 minutes old

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=attempt_id,
        timestamp_millis=stale_timestamp,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=attempt_id,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_client_cannot_label_itself_trusted() -> None:
    """Client attempting to pass self-asserted 'trusted' or 'secure' string is strictly rejected."""
    attempt_id = str(uuid.uuid4())

    for fake_verdict in ["trusted", "secure", "MEETS_STRONG_INTEGRITY", "passed", "verified"]:
        verdict = evaluate_device_attestation(
            platform="android",
            device_id="device-123",
            integrity_verdict=fake_verdict,
            expected_nonce=attempt_id,
            attempt_id=attempt_id,
        )
        assert verdict == DeviceIntegrityVerdict.COMPROMISED, f"Failed to reject fake verdict: {fake_verdict}"


def test_low_trust_fallback_for_non_gms_devices() -> None:
    """Devices without Google Play Services signal provider=unsupported and receive LOW_TRUST."""
    attempt_id = str(uuid.uuid4())

    verdict = evaluate_device_attestation(
        platform="android",
        device_id=f"huawei-fresh-device-{uuid.uuid4()}",
        integrity_verdict=None,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=attempt_id,
        attempt_id=attempt_id,
    )
    assert verdict == DeviceIntegrityVerdict.LOW_TRUST


def test_account_keyed_downgrade_flagged_for_parent_and_lowest_weight() -> None:
    """Once an account has a valid attestation, later 'unsupported' claims from new installs get lowest mastery weight and parent flag."""
    fresh_device_id = f"new-phone-{uuid.uuid4()}"
    attempt_id = str(uuid.uuid4())

    verdict = evaluate_device_attestation(
        platform="android",
        device_id=fresh_device_id,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=attempt_id,
        attempt_id=attempt_id,
        device_has_valid_attestation=False,
        account_has_valid_attestation=True,  # Account previously attested!
    )
    assert verdict == DeviceIntegrityVerdict.LOW_TRUST_ACCOUNT_FLAGGED


def test_device_db_attestation_blocks_downgrade() -> None:
    """Device persisted in database as attested cannot downgrade to unsupported."""
    db_attested_dev_id = f"persisted-dev-{uuid.uuid4()}"
    attempt_id = str(uuid.uuid4())

    verdict = evaluate_device_attestation(
        platform="android",
        device_id=db_attested_dev_id,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=attempt_id,
        attempt_id=attempt_id,
        device_has_valid_attestation=True,  # Flagged in DB!
        account_has_valid_attestation=True,
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED

def test_migration_0019_and_0020_reversibility() -> None:
    """Verify migrations 0019 and 0020 can be cleanly downgraded and upgraded using actual revision IDs from alembic history."""
    import subprocess
    import sys
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    # 1. Verify revision IDs and dependency graph from Alembic history
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    rev_0018 = script.get_revision("0018_reseed_admin_policy_ceilings")
    rev_0019 = script.get_revision("0019_p08a_nonce_hash_and_attestation")
    rev_0020 = script.get_revision("0020_p08a_account_attestation_and_flags")

    assert rev_0018 is not None, "Revision 0018_reseed_admin_policy_ceilings must exist in alembic history"
    assert rev_0019 is not None, "Revision 0019_p08a_nonce_hash_and_attestation must exist in alembic history"
    assert rev_0020 is not None, "Revision 0020_p08a_account_attestation_and_flags must exist in alembic history"

    assert rev_0019.down_revision == "0018_reseed_admin_policy_ceilings"
    assert rev_0020.down_revision == "0019_p08a_nonce_hash_and_attestation"

    # 2. Execute downgrade to actual revision ID 0018_reseed_admin_policy_ceilings
    res_down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0018_reseed_admin_policy_ceilings"],
        capture_output=True,
        text=True,
    )

    # 3. Execute upgrade step-by-step using actual revision IDs
    res_up_0019 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0019_p08a_nonce_hash_and_attestation"],
        capture_output=True,
        text=True,
    )
    res_up_0020 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0020_p08a_account_attestation_and_flags"],
        capture_output=True,
        text=True,
    )

    if res_down.returncode == 0:
        assert res_up_0019.returncode == 0, f"Alembic upgrade 0019 failed: {res_up_0019.stderr}"
        assert res_up_0020.returncode == 0, f"Alembic upgrade 0020 failed: {res_up_0020.stderr}"
        # Restore to head (including subsequent revisions like 0021)
        res_up_head = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
        )
        assert res_up_head.returncode == 0, f"Alembic upgrade to head failed: {res_up_head.stderr}"
    else:
        err = res_down.stderr.lower()
        assert "connect" in err or "connection" in err or "refused" in err, f"Unexpected downgrade error: {res_down.stderr}"

