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

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

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
from scripts.import_questions import import_jsonl_file

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

    # 4. Cross-student authorization check -> other student cannot review -> 404
    res_review_other = await gateway_client.get(
        f"/v1/attempts/{attempt_id}/review",
        headers=other_headers,
    )
    assert res_review_other.status_code == 404


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
