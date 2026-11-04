"""
Religion & Observance Audit Script
Performs a repository-wide search for all English and Bengali religious terms,
and locates every usage of `blocked_observance_keys`.
"""
import subprocess
import sys
from pathlib import Path

# Terms to audit
EN_TERMS = [
    "religion", "religious", "faith", "bismillah", "assalamu",
    "islam", "muslim", "hindu", "christian", "buddhist"
]

BN_TERMS = [
    "ধর্ম", "ইসলাম", "মুসলিম", "হিন্দু", "বৌদ্ধ", "খ্রিস্টান",
    "বিসমিল্লাহ", "আসসালামু", "সালাম", "রোজা", "পূজা", "প্রার্থনা"
]

ALL_TERMS = EN_TERMS + BN_TERMS

def get_tracked_files() -> list[str]:
    res = subprocess.run(["git", "ls-files"], capture_output=True, text=True, encoding="utf-8")
    return [f for f in res.stdout.splitlines() if f.strip()]

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 80)
    print("COMPREHENSIVE RELIGION & OBSERVANCE AUDIT")
    print("=" * 80)
    
    files = get_tracked_files()
    print(f"Total tracked files in git: {len(files)}\n")

    term_matches = {t: [] for t in ALL_TERMS}
    observance_key_matches = []

    # Files to exclude from term flagging (audit scripts themselves or git history docs)
    skip_files = {"scripts/religion_audit.py"}

    for fpath in files:
        if fpath in skip_files or fpath.endswith(".png") or fpath.endswith(".jpg"):
            continue
        try:
            content = Path(fpath).read_text(encoding="utf-8")
        except Exception:
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            line_lower = line.lower()
            
            # Check blocked_observance_keys
            if "blocked_observance_keys" in line:
                observance_key_matches.append((fpath, line_no, line.strip()))

            for term in ALL_TERMS:
                # For english, match whole word or substring as appropriate
                if term in line_lower:
                    term_matches[term].append((fpath, line_no, line.strip()))

    print("--- 1. AUDIT OF RELIGIOUS TERMS (ENGLISH & BANGLA) ---")
    total_term_hits = 0
    for term, hits in term_matches.items():
        if hits:
            total_term_hits += len(hits)
            print(f"\n[TERM: '{term}'] Found {len(hits)} occurrences:")
            for fpath, lno, ltext in hits:
                print(f"  {fpath}:{lno}: {ltext}")

    if total_term_hits == 0:
        print("ALL AUDITED RELIGIOUS TERMS (ENGLISH & BANGLA): ZERO OCCURRENCES FOUND ACROSS ENTIRE CODEBASE!")
    else:
        print(f"\nTotal term occurrences found: {total_term_hits}")

    print("\n" + "=" * 80)
    print("--- 2. ALL USAGES OF 'blocked_observance_keys' ---")
    print("=" * 80)
    if not observance_key_matches:
        print("None found.")
    else:
        for fpath, lno, ltext in observance_key_matches:
            print(f"  {fpath}:{lno}: {ltext}")

    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()

