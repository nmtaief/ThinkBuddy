"""Uptime healthcheck probe for ThinkBuddy services.

Probes /healthz on Gateway and Core services to ensure they are up and responsive.
Exit code 0 indicates healthy services; non-zero indicates an outage.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request
import json

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
CORE_URL = os.environ.get("CORE_URL", "http://localhost:8001")
TIMEOUT_SECONDS = float(os.environ.get("PROBE_TIMEOUT_SECONDS", "5.0"))


def probe(url: str, name: str) -> bool:
    target = f"{url.rstrip('/')}/healthz"
    start = time.perf_counter()
    try:
        req = urllib.request.Request(target, headers={"User-Agent": "ThinkBuddy-UptimeProbe/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000
            status = resp.status
            body = resp.read().decode("utf-8")
            if status == 200:
                print(f"[OK] {name} ({target}) responded {status} in {elapsed_ms:.1f}ms: {body.strip()}")
                return True
            else:
                print(f"[FAIL] {name} ({target}) unexpected status {status} in {elapsed_ms:.1f}ms: {body.strip()}", file=sys.stderr)
                return False
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"[DOWN] {name} ({target}) failed in {elapsed_ms:.1f}ms: {e}", file=sys.stderr)
        return False


def main() -> int:
    print(f"Running uptime probe against Gateway ({GATEWAY_URL}) and Core ({CORE_URL})...")
    gw_ok = probe(GATEWAY_URL, "Gateway")
    core_ok = probe(CORE_URL, "Core")

    if gw_ok and core_ok:
        print("All probed services are HEALTHY.")
        return 0
    else:
        print("One or more services FAILED healthcheck.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

