"""Bengali morphological normalizer, suffix stripper, and tsquery builder.

Solves the core lexical limitation where PostgreSQL simple tsquery misses inflected Bengali words
(e.g., সালোকসংশ্লেষণের vs সালোকসংশ্লেষণ, মুনাফার vs মুনাফা, কোষের vs কোষ)
while protecting false-friend root words (মাটি, সূত্র, ক্ষেত্র, বৃষ্টি, দৃষ্টি, ইত্যাদি)
using pure orthographic and phonotactic constraints without hard-coded word dictionaries.
"""

from __future__ import annotations

import re
import unicodedata

# Mapping of Bengali numerals to ASCII digits
BN_DIGITS = {
    "০": "0",
    "১": "1",
    "২": "2",
    "৩": "3",
    "৪": "4",
    "৫": "5",
    "৬": "6",
    "৭": "7",
    "৮": "8",
    "৯": "9",
}
ASCII_TO_BN_DIGITS = {v: k for k, v in BN_DIGITS.items()}

# Primary Bengali consonants
BN_CONSONANTS = set("কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহড়ঢ়য়ৎ")
# Bengali vowel diacritics (kar)
VOWEL_KARS = set("ািীুূৃেৈোৌ")
# Bengali independent vowels
INDEPENDENT_VOWELS = set("অআইঈউঊঋএঐওঔ")

# Common Bengali noun and case suffixes ordered by length (longest match first)
BENGALI_SUFFIXES = [
    # Plural + genitive / locative
    "গুলোর",
    "গুলির",
    "দেরকে",
    "গুলো",
    "গুলি",
    "সমূহ",
    "গণের",
    "গণ",
    # Definiteness + case
    "টিতে",
    "টাতে",
    "টির",
    "টার",
    "টিকে",
    "টাকে",
    "খানা",
    "খানি",
    # Multi-char case endings
    "থেকে",
    "দ্বারা",
    "য়েরা",
    "য়ের",
    "দের",
    # 2-char endings
    "ের",
    "য়ে",
    # 1-char / light suffixes (highest risk of false friends)
    "টি",
    "টা",
    "কে",
    "রে",
    "তে",
    "র",
    "য়",
]


def normalize_text(text: str) -> str:
    """Performs Unicode NFC normalization, zero-width stripping, and whitespace collapse."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFC", text)
    norm = re.sub(r"[\u200B\u200C\u200D\u200E\u200F\uFEFF]", "", norm)
    norm = re.sub(r"\s+", " ", norm)
    return norm.strip()


def count_consonants(text: str) -> int:
    """Counts Bengali consonants in string."""
    return sum(1 for c in text if c in BN_CONSONANTS)


def strip_bengali_suffix(word: str) -> tuple[str, str | None]:
    """Strips grammatical suffixes from a Bengali word to recover its root lemma.

    Returns (stem, stripped_suffix). Uses linguistic phonotactic guards to protect
    false-friend non-inflected roots (মাটি, সূত্র, ক্ষেত্র, বৃষ্টি, ইত্যাদি).
    """
    word = word.strip()
    if len(word) <= 3:
        return word, None

    for sfx in BENGALI_SUFFIXES:
        if word.endswith(sfx):
            stem = word[: -len(sfx)]

            # 1. Phonotactic guard: Never sever a conjunct consonant (stem cannot end with orphan virama/hasanta)
            if stem.endswith("\u09cd"):
                continue

            c_count = count_consonants(stem)
            viramas = stem.count("\u09cd")
            eff_c = c_count - viramas  # Effective distinct consonant positions
            has_indep_vowel = any(c in INDEPENDENT_VOWELS for c in stem)

            # 2. Minimum root constraint:
            # Suffixes with length <= 2 require at least 2 distinct consonant positions
            # or an independent vowel root (e.g. বই, আম)
            if len(sfx) <= 2:
                if eff_c < 2 and not (has_indep_vowel and c_count >= 1):
                    continue

            # 3. For definiteness clitics 'টি' and 'টা':
            # If the preceding stem ends in a vowel kar, it must be multisyllabic (eff_c >= 2)
            # This protects monosyllabic roots ending in vowel + টি: মাটি, বাটি, রুটি, ছুটি, ত্রুটি
            if sfx in ("টি", "টা") and stem and stem[-1] in VOWEL_KARS:
                if eff_c < 2:
                    continue

            # 4. For genitive 'র' or locative 'য়': preceding character must be a vowel sign (kar)
            if sfx in ("র", "য়"):
                if not stem or stem[-1] not in VOWEL_KARS:
                    continue

            # 5. Length guard
            if len(stem) >= 3 or (len(stem) >= 2 and (eff_c >= 2 or has_indep_vowel)):
                return stem, sfx

    return word, None


# Common Bengali question words and conversational stopwords that should not constrain lexical tsquery
QUESTION_STOPWORDS = {
    "কী",
    "কি",
    "কেন",
    "কাকে",
    "বলতে",
    "বোঝায়",
    "কখন",
    "কোথায়",
    "কত",
    "কোন",
    "কোনটি",
    "কীভাবে",
    "কিভাবে",
    "সম্পর্কে",
    "বলো",
    "বলুন",
    "আমাকে",
    "একটু",
    "দাও",
    "হলো",
    "হলে",
    "এবং",
    "ও",
    "বা",
    "কিন্তু",
    "যে",
    "এর",
    "তে",
    "টি",
    "টা",
}


def expand_query_for_tsquery(query: str) -> str:
    """Builds a robust PostgreSQL tsquery string using OR (|) clauses for inflections.

    Example:
        'সালোকসংশ্লেষণের গুরুত্ব কী?' -> '(সালোকসংশ্লেষণের | সালোকসংশ্লেষণ) & গুরুত্ব'
    """
    query = normalize_text(query)
    cleaned = re.sub(r"['\":;!?,.()\[\]{}*&|<>=+/#$@~।]", " ", query)
    tokens = [t for t in cleaned.split() if len(t) > 1 and t not in QUESTION_STOPWORDS]
    if not tokens:
        tokens = [t for t in cleaned.split() if len(t) > 1]
    if not tokens:
        return ""

    tsquery_parts = []
    for token in tokens:
        stem, sfx = strip_bengali_suffix(token)
        if sfx and stem != token:
            tsquery_parts.append(f"({token} | {stem})")
        else:
            tsquery_parts.append(token)

    return " & ".join(tsquery_parts)
