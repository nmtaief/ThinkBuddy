"""Retrieval evaluation harness for ThinkBuddy curriculum search.

Measures hybrid retrieval quality across Bangla and English test sets:
- Hit-rate@1, Hit-rate@3, Hit-rate@5 (correct chapter retrieved)
- Citation page accuracy@1, Citation page accuracy@5 (exact printed page identified)
- Enforces configurable threshold gates for CI/CD pipelines
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.common.database import AsyncSessionLocal
from rag.embedding import get_embedding_provider
from rag.vector_store import PgVectorStore

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("eval_retrieval")


async def run_evaluation(
    dataset_path: str | Path,
    min_hit_rate: float = 0.80,
    min_page_acc: float = 0.80,
    top_k: int = 5,
) -> dict[str, Any]:
    """Execute evaluation against live Postgres vector store."""
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Evaluation dataset not found: {dataset_path}")

    dataset = json.loads(path.read_text(encoding="utf-8"))
    if not dataset:
        raise ValueError("Dataset is empty")

    provider = get_embedding_provider()

    total_queries = len(dataset)
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    page_hits_at_1 = 0
    page_hits_at_5 = 0

    language_stats: dict[str, dict[str, int]] = {}

    print("\n" + "=" * 80)
    print("THINKBUDDY RETRIEVAL EVALUATION HARNESS")
    print(f"Dataset: {path.name} | Total Queries: {total_queries} | Top-K: {top_k}")
    print("=" * 80)

    async with AsyncSessionLocal() as session:
        vector_store = PgVectorStore(session)

        for item in dataset:
            q_text = item["question"]
            lang = item.get("language", "bn")
            exp_chapter = int(item["expected_chapter_number"])
            exp_page = int(item["expected_printed_page"])
            class_lvl = int(item.get("class_level", 7))
            subj = item.get("subject", "math")

            if lang not in language_stats:
                language_stats[lang] = {"total": 0, "hits": 0, "page_hits": 0}
            language_stats[lang]["total"] += 1

            # Embed and hybrid retrieve
            q_vec = await provider.embed_query(q_text)
            filters = {"class_level": class_lvl, "subject": subj}
            results = await vector_store.search_hybrid(
                query_text=q_text,
                query_vector=q_vec,
                limit=top_k,
                filters=filters,
            )

            # Evaluate chapter hit
            retrieved_chapters = [r.chapter_number for r in results]
            retrieved_pages = [r.printed_page for r in results]

            hit_1 = len(retrieved_chapters) > 0 and retrieved_chapters[0] == exp_chapter
            hit_3 = exp_chapter in retrieved_chapters[:3]
            hit_5 = exp_chapter in retrieved_chapters[:5]

            page_1 = len(retrieved_pages) > 0 and retrieved_pages[0] == exp_page
            page_5 = exp_page in retrieved_pages[:5]

            if hit_1:
                hits_at_1 += 1
            if hit_3:
                hits_at_3 += 1
            if hit_5:
                hits_at_5 += 1
            if page_1:
                page_hits_at_1 += 1
            if page_5:
                page_hits_at_5 += 1

            if hit_5:
                language_stats[lang]["hits"] += 1
            if page_5:
                language_stats[lang]["page_hits"] += 1

            status_mark = "[EXACT]" if page_1 else ("[TOP5]" if page_5 else "[MISS]")
            ch_top1 = retrieved_chapters[:1]
            pg_top1 = retrieved_pages[:1]
            print(
                f"  {status_mark} [{lang.upper()}] {q_text[:30]}... "
                f"-> Exp(Ch:{exp_chapter}, Pg:{exp_page}) | Top-1(Ch:{ch_top1}, Pg:{pg_top1})"
            )

    hit_rate_1 = hits_at_1 / total_queries
    hit_rate_3 = hits_at_3 / total_queries
    hit_rate_5 = hits_at_5 / total_queries
    page_acc_1 = page_hits_at_1 / total_queries
    page_acc_5 = page_hits_at_5 / total_queries

    print("-" * 80)
    print("SUMMARY RESULTS:")
    print(f"  * Hit-Rate@1 (Chapter):     {hit_rate_1 * 100:.1f}% ({hits_at_1}/{total_queries})")
    print(f"  * Hit-Rate@3 (Chapter):     {hit_rate_3 * 100:.1f}% ({hits_at_3}/{total_queries})")
    print(f"  * Hit-Rate@5 (Chapter):     {hit_rate_5 * 100:.1f}% ({hits_at_5}/{total_queries})")
    print(f"  * Page Acc@1:         {page_acc_1 * 100:.1f}% ({page_hits_at_1}/{total_queries})")
    print(f"  * Page Acc@5:         {page_acc_5 * 100:.1f}% ({page_hits_at_5}/{total_queries})")
    print("\nPER-LANGUAGE BREAKDOWN:")
    for lang, stat in language_stats.items():
        tot = stat["total"]
        h = stat["hits"]
        p = stat["page_hits"]
        h_pct = h / tot * 100
        p_pct = p / tot * 100
        print(
            f"  * [{lang.upper()}]: Hit@5 = {h_pct:.1f}% ({h}/{tot}) | "
            f"PageAcc@5 = {p_pct:.1f}% ({p}/{tot})"
        )

    # Threshold gate verification
    passed_gate = (hit_rate_5 >= min_hit_rate) and (page_acc_5 >= min_page_acc)
    print("=" * 80)
    if passed_gate:
        print(
            f"RETRIEVAL QUALITY GATE PASSED "
            f"(Thresholds: Hit@5 >= {min_hit_rate * 100}%, PageAcc@5 >= {min_page_acc * 100}%)"
        )
    else:
        print(
            f"RETRIEVAL QUALITY GATE FAILED "
            f"(Required Hit@5 >= {min_hit_rate * 100}%, PageAcc@5 >= {min_page_acc * 100}%)"
        )
    print("=" * 80 + "\n")

    return {
        "total_queries": total_queries,
        "hit_rate_1": hit_rate_1,
        "hit_rate_3": hit_rate_3,
        "hit_rate_5": hit_rate_5,
        "page_acc_1": page_acc_1,
        "page_acc_5": page_acc_5,
        "language_stats": language_stats,
        "passed_gate": passed_gate,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ThinkBuddy RAG retrieval evaluation harness")
    parser.add_argument(
        "--dataset",
        default="tests/data/retrieval_eval_dataset.json",
        help="Path to evaluation dataset JSON",
    )
    parser.add_argument(
        "--min-hit-rate",
        type=float,
        default=0.80,
        help="Minimum required Hit-rate@5 threshold (default: 0.80)",
    )
    parser.add_argument(
        "--min-page-accuracy",
        type=float,
        default=0.80,
        help="Minimum required citation page accuracy@5 threshold (default: 0.80)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks (default: 5)",
    )

    args = parser.parse_args()

    results = asyncio.run(
        run_evaluation(
            dataset_path=args.dataset,
            min_hit_rate=args.min_hit_rate,
            min_page_acc=args.min_page_accuracy,
            top_k=args.top_k,
        )
    )

    if not results["passed_gate"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
