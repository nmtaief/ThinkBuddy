"""Message understanding, entity extraction, and scope resolution for ThinkBuddy AI Tutor.

Extracts structured query context from student messages:
- class_level (6-10, 'SSC' -> 9/10)
- subject (math, science, english, bangla)
- chapter (number or keyword)
- exercise_label ('অনুশীলনী ১', '9.1', 'ex 1.1')
- question_no (int, e.g. 3, 5)
- subpart ('ক', 'খ', 'a', 'b')

Scope Hierarchy: Explicit in current message > Earlier conversation turns > Student profile default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Bengali to ASCII digits translation
BANGLA_DIGIT_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def normalize_digits(text: str) -> str:
    """Translate Bengali digits to standard ASCII digits."""
    return text.translate(BANGLA_DIGIT_MAP)


@dataclass
class ExtractedIntent:
    """Structured understanding of student message."""

    raw_query: str
    class_level: int | None = None
    subject: str | None = None
    chapter: str | None = None
    exercise_label: str | None = None
    question_no: int | None = None
    subpart: str | None = None
    is_retry: bool = False
    is_asking_library: bool = False


# Known NCTB chapter names across curriculum
CHAPTER_NAME_MAP: dict[str, tuple[str, str]] = {
    "প্যাটার্ন": ("math", "1"),
    "pattern": ("math", "1"),
    "মুনাফা": ("math", "2"),
    "profit": ("math", "2"),
    "perimap": ("math", "3"),
    "পরিমাপ": ("math", "3"),
    "measurement": ("math", "3"),
    "বীজগণিতীয় সূত্রাবলী": ("math", "4"),
    "বীজগণিতীয় ভগ্নাংশ": ("math", "5"),
    "সরল সহসমীকরণ": ("math", "6"),
    "সেট": ("math", "7"),
    "set": ("math", "7"),
    "চতুর্ভুজ": ("math", "8"),
    "quadrilateral": ("math", "8"),
    "পিথাগোরাস": ("math", "9"),
    "pythagoras": ("math", "9"),
    "বৃত্ত": ("math", "10"),
    "circle": ("math", "10"),
    "তথ্য ও উপাত্ত": ("math", "11"),
    "পরিসংখ্যান": ("math", "11"),
    "statistics": ("math", "11"),
    "stat": ("math", "11"),
    "ত্রিকোণমিতি": ("math", "9"),
    "trigonometry": ("math", "9"),
    "সালোকসংশ্লেষণ": ("science", "14"),
    "photosynthesis": ("science", "14"),
    "বাস্তুতন্ত্র": ("science", "14"),
    "ecosystem": ("science", "14"),
    "ব্যাপন": ("science", "3"),
    "অভিস্রবণ": ("science", "3"),
    "পরমাণু": ("science", "6"),
    "মহাকর্ষ": ("science", "7"),
    "gravity": ("science", "7"),
}


def parse_student_intent(text: str) -> ExtractedIntent:
    """Parse text and extract educational entities."""
    clean = normalize_digits(text).strip()
    clean_lower = clean.lower()

    intent = ExtractedIntent(raw_query=text)

    # 1. Retry detection
    retry_triggers = ["try again", "আবার চেষ্টা করো", "আবার চেষ্টা কর", "retry", "আবার বলো", "আবার বলো তো"]
    if clean_lower in retry_triggers or any(clean_lower.startswith(t) for t in retry_triggers):
        intent.is_retry = True
        return intent

    # 2. Asking library books
    library_triggers = [
        "what books", "which books", "kon boi", "kon kon boi", "books available",
        "library", "বই আছে", "কোন বই", "কী কী বই", "কি কি বই", "ssc books", "ssc boi",
        "বইগুলো কী", "বইগুলো কি"
    ]
    if any(t in clean_lower for t in library_triggers):
        intent.is_asking_library = True

    # 3. Class detection
    # Check explicit SSC / HSC
    if re.search(r"\b(ssc|এসএসসি|class\s*(?:9|10)|৯ম|১০ম|নবম|দশম)\b", clean_lower):
        intent.class_level = 9  # SSC maps to Class 9-10
    else:
        m_cls = re.search(r"\b(?:class|শ্রেণি|ক্লাস)\s*([6-9]|10)\b", clean_lower)
        if m_cls:
            intent.class_level = int(m_cls.group(1))
        elif re.search(r"\b(?:৬ষ্ঠ|ষষ্ঠ)\b", clean_lower):
            intent.class_level = 6
        elif re.search(r"\b(?:৭ম|সপ্তম)\b", clean_lower):
            intent.class_level = 7
        elif re.search(r"\b(?:৮ম|অষ্টম)\b", clean_lower):
            intent.class_level = 8
        elif re.search(r"\b(?:৯ম|নবম)\b", clean_lower):
            intent.class_level = 9
        elif re.search(r"\b(?:১০ম|দশম)\b", clean_lower):
            intent.class_level = 10

    # 4. Subject detection
    if any(w in clean_lower for w in ["math", "maths", "গণিত", "gonit", "onko", "অঙ্ক", "algebra", "geometry", "trigonometry", "ত্রিকোণমিতি", "পরিসংখ্যান", "statistics"]):
        intent.subject = "math"
    elif any(w in clean_lower for w in ["science", "বিজ্ঞান", "biggan", "biology", "physics", "chemistry"]):
        intent.subject = "science"
    elif any(w in clean_lower for w in ["english", "ইংরেজি", "eng"]):
        intent.subject = "english"
    elif any(w in clean_lower for w in ["bangla", "বাংলা"]):
        intent.subject = "bangla"

    # 5. Chapter detection
    m_ch = re.search(r"\b(?:chapter|অধ্যায়|অধ্যায়|ch|chap)\s*([0-9]+)\b", clean_lower)
    if m_ch:
        intent.chapter = m_ch.group(1)

    for ch_name, (subj, ch_num) in CHAPTER_NAME_MAP.items():
        if ch_name in clean_lower:
            if not intent.subject:
                intent.subject = subj
            if not intent.chapter:
                intent.chapter = ch_num
            break

    # 6. Exercise label detection (e.g. 9.1, 1.1, অনুশীলনী ১, ex 1.2)
    m_ex = re.search(r"\b(?:অনুশীলনী|onushiloni|exercise|ex)\s*([0-9]+(?:\.[0-9]+)?)\b", clean_lower)
    if m_ex:
        intent.exercise_label = f"অনুশীলনী {m_ex.group(1)}"
        if "." in m_ex.group(1):
            intent.chapter = m_ex.group(1).split(".")[0]
    else:
        # Standalone decimal like "9.1 er 5 no"
        m_dec = re.search(r"\b([0-9]+\.[0-9]+)\b", clean_lower)
        if m_dec:
            intent.exercise_label = f"অনুশীলনী {m_dec.group(1)}"
            intent.chapter = m_dec.group(1).split(".")[0]
        elif intent.chapter and ("onushiloni" in clean_lower or "অনুশীলনী" in clean_lower or "exercise" in clean_lower):
            intent.exercise_label = f"অনুশীলনী {intent.chapter}"
        elif "onushiloni" in clean_lower or "অনুশীলনী" in clean_lower or "exercise" in clean_lower:
            intent.exercise_label = "অনুশীলনী"

    # 7. Question number detection (e.g. "3 no", "৩ নং", "no 5", "question 3", "৫ নম্বর")
    # First match "no 3", "question 3", "নং ৩", "নম্বর ৩"
    m_q = re.search(r"(?:no|নং|নম্বর|নাম্বার|number|question|প্রশ্ন)\s*[:.]?\s*([0-9]+)", clean_lower)
    if m_q:
        intent.question_no = int(m_q.group(1))
    else:
        # Match "3 no", "৩ নং", "৩ নম্বর" (ensure not part of a decimal like 1.1)
        m_q2 = re.search(r"(?<!\.)\b([0-9]+)\s*(?:no|নং|নম্বর|নাম্বার|number)", clean_lower)
        if m_q2:
            intent.question_no = int(m_q2.group(1))

    # 8. Subpart detection (e.g. "ক", "খ", "গ", "ঘ", "part a", "a")
    m_sub = re.search(r"\b([কখগঘabcd])\s*(?:নং|পার্ট|part)?\b", clean_lower)
    if m_sub and intent.question_no is not None:
        raw_sub = m_sub.group(1)
        # normalize a->ক, b->খ, c->গ, d->ঘ
        trans_sub = {"a": "ক", "b": "খ", "c": "গ", "d": "ঘ"}
        intent.subpart = trans_sub.get(raw_sub, raw_sub)

    return intent


def resolve_effective_scope(
    current_intent: ExtractedIntent,
    history_messages: list[dict[str, Any]] | None = None,
    student_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve effective academic scope using strict priority:

    1. Explicitly present in current message
    2. Derived from recent conversation turns
    3. Student profile defaults
    """
    profile = student_profile or {"class_level": 8, "medium": "bn"}

    # 1. Start with profile default
    effective_class = int(profile.get("class_level", 8))
    effective_subject = "math"
    effective_chapter = None
    effective_exercise = None
    effective_qno = None
    effective_subpart = None

    # 2. Inspect recent conversation history (last 3 user messages)
    if history_messages:
        for msg in reversed(history_messages[-4:]):
            if msg.get("role") == "user":
                hist_intent = parse_student_intent(msg.get("content", ""))
                if hist_intent.class_level:
                    effective_class = hist_intent.class_level
                if hist_intent.subject:
                    effective_subject = hist_intent.subject
                if hist_intent.chapter:
                    effective_chapter = hist_intent.chapter
                if hist_intent.exercise_label:
                    effective_exercise = hist_intent.exercise_label
                if hist_intent.question_no:
                    effective_qno = hist_intent.question_no
                if hist_intent.subpart:
                    effective_subpart = hist_intent.subpart

    # 3. Explicit current message ALWAYS overrides
    if current_intent.class_level is not None:
        effective_class = current_intent.class_level
    if current_intent.subject is not None:
        effective_subject = current_intent.subject
    if current_intent.chapter is not None:
        effective_chapter = current_intent.chapter
    if current_intent.exercise_label is not None:
        effective_exercise = current_intent.exercise_label
    if current_intent.question_no is not None:
        effective_qno = current_intent.question_no
    if current_intent.subpart is not None:
        effective_subpart = current_intent.subpart

    if effective_exercise == "অনুশীলনী" and effective_chapter:
        effective_exercise = f"অনুশীলনী {effective_chapter}"

    return {
        "class_level": effective_class,
        "subject": effective_subject,
        "chapter": effective_chapter,
        "exercise_label": effective_exercise,
        "question_no": effective_qno,
        "subpart": effective_subpart,
    }


async def rewrite_conversational_query(
    raw_query: str,
    history_messages: list[dict[str, Any]] | None = None,
    effective_scope: dict[str, Any] | None = None,
    db: Any | None = None,
) -> str:
    """Rewrites anaphoric or incomplete conversational follow-up queries into self-contained search queries.

    Resolves 'its the last chapter of math' dynamically from PostgreSQL `chapters` table.
    """
    import logging
    logger = logging.getLogger(__name__)

    q_clean = normalize_digits(raw_query).strip()
    q_lower = q_clean.lower()
    scope = effective_scope or {}

    # Case 0: Retry triggers ("Try again", "আবার চেষ্টা করো")
    retry_triggers = ["try again", "আবার চেষ্টা করো", "আবার চেষ্টা কর", "retry", "আবার বলো", "আবার বলো তো"]
    if q_lower in retry_triggers and history_messages:
        for msg in reversed(history_messages):
            if msg.get("role") == "user":
                prev_text = msg.get("content", "").strip()
                if prev_text.lower() not in retry_triggers:
                    logger.info("Rewrite retry query: '%s' -> '%s'", raw_query, prev_text)
                    return prev_text

    # Case 1: Ordinal follow-up ("and the second one?", "দ্বিতীয়টি?", "and question 2?")
    ord_match = re.search(r"\b(?:the\s+)?(second|third|fourth|fifth|2nd|3rd|4th|5th|দ্বিতীয়|তৃতীয়|চতুর্থ|পঞ্চম)\s*(?:one|question|no|টা|টি)?\b", q_lower)
    if ord_match:
        ord_word = ord_match.group(1)
        ord_map = {
            "second": 2, "2nd": 2, "দ্বিতীয়": 2,
            "third": 3, "3rd": 3, "তৃতীয়": 3,
            "fourth": 4, "4th": 4, "চতুর্থ": 4,
            "fifth": 5, "5th": 5, "পঞ্চম": 5,
        }
        target_qno = ord_map.get(ord_word, 2)
        rewritten = f"Class {scope.get('class_level', 8)} {scope.get('subject', 'math')} chapter {scope.get('chapter', 1)} exercise {scope.get('exercise_label', 'অনুশীলনী ১')} question {target_qno}"
        logger.info("Rewrite follow-up query: '%s' -> '%s'", raw_query, rewritten)
        return rewritten

    # Case 2: Last chapter reference ("its the last chapter of math", "গণিতের শেষ অধ্যায়")
    # Queries chapters table dynamically (ORDER BY number DESC LIMIT 1)
    if any(k in q_lower for k in ["last chapter", "শেষ অধ্যায়", "শেষ অধ্যায়", "শেষের অধ্যায়"]):
        cl = scope.get("class_level", 8)
        subj = scope.get("subject", "math")
        if db is not None:
            try:
                from sqlalchemy import text
                q_sql = text("""
                    SELECT c.number, c.title
                    FROM chapters c
                    JOIN books b ON c.book_id = b.id
                    WHERE b.class_level = :cl AND b.subject = :subj
                    ORDER BY c.number DESC
                    LIMIT 1
                """)
                res = await db.execute(q_sql, {"cl": cl, "subj": subj})
                row = res.first()
                if row:
                    rewritten = f"{subj} শ্রেণি {cl} অধ্যায় {row[0]} {row[1]}"
                    logger.info("Rewrite last chapter query dynamically from DB: '%s' -> '%s'", raw_query, rewritten)
                    return rewritten
            except Exception as ex:
                logger.warning("Error querying dynamic last chapter: %s", ex)

        rewritten = f"{subj} শ্রেণি {cl} শেষ অধ্যায়"
        logger.info("Rewrite last chapter query: '%s' -> '%s'", raw_query, rewritten)
        return rewritten

    # Case 3: Pronoun reference to formula / definition ("what is its formula?", "এর সূত্র কী?", "its formula")
    if re.search(r"\b(its|it's|তার|এর|এটার)\s+(formula|definition|rule|সূত্র|সংজ্ঞা|নিয়ম)\b", q_lower) or any(k in q_lower for k in ["এর সূত্র", "এটার সূত্র"]):
        ch = scope.get("chapter")
        subj = scope.get("subject", "math")
        rewritten = f"{subj} অধ্যায় {ch or ''} এর প্রয়োজনীয় সূত্রাবলী ও সংজ্ঞা"
        logger.info("Rewrite pronoun query: '%s' -> '%s'", raw_query, rewritten)
        return rewritten

    return raw_query
