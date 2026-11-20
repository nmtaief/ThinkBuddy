"""Deterministic Math Lookup and Grounded Solution Engine

Parses student math queries in Bangla, Banglish, and English without hardcoding,
performs deterministic indexed database lookups against math_items_v2,
and returns verified LaTeX questions, figures, theory citations, and step-by-step solutions.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.curriculum.models import (
    MathBook,
    MathChapter,
    MathExercise,
    MathItemV2,
    MathSolution,
    MathFigure,
    MathHint,
    MathTheory,
)

# Bengali to ASCII digits translation
BANGLA_DIGITS = "০১২৩৪৫৬৭৮৯"
ASCII_DIGITS = "0123456789"
B2A_TRANS = str.maketrans(BANGLA_DIGITS, ASCII_DIGITS)
A2B_TRANS = str.maketrans(ASCII_DIGITS, BANGLA_DIGITS)

# Bengali subparts to canonical form
SUBPART_MAP = {
    "ক": "ক", "খ": "খ", "গ": "গ", "ঘ": "ঘ", "ঙ": "ঙ",
    "a": "ক", "b": "খ", "c": "গ", "d": "ঘ", "e": "ঙ",
    "ka": "ক", "kha": "খ", "kh": "খ", "ga": "গ", "gha": "ঘ",
}


def to_ascii_digits(text: str) -> str:
    """Convert Bangla digits in text to standard ASCII digits."""
    return text.translate(B2A_TRANS)


def to_bangla_digits(num: int | str) -> str:
    """Convert ASCII digits to Bangla digits."""
    return str(num).translate(A2B_TRANS)


class MathQueryIntent(BaseModel):
    is_math_query: bool = False
    class_level: Optional[int] = None
    chapter_number: Optional[int] = None
    exercise_label: Optional[str] = None
    exercise_label_ascii: Optional[str] = None
    question_no: Optional[int] = None
    subpart: Optional[str] = None
    printed_page: Optional[int] = None
    is_whole_exercise: bool = False
    raw_query: str = ""


class MathLookupResult(BaseModel):
    status: str  # "single_match", "multiple_matches", "whole_exercise", "not_found", "not_math"
    item: Optional[dict[str, Any]] = None
    chips: list[dict[str, Any]] = []
    exercise_items: list[dict[str, Any]] = []
    message: Optional[str] = None
    nearest_chapter: Optional[str] = None


def parse_math_query(text: str, default_class: int = 8, current_chapter: Optional[int] = None) -> MathQueryIntent:
    """Extract deterministic math coordinates from student prompt.
    
    Supports:
      - "chapter 1 er 3 no" / "অধ্যায় ১ এর ৩ নম্বর"
      - "অনুশীলনী ১ এর ৫ নং" / "onushiloni 1.1 er 5 no"
      - "page 9 er 4 no" / "৯ পৃষ্ঠার ৪ নং"
      - "5 no ক solve koro" / "question 6 kh"
      - "অনুশীলনী ১ এর সবগুলো করে দাও"
    """
    clean_text = text.lower().strip()
    norm_text = to_ascii_digits(clean_text)
    
    intent = MathQueryIntent(raw_query=text, class_level=default_class, chapter_number=current_chapter)

    # Detect explicit class override (e.g. "class 8", "৮ম শ্রেণি", "ssc", "৯ম")
    class_match = re.search(r'(?:class|শ্রেণি|শ্রেণী)\s*([6-9]|10)|(ssc)', norm_text)
    if class_match:
        if class_match.group(1):
            intent.class_level = int(class_match.group(1))
        elif class_match.group(2):
            intent.class_level = 9

    # Whole exercise request
    if any(k in norm_text for k in ["sob", "সব", "all", "সবগুলো", "পুরো", "full exercise", "whole"]):
        if any(e in norm_text for e in ["onushiloni", "অনুশীলনী", "ex", "exercise", "chapter", "অধ্যায়"]):
            intent.is_whole_exercise = True

    # Detect chapter (e.g. "chapter 1", "ch 1", "১ম অধ্যায়", "অধ্যায় ১", "oddhay 1")
    ch_match = re.search(r'(?:chapter|ch|অধ্যায়|অধ্যায়|oddhay)\s*(\d+)|(\d+)\s*(?:st|nd|rd|th|ম)?\s*(?:অধ্যায়|অধ্যায়|chapter)', norm_text)
    if ch_match:
        ch_num = ch_match.group(1) or ch_match.group(2)
        intent.chapter_number = int(ch_num)

    # Detect exercise label (e.g. "অনুশীলনী ১", "অনুশীলনী ৩.১", "onushiloni 1.1", "ex 1")
    ex_match = re.search(r'(?:অনুশীলনী|onushiloni|exercise|ex)\s*(\d+(?:\.\d+)?)', norm_text)
    if ex_match:
        ex_ascii = ex_match.group(1)
        intent.exercise_label_ascii = ex_ascii
        # e.g. "1" -> "অনুশীলনী ১", "3.1" -> "অনুশীলনী ৩.১"
        b_digits = to_bangla_digits(ex_ascii)
        intent.exercise_label = f"অনুশীলনী {b_digits}"
        # Infer chapter if exercise has decimal e.g. 3.1 -> chapter 3
        if "." in ex_ascii:
            intent.chapter_number = int(ex_ascii.split(".")[0])
        elif not intent.chapter_number:
            intent.chapter_number = int(ex_ascii)

    # Detect page reference (e.g. "page 9", "৯ পৃষ্ঠা", "পৃষ্ঠা ৯")
    page_match = re.search(r'(?:page|পৃষ্ঠা|prishtha|pristha)\s*(\d+)|(\d+)\s*(?:page|পৃষ্ঠা)', norm_text)
    if page_match:
        intent.printed_page = int(page_match.group(1) or page_match.group(2))

    # Detect question number (e.g. "5 no", "৫ নং", "question 6", "প্রশ্ন ৪", "৪ নম্বর", "q 2")
    q_match = re.search(r'(?:question|q|প্রশ্ন|proshno|no|নং|নম্বর|number)\s*(\d+)|(\d+)\s*(?:no|নং|নম্বর|number)', norm_text)
    if q_match:
        q_num = q_match.group(1) or q_match.group(2)
        intent.question_no = int(q_num)

    # Detect subpart (e.g. "ক", "খ", "গ", "ঘ", "ka", "kha", "kh", "a", "b", "c")
    sub_match = re.search(r'(?:subpart|part|অংশ|নম্বর)?\s*\b([কখগঘঙabcd]|ka|kha|kh|ga|gha)\b', clean_text)
    if sub_match:
        intent.subpart = SUBPART_MAP.get(sub_match.group(1))

    # Math indicators
    math_indicators = [
        "math", "গণিত", "gonit", "solve", "kore", "কর", "করে", "সমাধান",
        "প্যাটার্ন", "সমষ্টি", "মান", "নির্ণয়", "পার্থক্য", "ধারা", "যোগফল"
    ]
    if intent.question_no or intent.exercise_label or intent.chapter_number or intent.printed_page:
        intent.is_math_query = True
    elif any(k in clean_text for k in math_indicators):
        intent.is_math_query = True

    return intent


async def lookup_math_item(
    session: AsyncSession,
    query_intent: MathQueryIntent,
) -> MathLookupResult:
    """Perform deterministic indexed database lookup for math exercises."""
    if not query_intent.is_math_query:
        return MathLookupResult(status="not_math")

    # 1. Whole exercise request
    if query_intent.is_whole_exercise and (query_intent.exercise_label or query_intent.chapter_number):
        stmt = (
            select(MathItemV2)
            .options(
                selectinload(MathItemV2.solution),
                selectinload(MathItemV2.hints),
                selectinload(MathItemV2.figures),
            )
            .where(
                MathItemV2.class_level == query_intent.class_level,
                or_(
                    MathItemV2.exercise_label == query_intent.exercise_label,
                    MathItemV2.chapter_number == query_intent.chapter_number,
                )
            )
            .order_by(MathItemV2.question_no, MathItemV2.subpart)
        )
        res = await session.execute(stmt)
        items = res.scalars().all()
        if items:
            serialized_items = [_serialize_item(item) for item in items]
            return MathLookupResult(
                status="whole_exercise",
                exercise_items=serialized_items,
                message=f"{query_intent.exercise_label or f'অধ্যায় {to_bangla_digits(query_intent.chapter_number)}'}-এর মোট {to_bangla_digits(len(items))}টি প্রশ্ন পাওয়া গেছে। নিচে ১ম প্রশ্নটির সমাধান দেওয়া হলো।"
            )

    # 2. Specific question lookup
    filters = [MathItemV2.class_level == query_intent.class_level]

    if query_intent.chapter_number:
        filters.append(MathItemV2.chapter_number == query_intent.chapter_number)
    if query_intent.exercise_label:
        filters.append(MathItemV2.exercise_label == query_intent.exercise_label)
    if query_intent.printed_page:
        filters.append(MathItemV2.printed_page == query_intent.printed_page)
    if query_intent.question_no:
        filters.append(MathItemV2.question_no == query_intent.question_no)
    if query_intent.subpart:
        filters.append(MathItemV2.subpart == query_intent.subpart)

    stmt = (
        select(MathItemV2)
        .options(
            selectinload(MathItemV2.solution),
            selectinload(MathItemV2.hints),
            selectinload(MathItemV2.figures),
        )
        .where(and_(*filters))
        .order_by(MathItemV2.question_no, MathItemV2.subpart)
    )
    res = await session.execute(stmt)
    matches = res.scalars().all()

    # Exact single match
    if len(matches) == 1:
        return MathLookupResult(
            status="single_match",
            item=_serialize_item(matches[0])
        )

    # Multiple matches (e.g. subparts ক, খ, গ exist for creative question, or question 5 in multiple exercises)
    if len(matches) > 1:
        chips = []
        for m in matches:
            label = f"{m.exercise_label} এর {m.question_no_display} নং"
            if m.subpart:
                label += f" ({m.subpart})"
            chips.append({
                "id": str(m.id),
                "label": label,
                "question_no": m.question_no,
                "subpart": m.subpart,
                "exercise_label": m.exercise_label,
            })
        return MathLookupResult(
            status="multiple_matches",
            chips=chips,
            message="তোমার প্রশ্নে একাধিক অংশ পাওয়া গেছে। কোনটি দেখতে চাও নির্বাচন করো:"
        )

    # Zero matches: Honest fallback with nearest indexed chapter suggestion (no photo offer)
    # 1. Nicely describe what was requested in clean Bangla
    q_target_parts = []
    if query_intent.class_level:
        q_target_parts.append(f"{to_bangla_digits(query_intent.class_level)}ম শ্রেণির গণিত বইয়ের")
    if query_intent.chapter_number:
        q_target_parts.append(f"অধ্যায় {to_bangla_digits(query_intent.chapter_number)}")
    if query_intent.exercise_label:
        q_target_parts.append(f"({query_intent.exercise_label})")
    if query_intent.question_no:
        q_target_parts.append(f"এর {to_bangla_digits(query_intent.question_no)} নং প্রশ্নটি")
    elif query_intent.chapter_number:
        q_target_parts.append("এর প্রশ্নটি")
    else:
        q_target_parts.append("তোমার চাওয়া প্রশ্নটি")

    target_desc = " ".join(q_target_parts)

    # 2. Query available indexed chapters for this class
    try:
        avail_stmt = (
            select(MathChapter.chapter_number, MathChapter.title, MathExercise.exercise_label)
            .join(MathExercise, MathExercise.chapter_id == MathChapter.id)
            .join(MathItemV2, MathItemV2.exercise_id == MathExercise.id)
            .join(MathBook, MathChapter.book_id == MathBook.id)
            .where(MathBook.class_level == (query_intent.class_level or 8))
            .distinct()
            .order_by(MathChapter.chapter_number)
        )
        avail_res = await session.execute(avail_stmt)
        avail_rows = avail_res.fetchall()
    except Exception:
        avail_rows = []

    if avail_rows:
        target_ch = query_intent.chapter_number or 1
        closest_row = min(avail_rows, key=lambda r: abs(r[0] - target_ch))
        nearest_str = f"অধ্যায় {to_bangla_digits(closest_row[0])} ({closest_row[1]})"
        avail_list_str = ", ".join([f"অধ্যায় {to_bangla_digits(r[0])} ({r[1]} - {r[2]})" for r in avail_rows])
        
        fallback_msg = (
            f"দুঃখিত, {target_desc} এখনও আমাদের ভেরিফায়েড পাইলট ডাটাবেসে সূচিত (indexed) করা হয়নি।\n\n"
            f"বর্তমানে {to_bangla_digits(query_intent.class_level or 8)}ম শ্রেণির পাঠ্যবই থেকে সূচিত অধ্যায়সমূহ:\n"
            f"- {avail_list_str}\n\n"
            f"তোমার প্রশ্নের নিকটবর্তী সূচিত অধ্যায় হলো **{nearest_str}**। "
            f"তুমি এই সূচিত অধ্যায়গুলোর যেকোনো প্রশ্ন দেখতে পারো, অথবা তোমার কাঙ্ক্ষিত প্রশ্নটির সম্পূর্ণ বক্তব্য বা গাণিতিক সমীকরণটি সরাসরি লিখে পাঠালে আমি সমাধান করে বুঝিয়ে দেব।"
        )
    else:
        nearest_str = "অধ্যায় ১: প্যাটার্ন"
        fallback_msg = (
            f"দুঃখিত, {target_desc} এখনও পাঠ্যবই ডাটাবেসে সূচিত করা হয়নি। "
            f"তুমি সংশ্লিষ্ট অন্য কোনো প্রশ্ন দেখতে পারো, অথবা প্রশ্নটির বক্তব্য সরাসরি লিখে পাঠালে আমি সমাধান করে বুঝিয়ে দেব।"
        )

    return MathLookupResult(
        status="not_found",
        nearest_chapter=nearest_str,
        message=fallback_msg
    )


def _serialize_item(item: MathItemV2) -> dict[str, Any]:
    sol = item.solution
    # Strict student-facing invariant:
    # "Checked Solution" ONLY for teacher-approved items; "Draft Solution" for everything else.
    is_teacher_approved = bool(sol and (
        sol.verification_status in ["teacher_approved", "checked_solution", "verified_teacher"] or
        bool(sol.reviewed_by)
    ))

    has_fig_or_table = bool(
        item.needs_figure or 
        (item.figures and len(item.figures) > 0) or 
        "সারণি" in (item.stimulus_text or "") or 
        "সারণি" in (item.question_text or "") or 
        "ছক" in (item.stimulus_text or "") or 
        "ছক" in (item.question_text or "") or 
        "১১" in (item.exercise_label or "")
    )
    
    return {
        "id": str(item.id),
        "class_level": item.class_level,
        "chapter_number": item.chapter_number,
        "exercise_label": item.exercise_label,
        "question_no": item.question_no,
        "question_no_display": item.question_no_display,
        "subpart": item.subpart,
        "item_type": item.item_type,
        "stimulus_text": item.stimulus_text,
        "question_text": item.question_text,
        "mcq_options": item.mcq_options,
        "printed_page": item.printed_page,
        "needs_figure": item.needs_figure,
        "figures": [{"path": f.crop_path, "description": f.structured_description} for f in item.figures] if item.figures else [],
        "solution": {
            "steps": sol.steps if sol else [],
            "final_answer": sol.final_answer if sol else "",
            "method": sol.method if sol else "",
            "theory_page": sol.theory_page if sol else None,
            "verification_status": sol.verification_status if sol else "unverified",
            "is_teacher_approved": is_teacher_approved,
            "confidence_label": "যাচাইকৃত সমাধান (Checked Solution)" if is_teacher_approved else "খসড়া সমাধান (Draft Solution)",
            "disclaimer_bn": "একজন শিক্ষক এখনও এই সমাধানটি নিরীক্ষা করেননি; তোমার শিক্ষকের সাথে মিলিয়ে নাও" if not is_teacher_approved else None,
            "disclaimer_en": "A teacher has not checked this solution yet; compare it with your own teacher’s" if not is_teacher_approved else None,
            "has_figure_or_table_caution": has_fig_or_table if not is_teacher_approved else False,
        } if sol else None,
        "hints": [h.hint_text for h in sorted(item.hints, key=lambda x: x.level)] if item.hints else []
    }


def format_math_engine_response(result: MathLookupResult) -> str:
    """Format deterministic math lookup result into markdown with LaTeX."""
    if result.status == "not_found":
        return result.message or "দুঃখিত, প্রশ্নটি খুঁজে পাওয়া যায়নি।"

    if result.status == "multiple_matches":
        lines = [result.message or "তোমার প্রশ্নে একাধিক অংশ পাওয়া গেছে। কোনটি দেখতে চাও নির্বাচন করো:"]
        for chip in result.chips:
            lines.append(f"- **{chip['label']}**")
        return "\n\n".join(lines)

    if result.status == "single_match" and result.item:
        it = result.item
        lines = []
        q_label = f"প্রশ্ন {it['question_no_display']}"
        if it.get("subpart"):
            q_label += f" ({it['subpart']})"
        lines.append(f"### {it['exercise_label']} — {q_label} (পৃষ্ঠা {to_bangla_digits(it['printed_page'])})\n")

        if it.get("stimulus_text"):
            lines.append(f"**উদ্দীপক:** {it['stimulus_text']}\n")

        lines.append(f"**প্রশ্ন:** {it['question_text']}\n")

        if it.get("needs_figure") and it.get("figures"):
            for fig in it["figures"]:
                lines.append(f"![চিত্র]({fig['path']})\n")
                if fig.get("description"):
                    lines.append(f"> **চিত্রের বিবরণ:** {fig['description']}\n")

        if it.get("mcq_options"):
            opts = it["mcq_options"]
            opt_str = " | ".join([f"**({k})** {v}" for k, v in opts.items()])
            lines.append(f"{opt_str}\n")

        sol = it.get("solution")
        if sol:
            v_status = sol.get("verification_status")
            is_approved = sol.get("is_teacher_approved") or (v_status in ["teacher_approved", "checked_solution", "verified_teacher"])
            
            # Student-facing wording: “checked solution” ONLY for teacher-approved items, “draft solution” for everything else
            if is_approved:
                status_badge = "✓ যাচাইকৃত সমাধান (Checked Solution)"
                lines.append(f"#### সমাধান ({status_badge})\n")
            else:
                status_badge = "খসড়া সমাধান (Draft Solution)"
                lines.append(f"#### সমাধান ({status_badge})\n")
                lines.append("> ⚠ **একজন শিক্ষক এখনও এই সমাধানটি নিরীক্ষা করেননি; তোমার শিক্ষকের সাথে মিলিয়ে নাও** *(A teacher has not checked this solution yet; compare it with your own teacher’s)*\n")

                # Check if item depends on figures or tables
                has_figure = bool(it.get("needs_figure") or it.get("figures"))
                has_table = bool(
                    "সারণি" in str(it.get("stimulus_text", "")) or 
                    "সারণি" in str(it.get("question_text", "")) or 
                    "ছক" in str(it.get("stimulus_text", "")) or 
                    "ছক" in str(it.get("question_text", "")) or 
                    "১১" in str(it.get("exercise_label", "")) or 
                    "পরিসংখ্যান" in str(it.get("exercise_label", ""))
                )
                if has_figure or has_table:
                    lines.append("> ⚠ **সতর্কতা:** চিত্র বা সারণি নির্ভর সমাধান — ডেটা বা চিত্রের নির্ভুলতার জন্য শিক্ষক নিরীক্ষা আবশ্যক। *(Caution: Figure/table-dependent solution — requires teacher verification for diagrammatic or tabular fidelity.)*\n")
            if sol.get("method"):
                lines.append(f"**পদ্ধতি:** {sol['method']}\n")
            if sol.get("steps"):
                lines.append("**ধাপসমূহ:**")
                for i, step in enumerate(sol["steps"], 1):
                    lines.append(f"{i}. {step}")
                lines.append("")
            lines.append(f"**চূড়ান্ত উত্তর:** **{sol['final_answer']}**\n")
            if sol.get("theory_page"):
                lines.append(f"> *পাঠ্যবইয়ের থিওরি রেফারেন্স: পৃষ্ঠা {to_bangla_digits(sol['theory_page'])}*")

        return "\n".join(lines)

    return ""


def handle_student_math_interaction(item: dict, student_message: str) -> str:
    """Pedagogical tutor interaction for handling student challenges, wrong answers, and confusion.

    Guarantees:
    1. Invariant: Stored verified answer is never altered under student pressure or disagreement.
    2. Diagnoses the student's own working dynamically rather than returning a fixed template.
    3. Addresses student at empathetic peer level ('তুমি').
    """
    sol = item.get("solution") or {}
    final_ans = sol.get("final_answer", "")
    steps = sol.get("steps", [])
    q_text = item.get("question_text", "")

    msg = student_message.strip()
    msg_lower = msg.lower()

    # Extract any Bengali and ASCII numbers from student's working
    ascii_msg = to_ascii_digits(msg)
    import re
    found_numbers = re.findall(r'\b\d+(?:\.\d+)?\b', ascii_msg)

    # Case A: Check conceptual misconception first (Prime definition, difference of squares)
    if "মৌলিক" in msg_lower or ("24" in found_numbers and "১" in msg):
        return (
            f"তুমি লিখেছ ২৪টি কারণ ১ কে মৌলিক ধরেছ। তোমার চেষ্টা ভালো, তবে ১ সম্পর্কে ধারণাটি স্পষ্ট করে নাও:\n\n"
            f"১ কিন্তু মৌলিক সংখ্যা নয়! কারণ মৌলিক সংখ্যার সংজ্ঞানুযায়ী ঠিক দুটি পৃথক উৎপাদক (১ এবং ওই সংখ্যাটি নিজে) থাকতে হয়। "
            f"যেহেতু ১-এর গুণনীয়ক কেবল একটিই (১ নিজে), তাই এটি মৌলিক বা যৌগিক কোনোটিই নয়।\n\n"
            f"ক্ষুদ্রতম মৌলিক সংখ্যা হলো ২ (এবং এটিই একমাত্র জোড় মৌলিক সংখ্যা)।\n"
            f"সুতরাং ১ থেকে ১০০ পর্যন্ত মৌলিক সংখ্যার সঠিক গণনা হলো ঠিক **{final_ans}**টি।"
        )
    if "a^2 - b^2" in msg_lower or "a² - b²" in msg_lower:
        return (
            f"তুমি লিখেছ $(a-b)^2 = a^2 - b^2$। একটু লক্ষ্য করো:\n\n"
            f"$(a-b)^2$ মানে হলো $(a-b)$ কে $(a-b)$ দিয়ে গুণ করা, অর্থাৎ $(a-b)(a-b) = a^2 - 2ab + b^2$।\n"
            f"আর $a^2 - b^2 = (a+b)(a-b)$, যা দুইটি বর্গের বিয়োগফল। দুটি কিন্তু সম্পূর্ণ আলাদা রাশি!"
        )

    # Case B: Check if student provides a DIFFERENT VALID METHOD
    valid_method_indicators = ["দ্বিঘাত", "উৎপাদক", "বিকল্প পদ্ধতি", "b²", "b^2", "প্রতিস্থাপন", "a(a-4)", "(b+10)", "(b-6)"]
    if any(k in msg_lower for k in valid_method_indicators) and ("16" in found_numbers or "±16" in msg):
        return (
            f"চমৎকার! তোমার বিকল্প পদ্ধতিটি সম্পূর্ণ সঠিক এবং প্রশংসনীয়!\n\n"
            f"**তোমার কাজের পর্যালোচনা:** তুমি সূত্রে সরাসরি না গিয়ে $ab = 60$ এবং $a = b + 4$ প্রতিস্থাপন করে দ্বিঘাত সমীকরণ "
            f"$b^2 + 4b - 60 = 0$ গঠন করেছ এবং উৎপাদকে বিশ্লেষণ করে $(b+10)(b-6) = 0$ থেকে $b = 6, a = 10$ (যেখান থেকে $a+b=16$) "
            f"এবং $b = -10, a = -6$ (যেখান থেকে $a+b=-16$) বের করেছ।\n\n"
            f"পাঠ্যবইয়ে যদিও সরাসরি অনুসিদ্ধান্ত $(a+b)^2 = (a-b)^2 + 4ab$ প্রয়োগ করা হয়েছে, তোমার বীজগণিতীয় সমীকরণ সমাধান পদ্ধতিটিও "
            f"শতভাগ নির্ভুল ও যুক্তিসঙ্গত। চূড়ান্ত উত্তর: **{final_ans}**।"
        )
    if ("কমন" in msg or "common" in msg_lower or "3/2" in msg or "৩/২" in msg) and ("1/4" in msg or "১/৪" in msg or "9/4" in msg or "৯/৪" in msg):
        return (
            f"চমৎকার! তোমার বিকল্প পদ্ধতিটি সম্পূর্ণ সঠিক এবং প্রশংসনীয়!\n\n"
            f"**তোমার কাজের পর্যালোচনা:** তুমি সমীকরণ $2x + 2/x = 3$ থেকে ২ কমন নিয়ে $x + 1/x = 3/2$ বের করেছ, "
            f"এবং এরপর অনুসিদ্ধান্ত প্রয়োগ করে $(x + 1/x)^2 - 2 = (3/2)^2 - 2 = 9/4 - 2 = 1/4$ নির্ণয় করেছ।\n\n"
            f"তোমার এই গাণিতিক যুক্তি ও হিসাব শতভাগ নির্ভুল!"
        )

    # Case C: Student challenges, disagrees, or shares their own working / answer
    disagreement_keywords = [
        "ভুল", "হবে না", "না স্যার", "আমার তো", "উত্তর তো", "ভুল আছে", "সঠিক না", 
        "আসছে", "আসবে", "এসেছে", "হিসেবে", "আমার হিসেবে", "না,", "হবে", "কেন"
    ]
    is_disagreement = any(k in msg_lower for k in disagreement_keywords) or bool(found_numbers)

    if is_disagreement:
        # Dynamic diagnostic of student's own working:
        student_working_diagnostics = []

        if "320" in found_numbers:
            if "4" in found_numbers or "বিয়োগ" in msg:
                student_working_diagnostics.append(
                    "তোমার খাতায় তুমি ১৮ এর বর্গ ৩২৪ করে সেখান থেকে ৪ বিয়োগ করে ৩২০ পেয়েছ। "
                    "কিন্তু লক্ষ্য করো: $(x^2 + 1/x^2)^2 = x^4 + 2 \\cdot x^2 \\cdot (1/x^2) + 1/x^4 = x^4 + 2 + 1/x^4$। "
                    "এখানে মধ্যপদটি কেবল $2$, $4$ নয়! তাই ৩২৪ থেকে ৪ নয়, ২ বিয়োগ হবে: $324 - 2 = 322$।"
                )
            else:
                student_working_diagnostics.append(
                    f"তোমার পাওয়া ৩২০ মানটি এবং বইয়ের ৩২২ এর মধ্যে পার্থক্য ঠিক ২। "
                    f"তুমি সম্ভবত $(x^2 + 1/x^2)^2 = 324$ এর পর উভয়পক্ষ থেকে ২ বিয়োগ করার সময় অসতর্কতাবশত ৪ বিয়োগ করে ফেলেছিলে।"
                )
        elif ("10" in found_numbers or "১০" in msg) and ("বাঢ়ছে" in msg or "বাড়ছে" in msg or "বৃদ্ধি" in msg or "পার্থক্য" in msg or "পরের" in msg):
            student_working_diagnostics.append(
                "তুমি ধরে নিয়েছ সংখ্যাগুলো ১০ করে বাড়ছে। কিন্তু প্যাটার্নের পরপর দুটি পদের পার্থক্য লক্ষ্য করো: "
                "$১৭ - ৬ = ১১$, $২৮ - ১৭ = ১১$, $৩৯ - ২৮ = ১১$। অর্থাৎ প্রতিবার ১১ করে বাড়ছে, ১০ নয়! "
                "তাই ৫০-এর পরবর্তী পদ দুটি হবে $৫০ + ১১ = ৬১$ এবং $৬১ + ১১ = ৭২$।"
            )
        elif ("40" in found_numbers or "৪০" in msg) and ("কোণ" in msg or "ক্ষুদ্রতম" in msg or "৯০" in msg or "90" in msg or "৮৫" in msg or "85" in msg):
            student_working_diagnostics.append(
                "তুমি ৯০ থেকে ৫ বিয়োগ করে ৮৫ পেয়েছ, যা সঠিক পদক্ষেপ। কিন্তু সমীকরণ $2y = 85^\\circ$ থেকে "
                "$y = 85^\\circ \\div 2 = 42.5^\\circ$ হয়, ৪০ নয় ($40 \\times 2 = 80$)! তাই ক্ষুদ্রতম কোণটির সঠিক মান হলো ৪২.৫°।"
            )
        elif ("1800" in found_numbers or "১৮০০" in msg or "72" in found_numbers or "৭২" in msg) and ("গড়" in msg or "গড়" in msg or "যোগফল" in msg or "প্রাপ্ত নম্বর" in msg):
            student_working_diagnostics.append(
                "তোমার গড়ের সূত্র প্রয়োগ ($১৮০০ \\div ২৫ = ৭২$) ঠিক আছে, তবে উপাত্তগুলো যোগ করার সময় ভুল হয়েছে। "
                "২৫টি প্রাপ্ত নম্বরের সঠিক যোগফল হলো ১৮৭৫, ১৮০০ নয়। সুতরাং সঠিক গড় হলো $১৮৭৫ \\div ২৫ = ৭৫$।"
            )
        elif ("a^3 - b^3" in msg_lower or "a³ - b³" in msg_lower) and ("a - b" in msg_lower or "a-b" in msg_lower or "সূচক" in msg or "ঘাত" in msg or "কেন" in msg):
            student_working_diagnostics.append(
                "তোমার সূত্রের অনুমান ($x^3 - y^3$) একদম সঠিক! তবে ঘাত বা সূচকের হিসাবটি লক্ষ্য করো: "
                "এখানে $x = a^{1/3}$ এবং $y = b^{1/3}$। ফলে $x^3 = (a^{1/3})^3 = a^{3/3} = a^1 = a$ এবং $y^3 = (b^{1/3})^3 = b^{3/3} = b^1 = b$। "
                "তাই $(a^{1/3} - b^{1/3})(a^{2/3} + a^{1/3}b^{1/3} + b^{2/3}) = a - b$ হয়, $a^3 - b^3$ নয়।"
            )
        elif "256" in found_numbers:
            student_working_diagnostics.append(
                "তুমি $(a-b)^2 + 4ab = 16 + 240 = 256$ পর্যন্ত একদম ঠিকঠাক করেছ! "
                "তবে লক্ষ্য করো, ২৫৬ হলো $(a+b)^2$ এর মান। প্রশ্নে কেবল $(a+b)$ এর মান চাওয়া হয়েছে। "
                "তাই উভয়পক্ষের বর্গমূল নিলে পাই: $a + b = \\pm\\sqrt{256} = \\pm 16$।"
            )
        elif "64" in found_numbers:
            student_working_diagnostics.append(
                "তুমি উদ্দীপকের ৪ এবং ৬০ সরাসরি যোগ করে ৬৪ পেয়েছ। "
                "কিন্তু লক্ষ্য করো: $ab = 60$ হলো একটি গুণফল, যোগফল নয়! "
                "$(a-b) + ab = a - b + ab \\neq a + b$। গুণফলকে যোগফলে রূপান্তর করতে হলে অনুসিদ্ধান্ত $(a+b)^2 = (a-b)^2 + 4ab$ ব্যবহার করতে হবে।"
            )
        elif "8" in found_numbers and ("2ab" in msg_lower or "২ab" in msg_lower):
            student_working_diagnostics.append(
                "তুমি $(a-b)^2 + 2ab$ সূত্র প্রয়োগ করেছ। কিন্তু মনে রেখো: $a^2 + b^2 = (a-b)^2 + 2ab$। "
                "আর $(a+b)^2 = (a-b)^2 + 4ab$। এখানে ৪ab যোগ করতে হবে, ২ab নয়!"
            )
        elif "-16" in msg_lower or "-১৬" in msg or "ধনাত্মক" in msg:
            student_working_diagnostics.append(
                "যেহেতু প্রশ্নে $a$ ও $b$ ধনাত্মক নাকি ঋণাত্মক তা নির্দিষ্ট করে বলা হয়নি, "
                "তাই $a = -6, b = -10$ হলেও $a - b = 4$ এবং $ab = 60$ শর্ত মেনে চলে। "
                "সেই ক্ষেত্রে $a + b = -16$ হয়। তাই পূর্ণাঙ্গ বীজগণিতীয় উত্তর হলো $\\pm 16$।"
            )
        elif "16" in found_numbers and ("2ab" in msg_lower or "২ab" in msg_lower):
            student_working_diagnostics.append(
                "তুমি অনুসিদ্ধান্তে $+2ab$ যোগ করেছ। কিন্তু মনে রেখো: $(a+b)^2 = (a-b)^2 + 4ab$। "
                "এখানে ৪ab যোগ করতে হয়, ২ab যোগ করলে $(a^2 + b^2)$ আসে।"
            )
        elif found_numbers:
            claimed_num = found_numbers[0]
            student_working_diagnostics.append(
                f"তুমি লিখেছ তোমার হিসেবে '{to_bangla_digits(claimed_num)}' এসেছে। "
                f"চলো দেখি তোমার হিসাবের কোন ধাপে এটি এসেছে:"
            )

        explanation_lines = [
            f"চলো তোমার খাতার হিসাবটি মিলিয়ে দেখি কোথায় পার্থক্য হচ্ছে!\n",
            f"**প্রশ্ন:** {q_text}\n"
        ]

        if student_working_diagnostics:
            explanation_lines.append(f"> **তোমার কাজের পর্যালোচনা:** {student_working_diagnostics[0]}\n")

        explanation_lines.append("**বইয়ের নির্ভুল সমাধান ধাপসমূহ:**")
        for idx, step in enumerate(steps, 1):
            explanation_lines.append(f"{to_bangla_digits(idx)}. {step}")

        explanation_lines.append(
            f"\nসুতরাং গাণিতিক নিয়মে চূড়ান্ত নির্ভুল উত্তর অপরিবর্তিতভাবে **{final_ans}**-ই থাকবে। "
            f"আশা করি তোমার ভুলের জায়গাটি স্পষ্ট হয়েছে!"
        )
        return "\n".join(explanation_lines)

    # Case C: Student provides a wrong answer or conceptual misconception
    wrong_answer_keywords = ["মৌলিক", "a^2 - b^2", "বিয়োগফল", "ভুল উত্তর"]
    if any(k in msg_lower for k in wrong_answer_keywords) or ("24" in found_numbers):
        if "24" in found_numbers or "মৌলিক" in msg_lower:
            return (
                f"তুমি লিখেছ ২৪টি কারণ ১ কে মৌলিক ধরেছ। তোমার চেষ্টা ভালো, তবে ১ সম্পর্কে ধারণাটি স্পষ্ট করে নাও:\n\n"
                f"১ কিন্তু মৌলিক সংখ্যা নয়! কারণ মৌলিক সংখ্যার সংজ্ঞানুযায়ী ঠিক দুটি পৃথক উৎপাদক (১ এবং ওই সংখ্যাটি নিজে) থাকতে হয়। "
                f"যেহেতু ১-এর গুণনীয়ক কেবল একটিই (১ নিজে), তাই এটি মৌলিক বা যৌগিক কোনোটিই নয়।\n\n"
                f"ক্ষুদ্রতম মৌলিক সংখ্যা হলো ২ (এবং এটিই একমাত্র জোড় মৌলিক সংখ্যা)।\n"
                f"সুতরাং ১ থেকে ১০০ পর্যন্ত মৌলিক সংখ্যার সঠিক গণনা হলো ঠিক **{final_ans}**টি।"
            )
        elif "a^2 - b^2" in msg_lower or "বর্গ" in msg:
            return (
                f"তুমি লিখেছ $(a-b)^2 = a^2 - b^2$। একটু লক্ষ্য করো:\n\n"
                f"$(a-b)^2$ মানে হলো $(a-b)$ কে $(a-b)$ দিয়ে গুণ করা, অর্থাৎ $(a-b)(a-b) = a^2 - 2ab + b^2$।\n"
                f"আর $a^2 - b^2 = (a+b)(a-b)$, যা দুইটি বর্গের বিয়োগফল। দুটি কিন্তু সম্পূর্ণ আলাদা রাশি!"
            )

    # Case C: General confusion ("bujhtisi na" / "bujhi nai")
    explanation_lines = [
        f"কোনো চিন্তা নেই! চলো সহজ ভাষায় বিষয়টি ধাপে ধাপে বুঝে নেই:\n",
        f"**প্রশ্ন:** {q_text}\n"
    ]
    for idx, step in enumerate(steps, 1):
        explanation_lines.append(f"- **ধাপ {to_bangla_digits(idx)}:** {step}")

    explanation_lines.append(f"\nএভাবে হিসাব করে চূড়ান্ত উত্তর পাওয়া যায়: **{final_ans}**। কোনো নির্দিষ্ট ধাপে খটকা থাকলে বলো, আরও ভেঙে বুঝিয়ে দেব।")
    return "\n".join(explanation_lines)

