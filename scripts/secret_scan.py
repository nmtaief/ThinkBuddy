"""Local security & secret scanner adhering to Gitleaks pattern standards."""

import re
from pathlib import Path

# Standard secret pattern signatures
PATTERNS: dict[str, re.Pattern[str]] = {
    "Private Key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "Generic High Entropy Secret": re.compile(
        r"(?i)(?:api_key|secret_key|private_key|auth_token)\s*=\s*['\"][A-Za-z0-9+/=]{32,}['\"]"
    ),
    "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub Token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"),
    "Hardcoded Password Assignment": re.compile(
        r"(?i)(?:password|passwd|pwd)\s*=\s*['\"][^'\"]{8,}['\"]"
    ),
}

EXCLUDE_DIRS = {".git", ".pytest_cache", ".venv", "venv", "__pycache__", "docs-generated"}
EXCLUDE_FILES = {".env.example"}


def scan_repo() -> list[dict[str, str]]:
    findings = []
    root = Path(".")

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES or path.name.endswith(".pyc"):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for rule_name, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                matched_text = match.group(0)
                # Allow test token literals in tests/
                if "tests" in path.parts and ("test_" in matched_text or "token" in matched_text):
                    continue
                # Allow placeholder values
                if "placeholder" in matched_text or "dev_password" in matched_text:
                    continue

                findings.append(
                    {
                        "file": str(path),
                        "rule": rule_name,
                        "match": matched_text[:20] + "...",
                    }
                )
    return findings


if __name__ == "__main__":
    results = scan_repo()
    if results:
        print(f"Secret scan failed with {len(results)} findings:")
        for res in results:
            print(f"  - [{res['rule']}] in {res['file']}: {res['match']}")
        exit(1)
    else:
        print("Secret scan passed: 0 secret leaks identified.")
        exit(0)
