"""Seed database with complete realistic P08 Web App data (Tasks 1 & 4).

Seeds:
- Parent user ("রফিকুল ইসলাম", r@example.com)
- Student user ("তাহমিদ আলিম", tahmid@example.com)
- Family ("আলিম পরিবার") and active ParentStudentLink
- StudentProfile (Class 7, Medium 'bn', Group 'general')
- StudentStudySettings with active auto-adjustment for 1-tap undo test
- Plan and 3 daily Tasks for student's Home/Today screen
- Pending AI Suggestion (Math syllabus coverage increase)
- Pending Student Change Request (School sports day temporary reduction)
- Completed Practice Quiz Attempt with unlocked AttemptItems for Quiz Review
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid

from sqlalchemy import select

from core.auth.models import User
from core.common.database import AsyncSessionLocal
from core.common.time import utcnow
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile
from core.planner.models import (
    Plan,
    PlanDay,
    StudentChangeRequest,
    StudentStudySettings,
    Task,
)
from core.quiz.models import AttemptItem, Question, QuestionKey, Quiz, QuizAttempt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PARENT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STUDENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
FAMILY_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
QUIZ_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
ATTEMPT_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
PLAN_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


async def seed_data() -> None:
    async with AsyncSessionLocal() as session:
        # 1. Parent User
        stmt = select(User).where(User.id == PARENT_ID)
        res = await session.execute(stmt)
        parent = res.scalar_one_or_none()
        if not parent:
            parent = User(
                id=PARENT_ID,
                phone="+8801700000001",
                email="r@example.com",
                role="parent",
                display_name="রফিকুল ইসলাম (Rafiqul Islam)",
                status="active",
                locale="bn",
                auth_provider="fake",
                auth_uid="fake_parent_r",
            )
            session.add(parent)
            logger.info("Created parent user %s", PARENT_ID)

        # 2. Student User
        stmt = select(User).where(User.id == STUDENT_ID)
        res = await session.execute(stmt)
        student = res.scalar_one_or_none()
        if not student:
            student = User(
                id=STUDENT_ID,
                phone="+8801700000002",
                email="tahmid@example.com",
                role="student",
                display_name="তাহমিদ আলিম (Tahmid Alim)",
                status="active",
                locale="bn",
                auth_provider="family_invite",
                auth_uid="fake_student_tahmid",
            )
            session.add(student)
            logger.info("Created student user %s", STUDENT_ID)

        await session.flush()

        # 3. Family
        stmt = select(Family).where(Family.id == FAMILY_ID)
        res = await session.execute(stmt)
        family = res.scalar_one_or_none()
        if not family:
            family = Family(
                id=FAMILY_ID,
                name="আলিম পরিবার (Alim Family)",
                owner_parent_id=PARENT_ID,
            )
            session.add(family)

        # 4. StudentProfile
        stmt = select(StudentProfile).where(StudentProfile.user_id == STUDENT_ID)
        res = await session.execute(stmt)
        prof = res.scalar_one_or_none()
        if not prof:
            prof = StudentProfile(
                user_id=STUDENT_ID,
                class_level=7,
                group="general",
                medium="bn",
                school="ঢাকা রেসিডেন্সিয়াল মডেল কলেজ",
                daily_minutes=150,
            )
            session.add(prof)

        # 5. ParentStudentLink
        stmt = select(ParentStudentLink).where(
            ParentStudentLink.parent_id == PARENT_ID,
            ParentStudentLink.student_id == STUDENT_ID,
        )
        res = await session.execute(stmt)
        link = res.scalar_one_or_none()
        if not link:
            link = ParentStudentLink(
                id=uuid.uuid4(),
                parent_id=PARENT_ID,
                student_id=STUDENT_ID,
                family_id=FAMILY_ID,
                status="active",
            )
            session.add(link)

        # 6. StudentStudySettings with Auto-Adjustment for Undo
        stmt = select(StudentStudySettings).where(StudentStudySettings.student_id == STUDENT_ID)
        res = await session.execute(stmt)
        study_settings = res.scalar_one_or_none()
        if not study_settings:
            study_settings = StudentStudySettings(
                student_id=STUDENT_ID,
                school_day_minutes=150,
                holiday_minutes=240,
                study_window_start="17:00",
                study_window_end="21:30",
                rest_weekday="fri",
                adaptive_mode=True,
                version=1,
                ai_adjustments={
                    "recent_adjustments": [
                        {
                            "adjustment_id": "adj_1",
                            "title": "বিজ্ঞান বিষয়ের রিভিশন টাস্ক অগ্রাধিকার সমন্বয়",
                            "reason": "পূর্ববর্তী কুইজ বিশ্লেষণের প্রেক্ষিতে অধ্যায় ৪ এর জন্য সময় বরাদ্দ বৃদ্ধি করা হয়েছে।",
                            "applied_at": "2026-10-26T18:00:00Z",
                            "undone": False,
                            "previous_school_day_minutes": 150,
                            "adjusted_school_day_minutes": 165,
                        }
                    ]
                },
            )
            session.add(study_settings)

        # 7. AI Suggestion
        stmt = select(StudentChangeRequest).where(
            StudentChangeRequest.student_id == STUDENT_ID,
            StudentChangeRequest.status == "pending",
        )
        res = await session.execute(stmt)
        requests = res.scalars().all()
        if not any(r.requested_changes.get("type") == "ai_priority_suggestion" for r in requests):
            sug = StudentChangeRequest(
                id=uuid.uuid4(),
                student_id=STUDENT_ID,
                requested_by_user_id=PARENT_ID,
                status="pending",
                requested_changes={
                    "type": "ai_priority_suggestion",
                    "subject": "বিজ্ঞান",
                    "field": "pacing",
                    "current_minutes": 150,
                    "suggested_minutes": 165,
                    "evidence_codes": ["LOW_MASTERY_CH4", "UPCOMING_EXAM"],
                    "rationale": "Exam in 14 days; science chapter 4 needs review pacing.",
                    "rationale_bn": "আসন্ন অর্ধবার্ষিক পরীক্ষার পূর্বে বিজ্ঞান বিষয়ের সিলেবাস কভারেজ সুনিশ্চিত করতে দৈনিক পড়ার সময় ১৫ মিনিট বৃদ্ধির প্রস্তাব।",
                },
            )
            session.add(sug)

        # 8. Student Change Request
        if not any(r.requested_changes.get("type") == "student_request" for r in requests):
            cr = StudentChangeRequest(
                id=uuid.uuid4(),
                student_id=STUDENT_ID,
                requested_by_user_id=STUDENT_ID,
                status="pending",
                requested_changes={
                    "type": "student_request",
                    "requested_school_day_minutes": 120,
                    "reason": "বিদ্যালয়ের বার্ষিক ক্রীড়া প্রতিযোগিতা অনুশীলনের জন্য পড়ার সময় সাময়িক কমানোর অনুরোধ।",
                },
            )
            session.add(cr)

        # 9. Plan and Today's Tasks
        stmt = select(Plan).where(Plan.id == PLAN_ID)
        res = await session.execute(stmt)
        plan = res.scalar_one_or_none()
        today_date = utcnow().date()

        if not plan:
            plan = Plan(
                id=PLAN_ID,
                student_id=STUDENT_ID,
                version=1,
                status="active",
                valid_from=today_date,
                valid_to=today_date + datetime.timedelta(days=14),
            )
            session.add(plan)
            await session.flush()

            plan_day = PlanDay(
                id=uuid.uuid4(),
                plan_id=PLAN_ID,
                day_date=today_date,
                day_type="school_day",
                study_minutes=150,
            )
            session.add(plan_day)
            await session.flush()

            t1 = Task(
                id=uuid.uuid4(),
                plan_day_id=plan_day.id,
                subject="বিজ্ঞান",
                title="সালোকসংশ্লেষণ ও ক্লোরোপ্লাস্টের ভূমিকা",
                task_type="study",
                allocated_minutes=45,
                status="completed",
                guidelines="পাঠ্যবইয়ের ৪২-৪৪ পৃষ্ঠা মনোযোগ সহকারে পড়ুন এবং চিত্র ৪.১ আঁকুন।",
                printed_page_start=42,
                printed_page_end=44,
            )
            t2 = Task(
                id=uuid.uuid4(),
                plan_day_id=plan_day.id,
                subject="গণিত",
                title="বীজগণিতীয় সূত্রাবলি ও প্রয়োগ",
                task_type="study",
                allocated_minutes=45,
                status="pending",
                guidelines="অনুশীলনী ৫.১ এর ১ থেকে ৫ নম্বর সমস্যা সমাধান করুন।",
                printed_page_start=78,
                printed_page_end=80,
            )
            t3 = Task(
                id=uuid.uuid4(),
                plan_day_id=plan_day.id,
                subject="ইংরেজি",
                title="স্পেসড রিভিশন: Tense & Verb Forms",
                task_type="revision",
                allocated_minutes=30,
                status="pending",
                guidelines="পূর্ববর্তী বক্সের পুনরাবৃত্তিমূলক নিয়মাবলী চোখ বুলিয়ে নিন।",
                printed_page_start=22,
                printed_page_end=24,
            )
            session.add_all([t1, t2, t3])

        # 10. Completed Quiz Attempt with Review
        stmt = select(Quiz).where(Quiz.id == QUIZ_ID)
        res = await session.execute(stmt)
        quiz = res.scalar_one_or_none()
        if not quiz:
            quiz = Quiz(
                id=QUIZ_ID,
                title="বিজ্ঞান কুইজ: উদ্ভিদের খাদ্য উৎপাদন",
                subject="বিজ্ঞান",
                class_level=7,
                mode="practice",
                time_limit_sec=900,
                status="published",
            )
            session.add(quiz)
            await session.flush()

            q1 = Question(
                id=uuid.uuid4(),
                quiz_id=QUIZ_ID,
                position=1,
                stem="উদ্ভিদের সালোকসংশ্লেষণ প্রক্রিয়ায় কোন গ্যাস নির্গত হয়?",
                options=[
                    {"id": "opt_a", "text": "কার্বন ডাই অক্সাইড"},
                    {"id": "opt_b", "text": "অক্সিজেন"},
                    {"id": "opt_c", "text": "নাইট্রোজেন"},
                    {"id": "opt_d", "text": "হাইড্রোজেন"},
                ],
            )
            session.add(q1)
            await session.flush()

            qk1 = QuestionKey(
                question_id=q1.id,
                correct_option_id="opt_b",
                explanation="সালোকসংশ্লেষণের আলোক পর্যায়ে পানি ভেঙে উপজাত হিসেবে অক্সিজেন গ্যাস নির্গত হয়।",
            )
            session.add(qk1)

            attempt = QuizAttempt(
                id=ATTEMPT_ID,
                quiz_id=QUIZ_ID,
                student_id=STUDENT_ID,
                mode="practice",
                status="completed",
                score=1,
                total_items=1,
                submitted_at=utcnow(),
            )
            session.add(attempt)
            await session.flush()

            att_item = AttemptItem(
                id=uuid.uuid4(),
                attempt_id=ATTEMPT_ID,
                question_id=q1.id,
                position=1,
                selected_option_id="opt_b",
                is_correct=True,
                answered_at=utcnow(),
            )
            session.add(att_item)

        await session.commit()
        logger.info("Successfully seeded all P08 e2e database entities.")


if __name__ == "__main__":
    asyncio.run(seed_data())
