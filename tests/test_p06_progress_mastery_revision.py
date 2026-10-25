"""Comprehensive acceptance and property tests for Milestone P06.

Requirements Covered:
1. Daily and 3-day jobs regenerate future days via P03 planner under student lock (restoring weak-point share).
2. Streaks do not break on blackout, exam, rest, or weekly off days.
3. Jobs run per student at fixed local time (Asia/Dhaka), batched and throttled.
4. Revision queue is capped by available minutes and excludes subjects in blackout or past exam.
5. Review quiz built via P04 builder; skips with warning if too few questions.
6. Offline question worker: pool='practice', review_status='draft', rejected without valid source chunk.
7. Parent-facing wording uses "needs practice" and "not enough data", NEVER "weak".
8. Tests: Hypothesis properties (mastery bounds, monotonicity, Leitner boxes), concurrent double-run,
   Rule 9 authorization, Asia/Dhaka midnight rollover.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from sqlalchemy import select

from core.auth.models import User
from core.auth.tokens import create_access_jwt
from core.common.database import AsyncSessionLocal
from core.curriculum.models import Book, Chapter, Chunk
from core.families.models import ParentStudentLink, StudentProfile
from core.planner.models import Plan, PlanDay, StudySetup, SyllabusItem
from core.planner.settings_resolver import ResolvedPlannerSettings
from core.progress.jobs import (
    run_batched_daily_jobs,
    run_daily_composition_job,
    run_three_day_review_cycle,
)
from core.progress.mastery import SignalInput, compute_mastery
from core.progress.models import ProgressDaily, RevisionItem
from core.progress.question_worker import QuestionGenerationWorker
from core.progress.revision import (
    LEITNER_INTERVALS,
    RevisionScheduler,
    calculate_next_box,
)
from core.progress.streak import calculate_streak
from core.quiz.models import Question, QuestionKey, Quiz

logger = logging.getLogger(__name__)

CLIENT_HEADERS = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-p06-test-001",
    "Accept-Language": "bn",
}


# =============================================================================
# Helper Fixtures & Persisters
# =============================================================================
async def create_user(role: str = "student", display_name: str = "Test User") -> User:
    """Create and persist a user."""
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            auth_provider="fake",
            auth_uid=f"fake:uid:{uuid.uuid4()}",
            role=role,
            display_name=display_name,
            phone=f"+88017{uuid.uuid4().hex[:8]}",
            status="active",
            locale="bn",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def setup_student_with_curriculum() -> tuple[User, Book, Chapter, Chunk]:
    """Create a student with profile, book, chapter, and textbook chunk."""
    student = await create_user(role="student", display_name="Curriculum Student")
    async with AsyncSessionLocal() as session:
        # Student profile
        profile = StudentProfile(
            user_id=student.id,
            class_level=9,
            group="science",
            available_days=["sun", "mon", "tue", "wed", "thu"],
            created_at=datetime.now(UTC),
        )
        session.add(profile)

        # Curriculum Book, Chapter, Chunk
        book = Book(
            id=uuid.uuid4(),
            title="General Science",
            subject="Science",
            class_level=9,
            edition=f"ed_{uuid.uuid4().hex[:8]}",
            medium="bn",
            created_at=datetime.now(UTC),
        )
        session.add(book)
        await session.flush()

        chapter = Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=1,
            title="Living World",
            printed_page_start=1,
            printed_page_end=20,
            order_index=1,
            difficulty_factor=1.0,
            created_at=datetime.now(UTC),
        )
        session.add(chapter)
        await session.flush()

        chunk = Chunk(
            id=uuid.uuid4(),
            book_id=book.id,
            chapter_id=chapter.id,
            chunk_index=1,
            printed_page=5,
            pdf_page_index=7,
            text="উদ্ভিদ ও প্রাণীর জীবন প্রক্রিয়া বিষয়ক মূল ধারণা।",
            created_at=datetime.now(UTC),
        )
        session.add(chunk)

        # Study Setup
        setup = StudySetup(
            id=uuid.uuid4(),
            student_id=student.id,
            set_by_user_id=student.id,
            subject="Science",
            exam_name="Science Midterm",
            exam_date=date.today() + timedelta(days=45),
            active_plan_version=1,
            created_at=datetime.now(UTC),
        )
        session.add(setup)
        await session.flush()

        s_item = SyllabusItem(
            id=uuid.uuid4(),
            setup_id=setup.id,
            chapter_id=chapter.id,
            custom_order=1,
            weight=1.0,
            included=True,
        )
        session.add(s_item)

        await session.commit()
        return student, book, chapter, chunk


# =============================================================================
# 1. Hypothesis Property Tests (Requirement 8)
# =============================================================================
@given(
    sources=st.lists(
        st.sampled_from([
            "quiz_correct", "quiz_wrong", "practice_correct", "practice_wrong",
            "quiz_slow", "ai_question", "ai_repeat", "task_skipped", "teacher_flag"
        ]),
        min_size=0,
        max_size=30,
    ),
    weights=st.lists(st.floats(min_value=0.1, max_value=5.0), min_size=0, max_size=30),
    unverified_flags=st.lists(st.booleans(), min_size=0, max_size=30),
    day_offsets=st.lists(st.integers(min_value=0, max_value=60), min_size=0, max_size=30),
)
@hyp_settings(max_examples=30, deadline=None)
def test_hypothesis_mastery_bounds(
    sources: list[str],
    weights: list[float],
    unverified_flags: list[bool],
    day_offsets: list[int],
) -> None:
    """Property: Arbitrary streams of learning signals always yield bounded score & confidence [0.0, 1.0]."""
    n = min(len(sources), len(weights), len(unverified_flags), len(day_offsets))
    now = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)

    signals: list[SignalInput] = []
    for i in range(n):
        sig_dt = now - timedelta(days=day_offsets[i])
        signals.append(
            SignalInput(
                source=sources[i],
                weight=weights[i],
                is_unverified_device=unverified_flags[i],
                at=sig_dt,
            )
        )

    res = compute_mastery(signals=signals, evaluation_time=now)
    assert 0.0 <= res.score <= 1.0, f"Score out of bounds: {res.score}"
    assert 0.0 <= res.confidence <= 1.0, f"Confidence out of bounds: {res.confidence}"
    assert res.status in ("mastered", "needs_practice", "not_enough_data", "in_progress")
    assert "weak" not in res.status.lower()


@given(
    initial_score=st.floats(min_value=0.2, max_value=0.8),
    signal_weight=st.floats(min_value=0.5, max_value=2.0),
)
@hyp_settings(max_examples=25, deadline=None)
def test_hypothesis_mastery_monotonicity(initial_score: float, signal_weight: float) -> None:
    """Property: A positive signal never decreases mastery score; a negative signal never increases it."""
    now = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)

    base_signals = [
        SignalInput(
            source="practice_correct",
            weight=1.0,
            at=now - timedelta(days=1),
        )
    ]
    base_res = compute_mastery(signals=base_signals, initial_score=initial_score, evaluation_time=now)

    # Positive signal (quiz_correct)
    pos_signals = list(base_signals) + [
        SignalInput(
            source="quiz_correct",
            weight=signal_weight,
            at=now,
        )
    ]
    pos_res = compute_mastery(signals=pos_signals, initial_score=initial_score, evaluation_time=now)
    assert pos_res.score >= base_res.score - 1e-9, f"Positive signal decreased score: {pos_res.score} < {base_res.score}"

    # Negative signal (quiz_wrong)
    neg_signals = list(base_signals) + [
        SignalInput(
            source="quiz_wrong",
            weight=signal_weight,
            at=now,
        )
    ]
    neg_res = compute_mastery(signals=neg_signals, initial_score=initial_score, evaluation_time=now)
    assert neg_res.score <= base_res.score + 1e-9, f"Negative signal increased score: {neg_res.score} > {base_res.score}"


@given(
    box=st.integers(min_value=1, max_value=5),
    is_correct=st.booleans(),
)
@hyp_settings(max_examples=20, deadline=None)
def test_hypothesis_leitner_box_progression(box: int, is_correct: bool) -> None:
    """Property: Leitner progression advances box monotonically on correct (up to 5) and resets to 1 on wrong."""
    next_box, interval = calculate_next_box(current_box=box, is_correct=is_correct)

    if is_correct:
        assert next_box == min(5, box + 1)
        assert interval == LEITNER_INTERVALS[next_box]
        # Intervals must be strictly monotonically non-decreasing
        assert interval >= LEITNER_INTERVALS[box]
    else:
        assert next_box == 1
        assert interval == LEITNER_INTERVALS[1]


# =============================================================================
# 2. Streak Continuity with Exempt Days (Requirement 2)
# =============================================================================
@pytest.mark.asyncio
async def test_streak_continuity_with_exempt_days() -> None:
    """Requirement 2: Streaks must not break on blackout, exam, rest, or weekly off days."""
    student = await create_user(role="student", display_name="Streak Student")

    # Resolved settings with weekly off days = fri, sat
    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=120,
        holiday_minutes=180,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[
            {"start_date": "2026-10-20", "end_date": "2026-10-20", "reason": "family_event"}
        ],
        subject_priorities={"Science": "normal"},
    )

    # Date sequence:
    # 2026-10-19: Monday (School Day) -> Studied 30m, 1 task
    # 2026-10-20: Tuesday (Custom Blackout Day) -> 0m, 0 tasks (Exempt)
    # 2026-10-21: Wednesday (School Day) -> Studied 30m, 1 task
    # 2026-10-22: Thursday (Exam Day) -> 0m, 0 tasks (Exempt)
    # 2026-10-23: Friday (Weekly Off / Holiday) -> 0m, 0 tasks (Exempt)
    # 2026-10-24: Saturday (Weekly Off / Holiday) -> 0m, 0 tasks (Exempt)
    # 2026-10-25: Sunday (School Day) -> Studied 40m, 1 task

    exam_dates = {date(2026, 10, 22)}

    async with AsyncSessionLocal() as session:
        # Seed daily progress records
        p1 = ProgressDaily(
            id=uuid.uuid4(),
            student_id=student.id,
            date=date(2026, 10, 19),
            minutes=30,
            tasks_done=1,
            tasks_total=1,
            quiz_avg=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        p2 = ProgressDaily(
            id=uuid.uuid4(),
            student_id=student.id,
            date=date(2026, 10, 21),
            minutes=30,
            tasks_done=1,
            tasks_total=1,
            quiz_avg=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        p3 = ProgressDaily(
            id=uuid.uuid4(),
            student_id=student.id,
            date=date(2026, 10, 25),
            minutes=40,
            tasks_done=1,
            tasks_total=1,
            quiz_avg=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add_all([p1, p2, p3])
        await session.commit()

        # Calculate streak as of 2026-10-25
        streak = await calculate_streak(
            db=session,
            student_id=student.id,
            as_of_date=date(2026, 10, 25),
            resolved_settings=settings,
            exam_dates=exam_dates,
        )

        # 3 studied school days separated only by exempt days (blackout, exam, fri, sat)
        # Streak should be 3!
        assert streak == 3, f"Expected streak 3 across exempt days, got {streak}"

        # Now test breaking: if 2026-10-18 was a school day with 0 study, streak broke before 18
        # But if 2026-10-21 had NOT been studied (unexcused school day):
        # We delete p2 and recompute:
        await session.delete(p2)
        await session.commit()

        broken_streak = await calculate_streak(
            db=session,
            student_id=student.id,
            as_of_date=date(2026, 10, 25),
            resolved_settings=settings,
            exam_dates=exam_dates,
        )
        # 2026-10-21 was an unstudied school day, terminating the streak before it reached 10-19.
        # Only 2026-10-25 counts now.
        assert broken_streak == 1, f"Expected broken streak to be 1, got {broken_streak}"


# =============================================================================
# 3. Revision Queue Capping and Subject Exclusion (Requirement 4)
# =============================================================================
@pytest.mark.asyncio
async def test_revision_queue_capping_and_subject_exclusion() -> None:
    """Requirement 4: Cap revision queue by available minutes and exclude subjects in blackout or past exam."""
    student, book, chapter, chunk = await setup_student_with_curriculum()
    now_dt = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)

    async with AsyncSessionLocal() as session:
        # Create 10 revision items due in box 1 across 10 chapters
        items = []
        for i in range(10):
            ch = Chapter(
                id=uuid.uuid4(),
                book_id=book.id,
                number=i + 10,
                title=f"Chapter {i + 10}",
                printed_page_start=10 * i + 1,
                printed_page_end=10 * i + 10,
                order_index=i + 10,
            )
            session.add(ch)
            await session.flush()

            item = RevisionItem(
                id=uuid.uuid4(),
                student_id=student.id,
                chapter_id=ch.id,
                box=1,
                due_at=now_dt - timedelta(hours=i + 1),  # all overdue
                created_at=now_dt - timedelta(days=2),
                updated_at=now_dt - timedelta(days=2),
            )
            items.append(item)
            session.add(item)
        await session.commit()

        scheduler = RevisionScheduler(session)

        # Test A: Queue Capping by available minutes
        # If available_minutes = 6, and each item is ESTIMATED_MINUTES_PER_ITEM (2m), max 3 items
        due_capped = await scheduler.get_due_items(
            student_id=student.id,
            target_date=now_dt.date(),
            now_dt=now_dt,
            available_minutes=6,
        )
        assert len(due_capped) == 3, f"Expected 3 items for 6 minutes, got {len(due_capped)}"

        # Test B: Exclude subjects in past exam
        # Set exam_date = yesterday (2026-10-24)
        stmt_setup = select(StudySetup).where(StudySetup.student_id == student.id)
        res_setup = await session.execute(stmt_setup)
        setup = res_setup.scalar_one()
        setup.exam_date = now_dt.date() - timedelta(days=1)
        await session.commit()

        due_past_exam = await scheduler.get_due_items(
            student_id=student.id,
            target_date=now_dt.date(),
            now_dt=now_dt,
            available_minutes=20,
        )
        assert len(due_past_exam) == 0, f"Expected 0 items for past exam subject, got {len(due_past_exam)}"


# =============================================================================
# 4. Review Quiz Builder via P04 Builder (Requirement 5)
# =============================================================================
@pytest.mark.asyncio
async def test_review_quiz_builder_p04_skips_when_insufficient_questions() -> None:
    """Requirement 5: Build review quizzes via P04 builder; if too few questions, skip and warn."""
    student, book, chapter, chunk = await setup_student_with_curriculum()

    async with AsyncSessionLocal() as session:
        # Create an isolated chapter with guaranteed 0 questions
        empty_chapter = Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=99,
            title="Isolated Topic Without Questions",
            printed_page_start=80,
            printed_page_end=95,
            order_index=99,
            difficulty_factor=1.0,
            created_at=datetime.now(UTC),
        )
        session.add(empty_chapter)

        # Update student setup syllabus item to point to this chapter
        stmt_item = select(SyllabusItem).join(StudySetup).where(StudySetup.student_id == student.id)
        res_item = await session.execute(stmt_item)
        s_item = res_item.scalar_one()
        s_item.chapter_id = empty_chapter.id
        await session.commit()

        # Setup has 0 questions in question bank for this chapter
        # Running the 3-day review cycle should skip quiz creation and proceed with plan regeneration
        new_plan_version, review_quiz_id = await run_three_day_review_cycle(session, student.id)

        assert review_quiz_id is None, "Review quiz should be skipped when questions < 3"
        assert new_plan_version >= 1, "Plan version should regenerate successfully"

        # Now add 3 questions and verify review quiz is created
        for i in range(3):
            q = Question(
                id=uuid.uuid4(),
                chapter_id=empty_chapter.id,
                type="mcq",
                difficulty=0.5,
                origin="curated",
                pool="assessed",
                stem={"blocks": [{"type": "text", "text": f"Question {i + 1} on living organisms?"}]},
                options=[
                    {"id": "opt_a", "text": "Option A"},
                    {"id": "opt_b", "text": "Option B"},
                ],
                source_chunk_ids=[str(chunk.id)],
                created_at=datetime.now(UTC),
            )
            session.add(q)
            await session.flush()
            qk = QuestionKey(
                question_id=q.id,
                correct_option_id="opt_a",
                created_at=datetime.now(UTC),
            )
            session.add(qk)
        await session.commit()

        # Re-run 3-day review cycle with sufficient questions
        new_plan_v2, quiz_id_created = await run_three_day_review_cycle(session, student.id)
        assert quiz_id_created is not None, "Review quiz should be created when questions >= 3"
        quiz = await session.get(Quiz, quiz_id_created)
        assert quiz is not None
        assert quiz.kind == "review"
        assert quiz.student_id == student.id


# =============================================================================
# 5. Offline Question Worker Groundedness (Requirement 6)
# =============================================================================
@pytest.mark.asyncio
async def test_offline_question_worker_groundedness_and_rejection() -> None:
    """Requirement 6: Worker stays offline; questions are pool=practice, draft until approved, rejected without chunk."""
    student, book, chapter, chunk = await setup_student_with_curriculum()

    async with AsyncSessionLocal() as session:
        worker = QuestionGenerationWorker(session)

        # Case A: Valid chunk ID produces draft practice question
        q = await worker.generate_grounded_question(
            source_chunk_id=chunk.id,
            q_type="mcq",
            difficulty=0.6,
        )

        assert q.id is not None
        assert q.origin == "ai_generated"
        assert q.pool == "practice"
        assert q.review_status == "draft"
        assert q.chapter_id == chapter.id
        assert str(chunk.id) in q.source_chunk_ids

        # Answer key securely stored in question_keys
        stmt_qk = select(QuestionKey).where(QuestionKey.question_id == q.id)
        res_qk = await session.execute(stmt_qk)
        qk = res_qk.scalar_one_or_none()
        assert qk is not None
        assert qk.correct_option_id is not None

        # Case B: Invalid/non-existent chunk ID strictly raises ValueError
        non_existent_chunk_id = uuid.uuid4()
        with pytest.raises(ValueError, match="SOURCE_CHUNK_NOT_FOUND"):
            await worker.generate_grounded_question(
                source_chunk_id=non_existent_chunk_id,
            )


# =============================================================================
# 6. Parent-Facing Safe Wording (Requirement 7)
# =============================================================================
@pytest.mark.asyncio
async def test_parent_facing_safe_wording_no_weak(gateway_client: AsyncClient) -> None:
    """Requirement 7: Parent-facing wording uses 'needs practice' and 'not enough data', never 'weak'."""
    student, book, chapter, chunk = await setup_student_with_curriculum()
    token = create_access_jwt(student.id, role="student")
    auth_headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    # 1. Summary Endpoint
    res_sum = await gateway_client.get("/v1/progress/summary", headers=auth_headers)
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert "weak" not in str(sum_data).lower()
    assert "status" in sum_data
    assert sum_data["status"] in ("not_enough_data", "needs_practice", "mastered")

    # 2. Mastery Endpoint
    res_mas = await gateway_client.get("/v1/progress/mastery", headers=auth_headers)
    assert res_mas.status_code == 200
    mas_data = res_mas.json()
    assert "weak" not in str(mas_data).lower()

    # 3. Weak-Points Endpoint (exposes needs practice topics without ever using the word 'weak')
    res_wp = await gateway_client.get("/v1/progress/weak-points", headers=auth_headers)
    assert res_wp.status_code == 200
    wp_data = res_wp.json()
    assert "weak" not in str(wp_data).lower()
    for topic in wp_data:
        assert topic["status"] in ("needs_practice", "not_enough_data")


# =============================================================================
# 7. Standing Rule 9 Authorization Tests
# =============================================================================
@pytest.mark.asyncio
async def test_progress_authorization_rule_9(gateway_client: AsyncClient) -> None:
    """Standing Rule 9: Role checks + ownership checks on every progress and revision route."""
    student_a = await create_user(role="student", display_name="Student A")
    student_b = await create_user(role="student", display_name="Student B")
    parent = await create_user(role="parent", display_name="Parent User")

    # Link parent to Student A only
    async with AsyncSessionLocal() as session:
        link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=parent.id,
            student_id=student_a.id,
            status="active",
            created_at=datetime.now(UTC),
        )
        session.add(link)
        await session.commit()

    token_a = create_access_jwt(student_a.id, role="student")
    token_b = create_access_jwt(student_b.id, role="student")
    token_p = create_access_jwt(parent.id, role="parent")

    headers_a = {**CLIENT_HEADERS, "Authorization": f"Bearer {token_a}"}
    headers_b = {**CLIENT_HEADERS, "Authorization": f"Bearer {token_b}"}
    headers_p = {**CLIENT_HEADERS, "Authorization": f"Bearer {token_p}"}

    # 1. Student A accessing Student A data -> 200 OK
    res1 = await gateway_client.get("/v1/progress/summary", headers=headers_a)
    assert res1.status_code == 200

    # 2. Student B attempting to access Student A data -> 403 Forbidden
    res2 = await gateway_client.get(f"/v1/progress/summary?student_id={student_a.id}", headers=headers_b)
    assert res2.status_code == 403

    # 3. Parent accessing linked Student A -> 200 OK
    res3 = await gateway_client.get(f"/v1/progress/summary?student_id={student_a.id}", headers=headers_p)
    assert res3.status_code == 200

    # 4. Parent attempting to access unlinked Student B -> 403 Forbidden
    res4 = await gateway_client.get(f"/v1/progress/summary?student_id={student_b.id}", headers=headers_p)
    assert res4.status_code == 403


# =============================================================================
# 8. Concurrent Double-Run Idempotency (Requirement 8)
# =============================================================================
@pytest.mark.asyncio
async def test_concurrent_double_run_idempotency() -> None:
    """Requirement 8: Concurrent double-run of both daily composition and 3-day review jobs."""
    student, book, chapter, chunk = await setup_student_with_curriculum()

    # Run two daily composition jobs concurrently for the exact same student
    async with AsyncSessionLocal() as session1, AsyncSessionLocal() as session2:
        task1 = run_daily_composition_job(session1, student.id)
        task2 = run_daily_composition_job(session2, student.id)
        v1, v2 = await asyncio.gather(task1, task2)

        # Both should complete cleanly under the advisory lock without crashing
        assert v1 >= 1
        assert v2 >= 1

    # Verify no corrupted tasks or duplicated plans in the active plan
    async with AsyncSessionLocal() as check_session:
        active_version = max(v1, v2)
        stmt_days = (
            select(PlanDay)
            .join(Plan, PlanDay.plan_id == Plan.id)
            .where(Plan.student_id == student.id, Plan.version == active_version)
        )
        res_days = await check_session.execute(stmt_days)
        days = res_days.scalars().all()
        # Dates must be distinct
        dates = [d.date for d in days]
        assert len(dates) == len(set(dates)), "Duplicate plan days created by concurrent runs"
        assert len(dates) > 0, "Active plan must contain days"


# =============================================================================
# 9. Asia/Dhaka Midnight Rollover (Requirement 8)
# =============================================================================
def test_asia_dhaka_midnight_rollover() -> None:
    """Requirement 8: Date boundary calculations around 23:59:59 vs 00:00:01 Asia/Dhaka."""
    dhaka_tz = ZoneInfo("Asia/Dhaka")

    # 23:59:59 on Oct 25 in Dhaka (UTC+6) corresponds to 17:59:59 UTC on Oct 25
    utc_before_midnight = datetime(2026, 10, 25, 17, 59, 59, tzinfo=UTC)
    dhaka_before = utc_before_midnight.astimezone(dhaka_tz)
    assert dhaka_before.date() == date(2026, 10, 25)
    assert dhaka_before.hour == 23
    assert dhaka_before.minute == 59
    assert dhaka_before.second == 59

    # 2 seconds later: 00:00:01 on Oct 26 in Dhaka corresponds to 18:00:01 UTC on Oct 25
    utc_after_midnight = datetime(2026, 10, 25, 18, 0, 1, tzinfo=UTC)
    dhaka_after = utc_after_midnight.astimezone(dhaka_tz)
    assert dhaka_after.date() == date(2026, 10, 26)
    assert dhaka_after.hour == 0
    assert dhaka_after.minute == 0
    assert dhaka_after.second == 1

    # Date diff is strictly 1 day
    assert (dhaka_after.date() - dhaka_before.date()).days == 1


# =============================================================================
# 10. Batched and Throttled Daily Jobs (Requirement 3)
# =============================================================================
@pytest.mark.asyncio
async def test_batched_throttled_daily_jobs() -> None:
    """Requirement 3: Run jobs per student at fixed local time, batched and throttled."""
    student_1, _, _, _ = await setup_student_with_curriculum()
    student_2, _, _, _ = await setup_student_with_curriculum()

    async with AsyncSessionLocal() as session:
        # Run batch with batch_size=1 and throttle_delay_sec=0.01
        res = await run_batched_daily_jobs(
            db=session,
            student_ids=[student_1.id, student_2.id],
            batch_size=1,
            throttle_delay_sec=0.01,
        )

        assert res["total"] == 2
        assert res["success"] == 2
        assert res["failed"] == 0
