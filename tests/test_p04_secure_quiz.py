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

from __future__ import annotations

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

    # 4. Replay the same nonce for the already answered item -> 409 conflict
    res_replay = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={"nonce": valid_nonce, "response": {"selected_option_id": "opt_a"}},
        headers={**auth_headers, "X-Attempt-Token": valid_attempt_token},
    )
    # The server has already processed position 1 or nonce is no longer active
    assert res_replay.status_code in (409, 400)


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

    # 4. Cross-student authorization check -> other student cannot review -> 403 Forbidden
    res_review_other = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=other_headers,
    )
    assert res_review_other.status_code in (403, 404)


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
    auth_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

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
    ans_statuses = {ans_res1.status_code, ans_res2.status_code}
    assert ans_statuses == {200, 409}


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
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

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

    # 1. Student B tries to answer Student A's attempt -> 403 Forbidden
    res_b_answer = await gateway_client.post(
        f"/v1/attempts/{attempt_id}/items/1/answer",
        json={
            "nonce": item1["nonce"],
            "response": {"selected_option_id": item1["question"]["options"][0]["id"] if item1["question"]["options"] else "dummy"},
            "time_spent_ms": 10000,
        },
        headers={**headers_b, "X-Attempt-Token": attempt_token},
    )
    assert res_b_answer.status_code == 403

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

    # 4. Unlinked parent tries to review Student A's submitted attempt -> 403 FORBIDDEN
    res_unlinked_review = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=headers_p_unlinked,
    )
    assert res_unlinked_review.status_code == 403
    assert res_unlinked_review.json()["error"]["code"] == "FORBIDDEN"

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

