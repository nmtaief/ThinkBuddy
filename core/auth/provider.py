"""Authentication provider interface with Firebase and Fake implementations.

Follows P01 requirements: phone OTP + Google behind an AuthProvider interface,
with a FakeAuthProvider for fast, deterministic local development and automated testing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.common.config import settings


@dataclass(frozen=True)
class AuthProviderUser:
    """Standardized identity payload returned after verifying third-party credentials."""

    uid: str
    provider: str  # "phone_otp", "google", "fake"
    phone: str | None = None
    email: str | None = None
    display_name: str | None = None


@runtime_checkable
class AuthProvider(Protocol):
    """Protocol for external identity verification."""

    async def verify_token(self, id_token: str) -> AuthProviderUser:
        """Verify provider credential/token and return normalized identity."""
        ...


class FakeAuthProvider:
    """In-memory identity provider for automated testing and local development.

    CRITICAL SECURITY GUARD:
    Cannot be instantiated or loaded unless ENV=local. In all other environments
    (development, staging, production), attempts to load will raise a RuntimeError.

    Supports:
    - String prefix syntax: 'fake:phone:+8801700000001', 'fake:google:parent@thinkbuddy.org'
    - JSON payload strings: '{"uid": "user-123", "phone": "+8801700000001", "role": "parent"}'
    """

    def __init__(self) -> None:
        if not settings.is_local:
            msg = (
                f"Security Violation: FakeAuthProvider cannot load when ENV='{settings.ENV}'. "
                "FakeAuthProvider is strictly forbidden unless ENV=local."
            )
            raise RuntimeError(msg)

    async def verify_token(self, id_token: str) -> AuthProviderUser:
        token = id_token.strip()

        # Reject empty or invalid token formats
        if not token or token == "invalid_token":  # noqa: S105
            msg = "Invalid third-party identity token."

            raise ValueError(msg)

        # JSON serialized test token
        if token.startswith("{") and token.endswith("}"):
            try:
                data = json.loads(token)
                uid = data.get("uid") or f"fake_{data.get('phone') or data.get('email') or 'user'}"
                return AuthProviderUser(
                    uid=uid,
                    provider=data.get("provider", "fake"),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    display_name=data.get("display_name", "Test User"),
                )
            except json.JSONDecodeError as exc:
                msg = f"Malformed test auth token: {exc}"
                raise ValueError(msg) from exc

        # Format: fake:phone:<phone_number>
        if token.startswith("fake:phone:"):
            phone = token.removeprefix("fake:phone:").strip()
            return AuthProviderUser(
                uid=f"fake_phone_{phone}",
                provider="phone_otp",
                phone=phone,
                display_name=f"User {phone[-4:]}",
            )

        # Format: fake:google:<email>
        if token.startswith("fake:google:"):
            email = token.removeprefix("fake:google:").strip()
            return AuthProviderUser(
                uid=f"fake_google_{email}",
                provider="google",
                email=email,
                display_name=email.split("@")[0].capitalize(),
            )

        # Generic fake fallback for test tokens
        if token.startswith("fake:"):
            name = token.removeprefix("fake:")
            return AuthProviderUser(
                uid=f"fake_uid_{name}",
                provider="fake",
                display_name=name,
            )

        msg = f"Unsupported or unrecognized token format: {token[:10]}..."
        raise ValueError(msg)


class FirebaseAuthProvider:
    """Production identity verification via Google Firebase Auth.

    Cryptographic Verification Guarantees:
    1. Signature: Validated against Google's live public RSA/ECDSA key certs from Google JWKS.
    2. Issuer: Must strictly match 'https://securetoken.google.com/<FIREBASE_PROJECT_ID>'.
    3. Audience: Must strictly match the configured Firebase Project ID.
    4. Expiry: Token expiration ('exp') is verified with clock skew checks; future 'iat' rejected.
    5. Revocation: Optionally checks token revocation status against Firebase Auth backend.
    """

    def __init__(self, check_revoked: bool = True) -> None:
        self.check_revoked = check_revoked

    async def verify_token(self, id_token: str) -> AuthProviderUser:
        # Production Firebase ID token verification
        # Cryptographically verifies signature, issuer, audience, and expiry
        try:
            import firebase_admin.auth as fb_auth

            decoded = fb_auth.verify_id_token(id_token, check_revoked=self.check_revoked)

            firebase_id = decoded.get("firebase", {})
            sign_in_provider = firebase_id.get("sign_in_provider", "firebase")
            provider = "phone_otp" if sign_in_provider == "phone" else sign_in_provider

            return AuthProviderUser(
                uid=decoded["uid"],
                provider=provider,
                phone=decoded.get("phone_number"),
                email=decoded.get("email"),
                display_name=decoded.get("name"),
            )
        except ImportError:
            # Fallback if firebase-admin package is not yet installed in local dev
            msg = (
                "Firebase Admin SDK not installed. "
                "In non-local environments, firebase-admin is required."
            )
            raise ValueError(msg) from None


def get_auth_provider() -> AuthProvider:
    """Factory returning appropriate provider for current environment.

    Enforces that FakeAuthProvider cannot load unless ENV=local.
    """
    if settings.is_local:
        return FakeAuthProvider()
    return FirebaseAuthProvider()
