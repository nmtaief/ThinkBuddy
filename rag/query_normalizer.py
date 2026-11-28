"""Deterministic Banglish, Bangla Variant, and Unicode Query Normalizer."""

from __future__ import annotations

import re
import unicodedata

# Common Banglish-to-Bangla/English NCTB curriculum aliases
BANGLISH_ALIASES: dict[str, str] = {
    "kosh bivajon": "কোষ বিভাজন Cell Division",
    "kosh bibhajon": "কোষ বিভাজন Cell Division",
    "alor protifolon": "আলোর প্রতিফলন Reflection of Light",
    "alor protisaron": "আলোর প্রতিসরণ Refraction of Light",
    "alo": "আলো Light",
    "munafa": "মুনাফা Profit",
    "chokrobriddhi munafa": "চক্রবৃদ্ধি মুনাফা Compound Profit",
    "britto": "বৃত্ত Circle",
    "porimap": "পরিমাপ Measurement",
    "porimiti": "পরিমিতি Mensuration",
    "porisongkhan": "পরিসংখ্যান Statistics",
    "pithagoras": "পিথাগোরাসের উপপাদ্য Pythagoras Theorem",
    "pythagoras": "পিথাগোরাসের উপপাদ্য Pythagoras Theorem",
    "set o function": "সেট ও ফাংশন Set and Function",
    "rasayanik bikriya": "রাসায়নিক বিক্রিয়া Chemical Reaction",
    "paddartho": "পদার্থ Matter",
    "shokti": "শক্তি Energy",
    "tothyo o upatto": "তথ্য ও উপাত্ত Information and Data",
    "somikoron": "সমীকরণ Equation",
    "trikonomiti": "ত্রিকোণমিতি Trigonometry",
    "trigonmiti": "ত্রিকোণমিতি Trigonometry",
    "choturvuj": "চতুর্ভুজ Quadrilaterals",
    "trivuj": "ত্রিভুজ Triangle",
    "bastob songkha": "বাস্তব সংখ্যা Real Numbers",
    "mulod songkha": "মূলদ ও অমূলদ সংখ্যা Rational and Irrational Numbers",
    "suchok o logarithm": "সূচক ও লগারিদম Exponents and Logarithms",
    "pattern": "প্যাটার্ন Pattern",
    "vector": "ভেক্টর Vector",
    "water": "পানি জলবায়ু পরিবেশ Water",
}

_BANGLA_VARIANT_MAP = str.maketrans(
    {
        "\u0988": "ই",  # ঈ -> ই
        "\u098a": "উ",  # ঊ -> উ
        "\u09c0": "ি",  # ী -> ি
        "\u09c2": "ু",  # ূ -> ু
        "\u09b6": "স",  # শ -> স
        "\u09b7": "স",  # ষ -> স
        "\u09df": "য",  # য় -> য
        "\u09dc": "র",  # ড় -> র
        "\u09dd": "র",  # ঢ় -> র
        "\u09a3": "ন",  # ণ -> ন
        "\u0982": "ঙ",  # ং -> ঙ
    }
)


def normalize_bangla_variants(text: str) -> str:
    """Apply Unicode NFC normalization and collapse common Bangla spelling variants."""
    if not text:
        return ""
    nfc = unicodedata.normalize("NFC", text).strip()
    # Strip chandrabindu/nukta drift and normalize phonetic variants
    no_nukta = nfc.replace("\u09bc", "").replace("\u0981", "")
    return no_nukta.translate(_BANGLA_VARIANT_MAP)


def normalize_query(query: str) -> str:
    """Normalize a student query (Bangla, English, or Banglish) for retrieval & caching."""
    if not query:
        return ""
    nfc = unicodedata.normalize("NFC", query).strip()
    lower = nfc.lower()
    expanded_parts: list[str] = [nfc]

    for banglish, canonical in BANGLISH_ALIASES.items():
        if re.search(rf"\b{re.escape(banglish)}\b", lower):
            expanded_parts.append(canonical)

    return " ".join(dict.fromkeys(expanded_parts))
