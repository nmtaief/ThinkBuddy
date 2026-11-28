"""Layer 1: Structural Syllabus Map (syllabus_index) store for NCTB/HSC textbooks.

Maintains a hierarchical per-book syllabus map containing:
- book_name, subject, paper, chapter_number
- chapter_title_bn, chapter_title_en
- topics, key_formulas_and_definitions, prerequisite_topics
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.common.config import settings
from rag.bilingual_map import translate_chapter_title_en
from rag.query_normalizer import normalize_bangla_variants, normalize_query

logger = logging.getLogger(__name__)


class SyllabusChapterEntry(BaseModel):
    """Canonical structural syllabus record for a single textbook chapter."""

    book_name: str
    subject: str
    paper: str | None = None
    class_level: int | None = None
    chapter_number: int
    chapter_title_bn: str = ""
    chapter_title_en: str = ""
    topics: list[str] = Field(default_factory=list)
    key_formulas_and_definitions: list[str] = Field(default_factory=list)
    prerequisite_topics: list[str] = Field(default_factory=list)


def _tokenize_query(text: str) -> set[str]:
    """Tokenize Bangla and English text into normalized lowercase search tokens."""
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\u0980-\u09FF\s]", " ", text.lower())
    return {tok for tok in cleaned.split() if len(tok) >= 2}


class SyllabusIndexStore:
    """Persistent JSON-backed Structural Syllabus Map with fast topic scope lookup."""

    def __init__(self, index_path: str | Path | None = None) -> None:
        self.index_path = Path(index_path or settings.SYLLABUS_INDEX_PATH)
        self._entries: list[SyllabusChapterEntry] = []
        self._loaded = False
        self._last_mtime: float | None = None
        self._scope_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    def load(self) -> None:
        """Load syllabus entries from JSON store if present."""
        if self.index_path.is_file():
            try:
                self._last_mtime = self.index_path.stat().st_mtime
                raw = json.loads(self.index_path.read_text(encoding="utf-8"))
                items = raw.get("chapters", raw) if isinstance(raw, dict) else raw
                self._entries = [SyllabusChapterEntry.model_validate(item) for item in items]
            except Exception as exc:
                logger.warning("Failed to load syllabus index from %s: %s", self.index_path, exc)
                self._entries = []
        else:
            self._entries = []
            self._last_mtime = None
        self._scope_cache.clear()
        self._loaded = True

    def save(self) -> None:
        """Persist syllabus entries to JSON store."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0",
            "total_chapters": len(self._entries),
            "chapters": [entry.model_dump() for entry in self._entries],
        }
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()
            return
        if self.index_path.is_file():
            current_mtime = self.index_path.stat().st_mtime
            if self._last_mtime != current_mtime:
                self.load()

    def clear(self) -> None:
        """Clear all entries in memory (useful for tests or clean re-index)."""
        self._entries = []
        self._scope_cache.clear()
        self._loaded = True

    def upsert_entry(self, entry: SyllabusChapterEntry) -> None:
        """Insert or update a chapter entry keyed by (book_name, subject, chapter_number)."""
        self._ensure_loaded()
        for idx, existing in enumerate(self._entries):
            if (
                existing.book_name.lower() == entry.book_name.lower()
                and existing.subject.lower() == entry.subject.lower()
                and existing.chapter_number == entry.chapter_number
            ):
                # Merge unique topics, formulas, prerequisites
                merged_topics = list(dict.fromkeys([*existing.topics, *entry.topics]))
                merged_formulas = list(
                    dict.fromkeys(
                        [
                            *existing.key_formulas_and_definitions,
                            *entry.key_formulas_and_definitions,
                        ]
                    )
                )
                merged_prereqs = list(
                    dict.fromkeys([*existing.prerequisite_topics, *entry.prerequisite_topics])
                )
                updated = entry.model_copy(
                    update={
                        "chapter_title_bn": entry.chapter_title_bn or existing.chapter_title_bn,
                        "chapter_title_en": entry.chapter_title_en or existing.chapter_title_en,
                        "paper": entry.paper or existing.paper,
                        "class_level": entry.class_level or existing.class_level,
                        "topics": merged_topics,
                        "key_formulas_and_definitions": merged_formulas,
                        "prerequisite_topics": merged_prereqs,
                    }
                )
                self._entries[idx] = updated
                return
        self._entries.append(entry)

    def upsert_entries(self, entries: list[SyllabusChapterEntry], persist: bool = True) -> int:
        """Batch upsert syllabus entries."""
        for entry in entries:
            self.upsert_entry(entry)
        if persist:
            self.save()
        return len(entries)

    def list_entries(self) -> list[SyllabusChapterEntry]:
        self._ensure_loaded()
        return list(self._entries)

    def query_scope(
        self,
        book_name: str = "",
        subject: str = "",
        topic_query: str = "",
    ) -> dict[str, Any]:
        """Query the Structural Syllabus Map for NCTB/HSC chapter boundaries and allowed formulas."""
        self._ensure_loaded()
        cache_key = (
            (book_name or "").strip().lower(),
            (subject or "").strip().lower(),
            (topic_query or "").strip().lower(),
        )
        if cache_key in self._scope_cache:
            return self._scope_cache[cache_key]

        book_q = (book_name or "").strip().lower()
        subj_q = (subject or "").strip().lower()
        norm_topic_q = normalize_query(topic_query or "")
        topic_q = norm_topic_q.strip().lower()
        query_tokens = _tokenize_query(norm_topic_q) | _tokenize_query(
            normalize_bangla_variants(norm_topic_q)
        )

        candidates = self._entries
        if book_q:
            # Match by exact/substring book_name or class level hint (e.g. "Class 8" -> "অষ্টম শ্রেণি")
            class_alias_map = {
                "class 6": "ষষ্ঠ",
                "class 7": "সপ্তম",
                "class 8": "অষ্টম",
                "class 9": "নবম",
                "class 10": "দশম",
            }
            book_terms = [book_q]
            for en_cl, bn_cl in class_alias_map.items():
                if en_cl in book_q:
                    book_terms.append(bn_cl)
            book_filtered = [
                e
                for e in candidates
                if any(bt in e.book_name.lower() or e.book_name.lower() in bt for bt in book_terms)
            ]
            if book_filtered:
                candidates = book_filtered
        if subj_q:
            subj_filtered = [
                e for e in candidates if subj_q in e.subject.lower() or e.subject.lower() in subj_q
            ]
            if subj_filtered:
                candidates = subj_filtered

        scored: list[tuple[float, SyllabusChapterEntry]] = []
        for entry in candidates:
            en_title = entry.chapter_title_en or translate_chapter_title_en(
                entry.chapter_title_bn, entry.subject, entry.chapter_number
            )
            searchable = " ".join(
                [
                    entry.book_name,
                    entry.subject,
                    entry.chapter_title_bn,
                    en_title,
                    *entry.topics,
                    *entry.key_formulas_and_definitions,
                ]
            ).lower()
            searchable_variant = normalize_bangla_variants(searchable).lower()
            score = 0.0
            if topic_q and (topic_q in searchable or topic_q in searchable_variant):
                score += 10.0
            entry_tokens = _tokenize_query(searchable) | _tokenize_query(searchable_variant)
            overlap = query_tokens & entry_tokens
            score += float(len(overlap)) * 2.0
            # Substring fallback for Bangla/English partial stems
            if topic_q and not overlap:
                for tok in query_tokens:
                    if len(tok) >= 3 and (tok in searchable or tok in searchable_variant):
                        score += 1.5
            if not topic_q:
                score += 1.0
            if score > 0 or not query_tokens:
                scored.append((score, entry))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        matched_entries = [pair[1] for pair in scored[:5]]

        if not matched_entries:
            return {
                "found": False,
                "book_name": book_name,
                "subject": subject,
                "topic_query": topic_query,
                "matched_chapters": [],
                "allowed_topics": [],
                "key_formulas_and_definitions": [],
                "prerequisite_topics": [],
                "scope_note": "No matching syllabus chapter found in the structural map for this query.",
            }

        allowed_topics: list[str] = []
        formulas: list[str] = []
        prereqs: list[str] = []
        chapters_out: list[dict[str, Any]] = []
        for e in matched_entries:
            allowed_topics.extend(e.topics)
            formulas.extend(e.key_formulas_and_definitions)
            prereqs.extend(e.prerequisite_topics)
            chapters_out.append(
                {
                    "book_name": e.book_name,
                    "subject": e.subject,
                    "paper": e.paper,
                    "class_level": e.class_level,
                    "chapter_number": e.chapter_number,
                    "chapter_title_bn": e.chapter_title_bn,
                    "chapter_title_en": e.chapter_title_en,
                    "topics": e.topics,
                    "key_formulas_and_definitions": e.key_formulas_and_definitions,
                    "prerequisite_topics": e.prerequisite_topics,
                }
            )

        result = {
            "found": True,
            "book_name": matched_entries[0].book_name,
            "subject": matched_entries[0].subject,
            "topic_query": topic_query,
            "matched_chapters": chapters_out,
            "allowed_topics": list(dict.fromkeys(allowed_topics)),
            "key_formulas_and_definitions": list(dict.fromkeys(formulas)),
            "prerequisite_topics": list(dict.fromkeys(prereqs)),
            "scope_note": (
                "Stay strictly within the matched NCTB/HSC chapter topics and allowed formulas above. "
                "Do not introduce university-level theorems outside syllabus scope."
            ),
        }
        if len(self._scope_cache) >= 512:
            self._scope_cache.clear()
        self._scope_cache[cache_key] = result
        return result


_default_syllabus_store: SyllabusIndexStore | None = None


def get_syllabus_index_store(index_path: str | Path | None = None) -> SyllabusIndexStore:
    """Return singleton or custom-path SyllabusIndexStore."""
    global _default_syllabus_store
    if index_path is not None:
        store = SyllabusIndexStore(index_path=index_path)
        store.load()
        return store
    if _default_syllabus_store is None:
        _default_syllabus_store = SyllabusIndexStore()
        _default_syllabus_store.load()
    return _default_syllabus_store
