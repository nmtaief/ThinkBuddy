"""Column-level encryption for question keys stored at rest.

Per docs/05_SECURE_QUIZ.md and P04 hardening:
- Uses AES-256-GCM authenticated encryption.
- Encryption key is injected via QUESTION_KEY_ENCRYPTION_KEY environment variable.
- In Beta, volume encryption (LUKS / KMS) provides baseline at-rest protection;
  column encryption protects against unauthorized database inspection.
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


def _get_aes_key() -> bytes:
    key_str = getattr(settings, "QUESTION_KEY_ENCRYPTION_KEY", "dev_question_key_aes_gcm_32bytes_secret_key!")
    # Derive a strict 32-byte (256-bit) key using SHA-256
    return hashlib.sha256(key_str.encode("utf-8")).digest()


def encrypt_column_value(data: Any, key_str: str | None = None) -> str:
    """Encrypt payload with AES-256-GCM using specified or default key."""
    raw_key = (key_str or getattr(settings, "QUESTION_KEY_ENCRYPTION_KEY", "dev_question_key_aes_gcm_32bytes_secret_key!")).encode("utf-8")
    key = hashlib.sha256(raw_key).digest()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, json_bytes, None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_column_value(encrypted_payload: str, key_str: str | None = None) -> Any:
    """Decrypt AES-256-GCM payload using specified or default key."""
    if not encrypted_payload:
        return None
    raw_key = (key_str or getattr(settings, "QUESTION_KEY_ENCRYPTION_KEY", "dev_question_key_aes_gcm_32bytes_secret_key!")).encode("utf-8")
    key = hashlib.sha256(raw_key).digest()
    aesgcm = AESGCM(key)
    raw_bytes = base64.urlsafe_b64decode(encrypted_payload.encode("ascii"))
    if len(raw_bytes) < 12:
        raise ValueError("Ciphertext too short")
    nonce = raw_bytes[:12]
    ciphertext = raw_bytes[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(decrypted_bytes.decode("utf-8"))


# Backwards compatibility aliases
encrypt_key_data = encrypt_column_value
decrypt_key_data = decrypt_column_value
