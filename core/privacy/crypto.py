"""Cryptographic helpers for encrypting family data exports at rest."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.common.config import settings

logger = logging.getLogger("thinkbuddy.privacy.crypto")

DEFAULT_KEY_VERSION = "v1"


def _derive_key(key_str: str) -> bytes:
    return hashlib.sha256(key_str.encode("utf-8")).digest()


def encrypt_export_payload(
    data: Any,
    key_str: str | None = None,
    key_version: str = DEFAULT_KEY_VERSION,
) -> str:
    """Encrypt family data export JSON with AES-256-GCM and prepend key version."""
    raw_key = key_str or getattr(
        settings,
        "EXPORT_ENCRYPTION_KEY",
        "dev_export_aes_gcm_32bytes_encryption_key!",
    )
    key = _derive_key(raw_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    json_bytes = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, json_bytes, None)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{key_version}:{encoded}"


def decrypt_export_payload(
    payload_str: str,
    key_str: str | None = None,
) -> Any:
    """Decrypt AES-256-GCM encrypted family data export payload."""
    raw_key = key_str or getattr(
        settings,
        "EXPORT_ENCRYPTION_KEY",
        "dev_export_aes_gcm_32bytes_encryption_key!",
    )
    key = _derive_key(raw_key)
    aesgcm = AESGCM(key)

    if ":" in payload_str:
        _, encoded = payload_str.split(":", 1)
    else:
        encoded = payload_str

    raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
    if len(raw) < 28:  # 12-byte nonce + 16-byte tag
        raise ValueError("Invalid encrypted payload size")

    nonce, ciphertext = raw[:12], raw[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(decrypted_bytes.decode("utf-8"))
