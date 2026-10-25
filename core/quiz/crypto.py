"""Column-level encryption for question keys stored at rest.

Per docs/05_SECURE_QUIZ.md and P04 hardening:
- Uses AES-256-GCM authenticated encryption.
- Enabled in production for sensitive question answer keys (question_keys).
- In Beta, volume encryption (LUKS / KMS EBS encryption) provides baseline at-rest protection;
  column encryption protects against unauthorized database inspection and cross-role leakage.
- Key source: QUESTION_KEY_ENCRYPTION_KEY injected via environment variable from Secrets Manager.
- Key rotation approach: Version-prefixed payloads (e.g. 'v1:<nonce+ciphertext>').
  During key rotation, new writes use the new key version while reads support legacy versions
  via fallback key lookup, followed by an offline background re-encryption job.
- Database runtime role: The API process executes under database role `thinkbuddy_api`
  (strictly revoked from `question_keys`, restricted to `v_questions_public`), while grading
  and key ingestion run under authority role `thinkbuddy_grading`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.common.config import settings

logger = logging.getLogger("thinkbuddy.quiz.crypto")

DEFAULT_KEY_VERSION = "v1"


def _derive_key(key_str: str) -> bytes:
    return hashlib.sha256(key_str.encode("utf-8")).digest()


def encrypt_column_value(data: Any, key_str: str | None = None, key_version: str = DEFAULT_KEY_VERSION) -> str:
    """Encrypt payload with AES-256-GCM using specified or default key and prepend key version."""
    raw_key = key_str or getattr(settings, "QUESTION_KEY_ENCRYPTION_KEY", "dev_question_key_aes_gcm_32bytes_secret_key!")
    key = _derive_key(raw_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, json_bytes, None)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{key_version}:{encoded}"


def decrypt_column_value(encrypted_payload: str, key_str: str | None = None, legacy_keys: dict[str, str] | None = None) -> Any:
    """Decrypt AES-256-GCM payload supporting version prefixes and key rotation fallback."""
    if not encrypted_payload:
        return None

    payload = encrypted_payload
    version = DEFAULT_KEY_VERSION
    if ":" in payload:
        prefix, remainder = payload.split(":", 1)
        if prefix.startswith("v"):
            version = prefix
            payload = remainder

    # Resolve key by version if legacy keys map provided
    raw_key = key_str
    if not raw_key and legacy_keys and version in legacy_keys:
        raw_key = legacy_keys[version]
    if not raw_key:
        raw_key = getattr(settings, "QUESTION_KEY_ENCRYPTION_KEY", "dev_question_key_aes_gcm_32bytes_secret_key!")

    key = _derive_key(raw_key)
    aesgcm = AESGCM(key)
    raw_bytes = base64.urlsafe_b64decode(payload.encode("ascii"))
    if len(raw_bytes) < 12:
        raise ValueError("Ciphertext too short")
    nonce = raw_bytes[:12]
    ciphertext = raw_bytes[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(decrypted_bytes.decode("utf-8"))


# Backwards compatibility aliases
encrypt_key_data = encrypt_column_value
decrypt_key_data = decrypt_column_value
