"""Deterministic Student Mastery State Engine & Hierarchical Rollup Tracker.

State Transition Loop:
- On Wrong: unseen/recovering -> weak (wrong_count++, consecutive_correct=0, next_review_at=+24h, weakness_weight=min(5.0, 2.5+wrong*0.5), boost related topics)
- On Right: 
    - if weak -> recovering (consecutive_correct=1, weakness_weight=1.5, next_review_at=+3d)
    - if recovering (2nd right) or unseen -> mastered (consecutive_correct++, weakness_weight=0.2, recovered_from_wrong_count++ if wrong>0)
- Rollups updated atomically across book_topic -> chapter -> subject -> class.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import text


def to_uuid(val: Any) -> uuid.UUID:
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


class MasteryTracker:
    def __init__(self, db_session=None):
        self.db = db_session
        # In-memory storage structures for standalone and test execution
        self.history: List[Dict[str, Any]] = []
        self.states: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.rollups: Dict[str, Dict[str, Any]] = {}
        self.topic_boosts: Dict[str, float] = {}

    def get_state(self, user_id: str, question_id: str) -> Dict[str, Any]:
        key = (str(user_id), str(question_id))
        if key not in self.states:
            self.states[key] = {
                "user_id": str(user_id),
                "question_id": str(question_id),
                "status": "unseen",
                "wrong_count": 0,
                "correct_count": 0,
                "consecutive_correct": 0,
                "last_wrong_at": None,
                "last_correct_at": None,
                "next_review_at": None,
                "weakness_weight": 1.0
            }
        return self.states[key]

    def record_quiz_attempt(
        self,
        user_id: str,
        question: Dict[str, Any],
        is_correct: bool,
        quiz_mode: str = "daily_quiz",
        time_taken_sec: int = 30,
        now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Records an attempt, executes state transition, updates topic priority and rollups."""
        curr_time = now or datetime.now(timezone.utc)
        q_id = str(question.get("id"))
        u_id = str(user_id)
        
        # 1. Append history log
        history_entry = {
            "user_id": u_id,
            "question_id": q_id,
            "quiz_mode": quiz_mode,
            "is_correct": is_correct,
            "time_taken_sec": time_taken_sec,
            "attempted_at": curr_time
        }
        self.history.append(history_entry)

        # 2. State transition
        state = self.get_state(u_id, q_id)
        prev_status = state["status"]
        became_mastered = False
        was_recovered = False

        if not is_correct:
            # On Wrong
            state["status"] = "weak"
            state["wrong_count"] += 1
            state["consecutive_correct"] = 0
            state["last_wrong_at"] = curr_time
            state["next_review_at"] = curr_time + timedelta(hours=24)
            state["weakness_weight"] = round(min(5.0, 2.5 + state["wrong_count"] * 0.5), 2)
            
            # Boost priority of related prerequisite topics by +0.5
            for rel_topic_id in question.get("related_topic_ids", []):
                self.topic_boosts[str(rel_topic_id)] = self.topic_boosts.get(str(rel_topic_id), 1.0) + 0.5
        else:
            # On Right
            state["correct_count"] += 1
            state["last_correct_at"] = curr_time

            if prev_status == "weak":
                # Partial Recovery: 1st correct after wrong
                state["status"] = "recovering"
                state["consecutive_correct"] = 1
                state["weakness_weight"] = 1.5
                state["next_review_at"] = curr_time + timedelta(days=3)
            elif prev_status == "recovering":
                # Full Recovery: 2nd consecutive correct
                state["status"] = "mastered"
                state["consecutive_correct"] += 1
                state["weakness_weight"] = 0.2
                state["next_review_at"] = None
                became_mastered = True
                if state["wrong_count"] > 0:
                    was_recovered = True
            elif prev_status == "unseen":
                # Mastered on first attempt
                state["status"] = "mastered"
                state["consecutive_correct"] = 1
                state["weakness_weight"] = 0.2
                state["next_review_at"] = None
                became_mastered = True

        # 3. Update Materialized Rollups
        self._update_rollups(u_id, question, prev_status, state["status"], was_recovered)

        return {
            "user_id": u_id,
            "question_id": q_id,
            "previous_status": prev_status,
            "new_status": state["status"],
            "wrong_count": state["wrong_count"],
            "correct_count": state["correct_count"],
            "weakness_weight": state["weakness_weight"],
            "next_review_at": state["next_review_at"],
            "was_recovered": was_recovered
        }

    def _update_rollups(
        self,
        user_id: str,
        question: Dict[str, Any],
        prev_status: str,
        new_status: str,
        was_recovered: bool
    ):
        """Aggregates rollups across book_topic -> chapter -> subject -> class."""
        class_level = question.get("class_level", 8)
        subject = question.get("subject", "general")
        chapter_id = question.get("chapter_id")
        book_topic_id = question.get("book_topic_id")
        book_topic_name = question.get("book_topic_name")

        grains = [
            ("class", f"{user_id}_class_{class_level}", {"class_level": class_level}),
            ("subject", f"{user_id}_sub_{subject}", {"class_level": class_level, "subject": subject}),
            ("chapter", f"{user_id}_chap_{chapter_id}", {"class_level": class_level, "subject": subject, "chapter_id": chapter_id}),
            ("book_topic", f"{user_id}_top_{book_topic_id}", {"class_level": class_level, "subject": subject, "book_topic_id": book_topic_id, "book_topic_name": book_topic_name}),
        ]

        for grain_level, rollup_key, meta in grains:
            if rollup_key not in self.rollups:
                self.rollups[rollup_key] = {
                    "user_id": user_id,
                    "grain_level": grain_level,
                    "total_attempted": 0,
                    "weak_count": 0,
                    "recovering_count": 0,
                    "mastered_count": 0,
                    "recovered_from_wrong_count": 0,
                    "accuracy_pct": 0.0,
                    "mastery_pct": 0.0,
                    "needs_more_practice": False,
                    **meta
                }
            r = self.rollups[rollup_key]
            
            if prev_status == "unseen":
                r["total_attempted"] += 1

            # Adjust status counts
            if prev_status == "weak":
                r["weak_count"] = max(0, r["weak_count"] - 1)
            elif prev_status == "recovering":
                r["recovering_count"] = max(0, r["recovering_count"] - 1)
            elif prev_status == "mastered":
                r["mastered_count"] = max(0, r["mastered_count"] - 1)

            if new_status == "weak":
                r["weak_count"] += 1
            elif new_status == "recovering":
                r["recovering_count"] += 1
            elif new_status == "mastered":
                r["mastered_count"] += 1

            if was_recovered:
                r["recovered_from_wrong_count"] += 1

            # Compute percentages
            tot = r["total_attempted"]
            if tot > 0:
                r["mastery_pct"] = round((r["mastered_count"] / tot) * 100.0, 1)
                success_attempts = r["mastered_count"] + r["recovering_count"]
                r["accuracy_pct"] = round((success_attempts / tot) * 100.0, 1)
            
            # "আরও অনুশীলন দরকার" threshold
            r["needs_more_practice"] = (r["weak_count"] > 0) or (r["accuracy_pct"] < 70.0)

    async def record_quiz_attempt_db(
        self,
        db,
        user_id: str,
        question: Dict[str, Any],
        is_correct: bool,
        quiz_mode: str = "daily_quiz",
        time_taken_sec: int = 30,
        now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Runs deterministic state transition and persists to live PostgreSQL tables."""
        res = self.record_quiz_attempt(
            user_id=user_id,
            question=question,
            is_correct=is_correct,
            quiz_mode=quiz_mode,
            time_taken_sec=time_taken_sec,
            now=now
        )

        if db is None:
            return res

        curr_time = now or datetime.now(timezone.utc)
        u_uuid = to_uuid(user_id)
        q_uuid = to_uuid(question.get("id"))

        # Verify question exists in PostgreSQL before foreign key insert
        check_q = text("SELECT id FROM questions WHERE id = :qid;")
        row_exists = (await db.execute(check_q, {"qid": q_uuid})).fetchone()
        if not row_exists:
            return res

        # 1. Insert history
        ins_hist = text("""
            INSERT INTO student_question_history (id, user_id, question_id, quiz_mode, is_correct, time_taken_sec, attempted_at)
            VALUES (:id, :user_id, :question_id, :quiz_mode, :is_correct, :time_taken_sec, :attempted_at);
        """)
        await db.execute(ins_hist, {
            "id": uuid.uuid4(),
            "user_id": u_uuid,
            "question_id": q_uuid,
            "quiz_mode": quiz_mode,
            "is_correct": is_correct,
            "time_taken_sec": time_taken_sec,
            "attempted_at": curr_time
        })

        # 2. Upsert student_question_state
        state = self.get_state(str(user_id), str(question.get("id")))
        ins_state = text("""
            INSERT INTO student_question_state (
                user_id, question_id, status, wrong_count, correct_count,
                consecutive_correct, last_wrong_at, last_correct_at, next_review_at, weakness_weight, updated_at
            ) VALUES (
                :user_id, :question_id, :status, :wrong_count, :correct_count,
                :consecutive_correct, :last_wrong_at, :last_correct_at, :next_review_at, :weakness_weight, :curr_time
            ) ON CONFLICT (user_id, question_id) DO UPDATE SET
                status = EXCLUDED.status,
                wrong_count = EXCLUDED.wrong_count,
                correct_count = EXCLUDED.correct_count,
                consecutive_correct = EXCLUDED.consecutive_correct,
                last_wrong_at = EXCLUDED.last_wrong_at,
                last_correct_at = EXCLUDED.last_correct_at,
                next_review_at = EXCLUDED.next_review_at,
                weakness_weight = EXCLUDED.weakness_weight,
                updated_at = EXCLUDED.updated_at;
        """)
        await db.execute(ins_state, {
            "user_id": u_uuid,
            "question_id": q_uuid,
            "status": state["status"],
            "wrong_count": state["wrong_count"],
            "correct_count": state["correct_count"],
            "consecutive_correct": state["consecutive_correct"],
            "last_wrong_at": state["last_wrong_at"],
            "last_correct_at": state["last_correct_at"],
            "next_review_at": state["next_review_at"],
            "weakness_weight": state["weakness_weight"],
            "curr_time": curr_time
        })

        # 3. Upsert student_progress_rollups (Class Grain)
        c_level = int(question.get("class_level", 8))
        class_key = f"{user_id}_class_{c_level}"
        r = self.rollups.get(class_key)
        if r:
            ins_rollup = text("""
                INSERT INTO student_progress_rollups (
                    id, user_id, grain_level, class_level, total_attempted,
                    weak_count, recovering_count, mastered_count, recovered_from_wrong_count,
                    accuracy_pct, mastery_pct, needs_more_practice, updated_at
                ) VALUES (
                    :id, :user_id, 'class', :class_level, :total_attempted,
                    :weak_count, :recovering_count, :mastered_count, :recovered_from_wrong_count,
                    :accuracy_pct, :mastery_pct, :needs_more_practice, :curr_time
                ) ON CONFLICT ON CONSTRAINT uq_student_rollup DO UPDATE SET
                    total_attempted = EXCLUDED.total_attempted,
                    weak_count = EXCLUDED.weak_count,
                    recovering_count = EXCLUDED.recovering_count,
                    mastered_count = EXCLUDED.mastered_count,
                    recovered_from_wrong_count = EXCLUDED.recovered_from_wrong_count,
                    accuracy_pct = EXCLUDED.accuracy_pct,
                    mastery_pct = EXCLUDED.mastery_pct,
                    needs_more_practice = EXCLUDED.needs_more_practice,
                    updated_at = EXCLUDED.updated_at;
            """)
            try:
                await db.execute(ins_rollup, {
                    "id": uuid.uuid4(),
                    "user_id": u_uuid,
                    "class_level": c_level,
                    "total_attempted": r["total_attempted"],
                    "weak_count": r["weak_count"],
                    "recovering_count": r["recovering_count"],
                    "mastered_count": r["mastered_count"],
                    "recovered_from_wrong_count": r["recovered_from_wrong_count"],
                    "accuracy_pct": r["accuracy_pct"],
                    "mastery_pct": r["mastery_pct"],
                    "needs_more_practice": r["needs_more_practice"],
                    "curr_time": curr_time
                })
            except Exception:
                pass

        await db.commit()
        return res
