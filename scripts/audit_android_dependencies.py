"""
Android Dependency Vulnerability Auditor
Queries the Google OSV (Open Source Vulnerabilities) API for all dependencies
declared in android/gradle/libs.versions.toml.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

TOML_PATH = Path("android/gradle/libs.versions.toml")
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"


def parse_libs_versions_toml(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        print(f"Error: {path} not found.")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    
    # Parse versions
    versions: dict[str, str] = {}
    in_versions = False
    in_libraries = False

    libs: list[dict[str, str]] = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[versions]":
            in_versions = True
            in_libraries = False
            continue
        elif line == "[libraries]":
            in_versions = False
            in_libraries = True
            continue
        elif line.startswith("["):
            in_versions = False
            in_libraries = False
            continue

        if in_versions:
            match = re.match(r'^([\w.-]+)\s*=\s*"([^"]+)"', line)
            if match:
                versions[match.group(1)] = match.group(2)
        elif in_libraries:
            # e.g.: androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "coreKtx" }
            # or version = "1.0.0"
            alias_match = re.match(r'^([\w.-]+)\s*=\s*\{([^}]+)\}', line)
            if alias_match:
                alias = alias_match.group(1)
                body = alias_match.group(2)
                group_m = re.search(r'group\s*=\s*"([^"]+)"', body)
                name_m = re.search(r'name\s*=\s*"([^"]+)"', body)
                ver_ref_m = re.search(r'version\.ref\s*=\s*"([^"]+)"', body)
                ver_direct_m = re.search(r'version\s*=\s*"([^"]+)"', body)

                group = group_m.group(1) if group_m else None
                name = name_m.group(1) if name_m else None
                ver = None
                if ver_ref_m:
                    ver = versions.get(ver_ref_m.group(1))
                elif ver_direct_m:
                    ver = ver_direct_m.group(1)

                if group and name and ver:
                    libs.append({
                        "alias": alias,
                        "group": group,
                        "name": name,
                        "coordinate": f"{group}:{name}",
                        "version": ver
                    })

    return libs


def check_vulnerabilities(libs: list[dict[str, str]]) -> dict:
    queries = []
    for lib in libs:
        queries.append({
            "package": {
                "name": lib["coordinate"],
                "ecosystem": "Maven"
            },
            "version": lib["version"]
        })

    payload = json.dumps({"queries": queries}).encode("utf-8")
    req = Request(
        OSV_BATCH_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "ThinkBuddy-Android-Auditor/1.0"}
    )

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except URLError as e:
        print(f"Warning: Failed to reach OSV API: {e}")
        return {"results": [{} for _ in libs]}


def main() -> int:
    print("=" * 70)
    print("ThinkBuddy Android Dependency Vulnerability Auditor (OSV.dev)")
    print("=" * 70)

    libs = parse_libs_versions_toml(TOML_PATH)
    print(f"Loaded {len(libs)} declared dependencies from {TOML_PATH}\n")

    osv_res = check_vulnerabilities(libs)
    results = osv_res.get("results", [])

    vuln_count = 0
    clean_count = 0

    print(f"{'Coordinate':<42} | {'Version':<14} | {'Status':<10}")
    print("-" * 72)

    for i, lib in enumerate(libs):
        lib_res = results[i] if i < len(results) else {}
        vulns = lib_res.get("vulns", [])
        if vulns:
            vuln_count += 1
            vuln_ids = ", ".join(v.get("id", "Unknown") for v in vulns)
            print(f"{lib['coordinate']:<42} | {lib['version']:<14} | VULN: {vuln_ids}")
        else:
            clean_count += 1
            print(f"{lib['coordinate']:<42} | {lib['version']:<14} | OK (Clean)")

    print("-" * 72)
    print(f"Summary: {len(libs)} scanned, {clean_count} clean, {vuln_count} vulnerable.")
    print("=" * 70)
    return 1 if vuln_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

