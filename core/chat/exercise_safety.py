"""Safety gate for exercise retrieval.
Until exercise precision is >= 95%, get_exercise_question must never return
one confident question when the exercise label is ambiguous or unverified.
If several sub-sections match (e.g. অনুশীলনী ২.১ and ২.২), return all candidates
so the model asks which one.
"""

from typing import Any
import re

def resolve_exercise_candidates(
    matched_exercises: list[dict[str, Any]],
    requested_label: str | None,
    requested_qno: int | str,
) -> dict[str, Any]:
    """Inspect matched exercises and determine if single question or disambiguation is needed.
    
    Returns:
        {
            "status": "exact" | "ambiguous" | "not_found",
            "question": dict | None,
            "candidates": list[dict],
            "message": str
        }
    """
    if not matched_exercises:
        return {
            "status": "not_found",
            "question": None,
            "candidates": [],
            "message": f"অনুশীলনীতে {requested_qno} নম্বর প্রশ্নটি পাওয়া যায়নি।"
        }

    # Filter candidates if requested_label specifies "অনুশীলনী" or "নমুনা"
    if requested_label:
        norm_req = requested_label.strip().lower()
        if any(w in norm_req for w in ["অনুশীলনী", "onushiloni", "exercise", "ex"]):
            onushiloni_items = [e for e in matched_exercises if "অনুশীলনী" in (e.get("exercise_label") or "")]
            if onushiloni_items:
                matched_exercises = onushiloni_items
        elif "নমুনা" in norm_req or "sample" in norm_req:
            nomuna_items = [e for e in matched_exercises if "নমুনা" in (e.get("exercise_label") or "")]
            if nomuna_items:
                matched_exercises = nomuna_items
    else:
        # If user didn't specify, prefer actual 'অনুশীলনী' over 'নমুনা প্রশ্ন' (sample questions)
        onushiloni_items = [e for e in matched_exercises if "অনুশীলনী" in (e.get("exercise_label") or "")]
        if onushiloni_items:
            matched_exercises = onushiloni_items

    # Group by distinct exercise_label (e.g. 'অনুশীলনী ২.১', 'অনুশীলনী ২.২')
    distinct_labels = sorted(list(set(e.get("exercise_label") for e in matched_exercises if e.get("exercise_label"))))

    # If the user specified a decimal in the query (e.g. '2.1', '২.১', '9.1')
    has_decimal = False
    if requested_label:
        has_decimal = bool(re.search(r'\d+\.\d+|[১-৯]+\.[১-৯]+', requested_label))

    if len(distinct_labels) > 1 and not has_decimal:
        return {
            "status": "ambiguous",
            "question": None,
            "candidates": matched_exercises,
            "distinct_labels": distinct_labels,
            "message": (
                f"এই অধ্যায়ে একাধিক অনুশীলনী রয়েছে ({', '.join(distinct_labels)})। "
                f"তুমি কোন অনুশীলনীর {requested_qno} নম্বর প্রশ্নটির সমাধান জানতে চাচ্ছ?"
            )
        }

    # If a specific label was provided or only 1 distinct label matched
    return {
        "status": "exact",
        "question": matched_exercises[0],
        "candidates": matched_exercises,
        "message": "প্রশ্নটি পাওয়া গেছে।"
    }

