"""Authentication provider interface with Firebase and Fake implementations.

Follows P01 requirements: phone OTP + Google behind an AuthProvider interface,
with a FakeAuthProvider for fast, deterministic local development and automated testing.
"""

from __future__ import annotations

import json
import time
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
    auth_time: int | None = None


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
                    auth_time=data.get("auth_time", int(time.time())),
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
                auth_time=int(time.time()),
            )

        # Format: fake:google:<email>
        if token.startswith("fake:google:"):
            email = token.removeprefix("fake:google:").strip()
            return AuthProviderUser(
                uid=f"fake_google_{email}",
                provider="google",
                email=email,
                display_name=email.split("@")[0].capitalize(),
                auth_time=int(time.time()),
            )

        # Generic fake fallback for test tokens
        if token.startswith("fake:"):
            name = token.removeprefix("fake:")
            return AuthProviderUser(
                uid=f"fake_uid_{name}",
                provider="fake",
                display_name=name,
                auth_time=int(time.time()),
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
                auth_time=decoded.get("auth_time"),
            )
        except ImportError:
            # Fallback if firebase-admin package is not yet installed in local dev
            msg = (
                "Firebase Admin SDK not installed. "
                "In non-local environments, firebase-admin is required."
            )
            raise ValueError(msg) from None


class GoogleAuthProvider:
    """Production identity verification via Google OAuth2 ID Token.

    Verifies JWT signature against Google's public JWKS certificates
    (https://www.googleapis.com/oauth2/v3/certs), verifying issuer, expiry,
    and audience.
    """

    GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
    GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

    def __init__(self, client_id: str | None = None) -> None:
        self.client_id = client_id or getattr(settings, "GOOGLE_CLIENT_ID", None)
        self._jwks_client = None

    def _get_jwks_client(self):
        if self._jwks_client is None:
            import jwt
            self._jwks_client = jwt.PyJWKClient(self.GOOGLE_JWKS_URL)
        return self._jwks_client

    async def verify_token(self, id_token: str) -> AuthProviderUser:
        token = id_token.strip()
        if not token:
            msg = "Missing Google ID token."
            raise ValueError(msg)

        # In local dev environment, allow fake:google: test tokens
        if settings.is_local and (token.startswith("fake:google:") or token.startswith("fake:")):
            fake_prov = FakeAuthProvider()
            return await fake_prov.verify_token(token)

        try:
            import jwt

            jwks_client = self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            options = {"verify_aud": bool(self.client_id)}
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id if self.client_id else None,
                options=options,
            )
            iss = decoded.get("iss", "")
            if iss not in self.GOOGLE_ISSUERS:
                msg = f"Invalid Google ID token issuer: {iss}"
                raise ValueError(msg)

            sub = decoded.get("sub")
            if not sub:
                msg = "Missing subject (sub) in Google ID token."
                raise ValueError(msg)

            email = decoded.get("email")
            display_name = decoded.get("name") or (email.split("@")[0] if email else "Google User")

            return AuthProviderUser(
                uid=f"google_{sub}",
                provider="google",
                email=email,
                display_name=display_name,
                auth_time=decoded.get("iat"),
            )
        except Exception as exc:
            msg = f"Google ID token verification failed: {exc}"
            raise ValueError(msg) from exc


_fake_provider: FakeAuthProvider | None = None
_firebase_provider: FirebaseAuthProvider | None = None
_google_provider: GoogleAuthProvider | None = None


def get_google_auth_provider() -> GoogleAuthProvider:
    """Factory returning Google Auth provider singleton."""
    global _google_provider
    if _google_provider is None:
        _google_provider = GoogleAuthProvider()
    return _google_provider


def get_auth_provider() -> AuthProvider:
    """Factory returning appropriate provider for current environment.

    Enforces that FakeAuthProvider cannot load unless ENV=local.
    """
    global _fake_provider, _firebase_provider
    if settings.is_local:
        if _fake_provider is None:
            _fake_provider = FakeAuthProvider()
        return _fake_provider
    if _firebase_provider is None:
        _firebase_provider = FirebaseAuthProvider()
    return _firebase_provider
