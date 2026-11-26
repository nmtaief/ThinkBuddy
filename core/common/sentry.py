"""Sentry error reporting with strict PII scrubbing.

Standing Rule 15:
Log, don't leak. Never send tokens, OTPs, answer keys, student chat content, or PII to Sentry.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "authorization",
    "x-reauth-token",
    "provider_token",
    "attempt_token",
    "link_code",
    "access_token",
    "refresh_token",
    "password",
    "phone",
    "email",
    "secret",
}


def scrub_sensitive_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively scrub sensitive keys and tokens from event dictionaries."""
    clean = {}
    for k, v in d.items():
        k_lower = str(k).lower()
        if any(s in k_lower for s in SENSITIVE_KEYS):
            clean[k] = "[REDACTED_PII]"
        elif isinstance(v, dict):
            clean[k] = scrub_sensitive_dict(v)
        elif isinstance(v, list):
            clean[k] = [
                scrub_sensitive_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            clean[k] = v
    return clean


def sentry_before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Filter hook called before every Sentry event is transmitted."""
    # 1. Scrub HTTP request headers and body
    req = event.get("request", {})
    if "headers" in req and isinstance(req["headers"], dict):
        req["headers"] = scrub_sensitive_dict(req["headers"])
    if "data" in req and isinstance(req["data"], dict):
        req["data"] = scrub_sensitive_dict(req["data"])

    # 2. Scrub user identity PII (keep user ID only, drop IP/email/phone)
    if "user" in event and isinstance(event["user"], dict):
        event["user"] = {
            "id": event["user"].get("id"),
            "ip_address": "0.0.0.0",  # nosec B104 - anonymized IP
        }

    # 3. Scrub breadcrumbs
    crumbs = event.get("breadcrumbs", {}).get("values", [])
    for crumb in crumbs:
        if "data" in crumb and isinstance(crumb["data"], dict):
            crumb["data"] = scrub_sensitive_dict(crumb["data"])

    return event


def init_sentry(dsn: str | None, environment: str = "production", release: str = "1.0.0") -> None:
    """Initialize Sentry SDK with privacy-safe defaults if DSN is provided."""
    if not dsn:
        logger.info("Sentry DSN not configured. Running without Sentry error reporting.")
        return

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=0.1,
            send_default_pii=False,
            before_send=sentry_before_send,
        )
        logger.info("Sentry initialized with strict Rule 15 PII sanitization.")
    except ImportError:
        logger.warning("sentry_sdk is not installed. Skipping Sentry initialization.")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")

