"""Smart Shuffle & Deterministic Quiz Generators (Daily Quiz 40/40/20 & Practice Quiz).

Enforces:
- Standing Rule 5: Server is the authority.
- Standing Rule 6: Never send answer keys or explanations to clients before submission!
- Standing Rule 13: Bangla and English everywhere (UI Badges).
"""

import re
import math
import random
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from services.mastery_tracker import MasteryTracker


from core.common.latex_normalizer import normalize_latex


def scrub_answer_keys(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Strictly redacts correct_answer and explanation_text before sending to clients (Standing Rule 6).
    Also strips leading numbering artifacts ('১.', '২.', 'ক.') cleanly, strips leaked board references,
    normalizes LaTeX delimiters, and attaches structured options.
    """
    sanitized = []
    for q in questions:
        q_copy = dict(q)
        q_copy.pop("correct_answer", None)
        q_copy.pop("explanation_text", None)
        if "question_text" in q_copy and q_copy["question_text"]:
            text_clean = re.sub(
                r"^(?:[০-৯0-9]+|[ক-হa-zA-Z]|[iI]{1,3}|[ivxIVX]+)[\.\:\-\)]\s*",
                "",
                q_copy["question_text"]
            ).strip()
            # Clean trailing textbook printing footer artifacts (e.g. ফর্ম-৫, চারু ও কারুকলা)
            text_clean = re.sub(r"\s*(?:ফর্ম|ফর্মা)[\-\s]*[০-৯0-9]+.*$", "", text_clean).strip()
            # Strip leaked board-paper numbering references
            text_clean = re.sub(
                r'([০-৯0-9]+\s*(?:ও|,|এবং|-)\s*)?[০-৯0-9]+\s*নং\s*প্রশ্নের\s*উত্তর\s*দাও',
                'নিচের উদ্দীপকের আলোকে প্রশ্নটির উত্তর দাও',
                text_clean
            ).strip()
            # Normalize LaTeX ($$$ -> $, set braces, chem arrows)
            text_clean = normalize_latex(text_clean)
            q_copy["question_text"] = text_clean

        # Normalize options
        opts = q_copy.get("options")
        if opts is None and q_copy.get("options_json") is not None:
            opts = q_copy.get("options_json")
        if isinstance(opts, str):
            try:
                opts = json.loads(opts)
            except Exception:
                opts = None
        if isinstance(opts, list):
            opts = [normalize_latex(str(opt)) for opt in opts]
        q_copy["options"] = opts

        sanitized.append(q_copy)
    return sanitized


ACTIVITY_PROMPT_PATTERN = re.compile(
    r'(খাতায় তৈরি করো|দলে আলোচনা করো|তালিকা তৈরি করো|খাতায় লেখো|খাতায় আঁকো|তোমার খাতায়|পোস্টার তৈরি করো|খাতায় ছক এঁকে)'
)

def is_activity_prompt(q: Dict[str, Any]) -> bool:
    if q.get("is_auto_gradable") is False:
        return True
    return bool(ACTIVITY_PROMPT_PATTERN.search(q.get("question_text", "")))


class QuizGenerator:
    def __init__(self, questions_pool: List[Dict[str, Any]], tracker: Optional[MasteryTracker] = None):
        self.pool = questions_pool
        self.tracker = tracker or MasteryTracker()

    def get_shuffled_practice_set(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Multi-dimensional filtering and weighted shuffling."""
        filters = filters or {}
        candidates = [q for q in self.pool if not is_activity_prompt(q)]

        # 1. Apply Filters
        if "class_level" in filters:
            candidates = [q for q in candidates if q.get("class_level") == filters["class_level"]]
        if "subject" in filters:
            sub = filters["subject"].lower()
            candidates = [q for q in candidates if sub in q.get("subject", "").lower()]
        if "chapter_id" in filters:
            candidates = [q for q in candidates if q.get("chapter_id") == filters["chapter_id"]]
        if "book_topic_id" in filters:
            candidates = [q for q in candidates if q.get("book_topic_id") == filters["book_topic_id"]]
        if "format" in filters:
            candidates = [q for q in candidates if q.get("format") == filters["format"]]
        if "cognitive_tier" in filters:
            candidates = [q for q in candidates if q.get("cognitive_tier") == filters["cognitive_tier"]]
        if "source_type" in filters:
            candidates = [q for q in candidates if q.get("source_type") == filters["source_type"]]

        # Focus mode filtering
        focus = filters.get("focus_mode", "all")
        if focus == "mistakes_only":
            candidates = [
                q for q in candidates 
                if self.tracker.get_state(user_id, q["id"])["status"] in ("weak", "recovering")
            ]
        elif focus == "unseen_only":
            candidates = [
                q for q in candidates 
                if self.tracker.get_state(user_id, q["id"])["status"] == "unseen"
            ]
        elif focus == "high_importance":
            candidates = [q for q in candidates if q.get("importance_score", 1.0) >= 3.0]

        # 2. Weighted Sorting
        def compute_weight(q: Dict[str, Any]) -> float:
            st = self.tracker.get_state(user_id, q["id"])
            w_weakness = st.get("weakness_weight", 1.0)
            w_importance = q.get("importance_score", 1.0)
            w_rep = q.get("repetitiveness_score", 1.0)
            boost = self.tracker.topic_boosts.get(str(q.get("book_topic_id")), 1.0)
            return w_weakness * w_importance * (1.0 + 0.2 * w_rep) * boost

        candidates.sort(key=compute_weight, reverse=True)
        return candidates[:limit]

    def generate_daily_quiz(
        self,
        user_id: str,
        class_level: int,
        limit: int = 12,
        now: Optional[datetime] = None,
        subject: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generates Daily Quiz with deterministic 40/40/20 distribution & subject diversity:
        - 40% Mistake Recovery (Overdue weak & recovering questions)
        - 40% High-Yield Syllabus (Unseen, high importance & repetitiveness)
        - 20% Related Topics (Prerequisites of weak topics)
        - Subject diversity caps: max 2 per subject for limit<=5, max 3-4 per subject for limit<=12.
        Attaches Bengali UI badges.
        """
        curr_time = now or datetime.now(timezone.utc)

        def is_orphaned_cq(q: Dict[str, Any]) -> bool:
            txt = q.get("question_text", "")
            if not q.get("uddipok_id") and not q.get("uddipok_text"):
                if any(w in txt for w in ("উদ্দীপক", "অনুচ্ছেদ", "আশরাফের শিক্ষাজীবন")):
                    if not ("\n" in txt and len(txt) > 60):
                        return True
            return False

        class_questions = [
            q for q in self.pool 
            if q.get("class_level") == class_level and not is_orphaned_cq(q) and not is_activity_prompt(q)
        ]

        is_single_subject = bool(subject)
        if is_single_subject:
            max_per_subject = limit
        elif limit <= 5:
            max_per_subject = 2
        elif limit <= 8:
            max_per_subject = 3
        elif limit <= 12:
            max_per_subject = 4
        else:
            max_per_subject = max(3, math.ceil(limit / 3))

        subject_counts: Dict[str, int] = {}
        topic_counts: Dict[str, int] = {}
        max_per_topic = 2  # per-topic diversity cap

        def get_subj(q: Dict[str, Any]) -> str:
            return str(q.get("subject", "general")).lower()

        def get_topic(q: Dict[str, Any]) -> str:
            return str(q.get("book_topic_name") or q.get("book_topic_id") or "general").strip().lower()

        def can_add(q: Dict[str, Any], relax_subject: bool = False, relax_topic: bool = False) -> bool:
            t = get_topic(q)
            if not relax_topic and topic_counts.get(t, 0) >= max_per_topic:
                return False
            if is_single_subject or relax_subject:
                return True
            return subject_counts.get(get_subj(q), 0) < max_per_subject

        def record_add(q: Dict[str, Any]):
            s = get_subj(q)
            subject_counts[s] = subject_counts.get(s, 0) + 1
            t = get_topic(q)
            topic_counts[t] = topic_counts.get(t, 0) + 1

        # Targets
        n_recovery = max(1, int(limit * 0.40))  # ~5 items
        n_yield = max(1, int(limit * 0.40))     # ~5 items
        n_related = limit - (n_recovery + n_yield) # ~2 items

        # Bucket 1: Mistake Recovery (overdue weak/recovering)
        recovery_pool = []
        weak_topic_ids = set()
        for q in class_questions:
            st = self.tracker.get_state(user_id, q["id"])
            if st["status"] in ("weak", "recovering"):
                weak_topic_ids.add(str(q.get("book_topic_id")))
                next_rev = st.get("next_review_at")
                if not next_rev or next_rev <= curr_time:
                    recovery_pool.append((q, st.get("weakness_weight", 1.0)))

        recovery_pool.sort(key=lambda x: x[1], reverse=True)
        selected_recovery = []
        selected_ids = set()
        for q, w in recovery_pool:
            if len(selected_recovery) >= n_recovery:
                break
            if can_add(q):
                q["ui_badge"] = "আগে ভুল হয়েছিল — আবার চেষ্টা করো"
                selected_recovery.append(q)
                selected_ids.add(q["id"])
                record_add(q)

        # Bucket 2: High-Yield Syllabus (Unseen, high importance)
        yield_pool = []
        for q in class_questions:
            if q["id"] in selected_ids:
                continue
            st = self.tracker.get_state(user_id, q["id"])
            if st["status"] == "unseen":
                score = q.get("importance_score", 1.0) * (1.0 + 0.3 * q.get("repetitiveness_score", 1.0))
                yield_pool.append((q, score))

        yield_by_sub: Dict[str, List[Tuple[Dict[str, Any], float]]] = {}
        for q, score in yield_pool:
            yield_by_sub.setdefault(get_subj(q), []).append((q, score))
        for s in yield_by_sub:
            yield_by_sub[s].sort(key=lambda x: x[1], reverse=True)

        selected_yield = []
        sub_keys = list(yield_by_sub.keys())
        while len(selected_yield) < n_yield and any(yield_by_sub[s] for s in sub_keys):
            added_in_round = False
            for s in sub_keys:
                if len(selected_yield) >= n_yield:
                    break
                queue = yield_by_sub[s]
                while queue:
                    candidate, score = queue.pop(0)
                    if candidate["id"] not in selected_ids and can_add(candidate):
                        if candidate.get("repetitiveness_score", 1.0) >= 2.0:
                            candidate["ui_badge"] = "বোর্ডে বারবার এসেছে"
                        else:
                            candidate["ui_badge"] = "গুরুত্বপূর্ণ টপিক"
                        selected_yield.append(candidate)
                        selected_ids.add(candidate["id"])
                        record_add(candidate)
                        added_in_round = True
                        break
            if not added_in_round:
                break

        # Bucket 3: Related Topics (Prerequisites of weak topics)
        related_pool = []
        for q in class_questions:
            if q["id"] in selected_ids:
                continue
            is_related = False
            for r_id in q.get("related_topic_ids", []):
                if str(r_id) in weak_topic_ids:
                    is_related = True
                    break
            if is_related or str(q.get("book_topic_id")) in self.tracker.topic_boosts:
                related_pool.append(q)

        if len(related_pool) < n_related:
            remaining = [q for q in class_questions if q["id"] not in selected_ids and q not in related_pool]
            remaining.sort(key=lambda x: x.get("importance_score", 1.0), reverse=True)
            related_pool.extend(remaining[:(n_related * 2)])

        related_by_sub: Dict[str, List[Dict[str, Any]]] = {}
        for q in related_pool:
            related_by_sub.setdefault(get_subj(q), []).append(q)

        selected_related = []
        r_sub_keys = list(related_by_sub.keys())
        while len(selected_related) < n_related and any(related_by_sub[s] for s in r_sub_keys):
            added_in_round = False
            for s in r_sub_keys:
                if len(selected_related) >= n_related:
                    break
                queue = related_by_sub[s]
                while queue:
                    candidate = queue.pop(0)
                    if candidate["id"] not in selected_ids and can_add(candidate):
                        candidate["ui_badge"] = "সম্পর্কিত টপিক"
                        selected_related.append(candidate)
                        selected_ids.add(candidate["id"])
                        record_add(candidate)
                        added_in_round = True
                        break
            if not added_in_round:
                break

        final_quiz = selected_recovery + selected_yield + selected_related

        # Backfill if any bucket was short
        if len(final_quiz) < limit:
            remaining = [q for q in class_questions if q["id"] not in selected_ids]
            remaining.sort(key=lambda x: x.get("importance_score", 1.0), reverse=True)
            # Pass A: respect subject and topic caps
            for q in remaining:
                if len(final_quiz) >= limit:
                    break
                if can_add(q):
                    q_copy = dict(q)
                    q_copy["ui_badge"] = "গুরুত্বপূর্ণ টপিক"
                    final_quiz.append(q_copy)
                    selected_ids.add(q["id"])
                    record_add(q)

            # Pass B: relax subject cap, keep topic cap
            if len(final_quiz) < limit:
                for q in remaining:
                    if len(final_quiz) >= limit:
                        break
                    if q["id"] not in selected_ids and can_add(q, relax_subject=True):
                        q_copy = dict(q)
                        q_copy["ui_badge"] = "গুরুত্বপূর্ণ টপিক"
                        final_quiz.append(q_copy)
                        selected_ids.add(q["id"])
                        record_add(q)

            # Pass C: if still under limit, relax topic cap to satisfy limit
            if len(final_quiz) < limit:
                for q in remaining:
                    if len(final_quiz) >= limit:
                        break
                    if q["id"] not in selected_ids and can_add(q, relax_subject=True, relax_topic=True):
                        q_copy = dict(q)
                        q_copy["ui_badge"] = "গুরুত্বপূর্ণ টপিক"
                        final_quiz.append(q_copy)
                        selected_ids.add(q["id"])
                        record_add(q)

        # Redact answer keys before returning to client (Standing Rule 6)
        return scrub_answer_keys(final_quiz)

    def generate_practice_quiz(
        self,
        user_id: str,
        filters: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Generates Practice Quiz with multi-filter and zero-answer-key delivery."""
        practice_set = self.get_shuffled_practice_set(user_id, filters, limit)
        return scrub_answer_keys(practice_set)
