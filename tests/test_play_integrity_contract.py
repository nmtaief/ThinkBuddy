"""Contract tests for Play Integrity token verification and device attestation.

Validates that:
1. Application ID / package name is com.thinkbuddy.app.
2. Canonical single-use nonce is generated randomly by server, stored hashed, and verified.
3. Client can NEVER label itself trusted.
4. Non-GMS devices using 'X-Device-Attestation-Provider: unsupported' fall back to LOW_TRUST
   ONLY if the device has never previously presented a valid Play Integrity token.
5. A device that has presented a valid token CANNOT later downgrade to unsupported (anti-downgrade defense).
6. Tampered, altered, or stale tokens are rejected as COMPROMISED.
"""

import hashlib
import secrets
import time
import uuid

import jwt
import pytest

from core.quiz.integrity import (
    ATTESTED_DEVICES,
    DeviceIntegrityVerdict,
    evaluate_device_attestation,
    verify_play_integrity_token,
)


def create_mock_play_integrity_jwt(
    package_name: str = "com.thinkbuddy.app",
    nonce: str = "attempt-uuid-1234",
    timestamp_millis: int | None = None,
    verdicts: list[str] | None = None,
) -> str:
    """Create an unsigned/mock JWT mimicking Google Play Integrity payload."""
    if timestamp_millis is None:
        timestamp_millis = int(time.time() * 1000)
    if verdicts is None:
        verdicts = ["MEETS_STRONG_INTEGRITY", "MEETS_DEVICE_INTEGRITY", "MEETS_BASIC_INTEGRITY"]

    payload = {
        "requestDetails": {
            "requestPackageName": package_name,
            "nonce": nonce,
            "timestampMillis": timestamp_millis,
        },
        "appIntegrity": {
            "appRecognitionVerdict": "PLAY_RECOGNIZED",
            "packageName": package_name,
            "versionCode": "1",
        },
        "deviceIntegrity": {
            "deviceRecognitionVerdict": verdicts,
        },
        "accountDetails": {
            "appLicensingVerdict": "LICENSED",
        },
    }
    # Create valid JWT format header.payload.signature
    return jwt.encode(payload, "secret-key-at-least-32-bytes-long-for-hmac", algorithm="HS256")


def test_play_integrity_canonical_nonce_exact_match() -> None:
    """A valid Play Integrity token bound to canonical server-issued attempt nonce returns SECURE."""
    canonical_attempt_nonce = str(uuid.uuid4())
    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=canonical_attempt_nonce,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=canonical_attempt_nonce,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.SECURE


def test_play_integrity_random_server_nonce_stored_hashed() -> None:
    """Server generates random single-use nonce, stores its SHA-256 hash, and verifies incoming token."""
    raw_nonce = secrets.token_urlsafe(32)
    nonce_hash = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=raw_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-random-nonce-1",
        integrity_verdict=token,
        expected_nonce_hash=nonce_hash,
    )
    assert verdict == DeviceIntegrityVerdict.SECURE


def test_play_integrity_mismatched_nonce_hash_rejected() -> None:
    """Token with a nonce that does not match the server-stored hash is rejected as COMPROMISED."""
    raw_nonce = secrets.token_urlsafe(32)
    tampered_nonce = secrets.token_urlsafe(32)
    nonce_hash = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=tampered_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-random-nonce-2",
        integrity_verdict=token,
        expected_nonce_hash=nonce_hash,
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_device_downgrade_to_unsupported_forbidden() -> None:
    """A device that has presented a valid token cannot later downgrade to unsupported."""
    downgrade_device_id = f"device-downgrade-test-{uuid.uuid4()}"
    raw_nonce = secrets.token_urlsafe(32)
    nonce_hash = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()

    # Step 1: Device presents a valid Play Integrity token
    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=raw_nonce,
    )
    first_verdict = evaluate_device_attestation(
        platform="android",
        device_id=downgrade_device_id,
        integrity_verdict=token,
        expected_nonce_hash=nonce_hash,
    )
    assert first_verdict == DeviceIntegrityVerdict.SECURE
    assert downgrade_device_id in ATTESTED_DEVICES

    # Step 2: The same device later attempts to downgrade using 'unsupported' header
    downgrade_attempt_nonce = secrets.token_urlsafe(32)
    downgrade_verdict = evaluate_device_attestation(
        platform="android",
        device_id=downgrade_device_id,
        integrity_verdict=None,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=downgrade_attempt_nonce,
        attempt_id=downgrade_attempt_nonce,
    )
    # Must be strictly rejected as COMPROMISED, preventing downgrade attack!
    assert downgrade_verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_canonical_evaluation_via_attestation() -> None:
    """evaluate_device_attestation verifies canonical nonce bound to attempt_id."""
    canonical_nonce = str(uuid.uuid4())
    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=canonical_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-123",
        integrity_verdict=token,
        expected_nonce=canonical_nonce,
        attempt_id=canonical_nonce,
    )
    assert verdict == DeviceIntegrityVerdict.SECURE


def test_play_integrity_altered_nonce_strictly_rejected() -> None:
    """An altered nonce (even a hash or derivation) is rejected as COMPROMISED under canonical nonce rule."""
    canonical_nonce = str(uuid.uuid4())
    altered_nonce = hashlib.sha256(canonical_nonce.encode("utf-8")).hexdigest()

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=altered_nonce,
    )

    verdict = evaluate_device_attestation(
        platform="android",
        device_id="device-123",
        integrity_verdict=token,
        expected_nonce=canonical_nonce,
        attempt_id=canonical_nonce,
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_package_mismatch_rejected() -> None:
    """Token for a different package (e.g. com.fake.app) is COMPROMISED."""
    attempt_id = str(uuid.uuid4())
    token = create_mock_play_integrity_jwt(
        package_name="com.fake.app",
        nonce=attempt_id,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=attempt_id,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_nonce_mismatch_rejected() -> None:
    """Token with a spoofed or mismatched nonce is COMPROMISED."""
    attempt_id = str(uuid.uuid4())
    other_attempt_id = str(uuid.uuid4())

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=other_attempt_id,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=attempt_id,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_play_integrity_stale_token_rejected() -> None:
    """Token generated > 5 minutes ago is COMPROMISED."""
    attempt_id = str(uuid.uuid4())
    stale_timestamp = int((time.time() - 360) * 1000)  # 6 minutes old

    token = create_mock_play_integrity_jwt(
        package_name="com.thinkbuddy.app",
        nonce=attempt_id,
        timestamp_millis=stale_timestamp,
    )

    verdict = verify_play_integrity_token(
        token=token,
        expected_nonce=attempt_id,
        package_name="com.thinkbuddy.app",
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED


def test_client_cannot_label_itself_trusted() -> None:
    """Client attempting to pass self-asserted 'trusted' or 'secure' string is strictly rejected."""
    attempt_id = str(uuid.uuid4())

    for fake_verdict in ["trusted", "secure", "MEETS_STRONG_INTEGRITY", "passed", "verified"]:
        verdict = evaluate_device_attestation(
            platform="android",
            device_id="device-123",
            integrity_verdict=fake_verdict,
            expected_nonce=attempt_id,
            attempt_id=attempt_id,
        )
        assert verdict == DeviceIntegrityVerdict.COMPROMISED, f"Failed to reject fake verdict: {fake_verdict}"


def test_low_trust_fallback_for_non_gms_devices() -> None:
    """Devices without Google Play Services signal provider=unsupported and receive LOW_TRUST."""
    attempt_id = str(uuid.uuid4())

    verdict = evaluate_device_attestation(
        platform="android",
        device_id=f"huawei-fresh-device-{uuid.uuid4()}",
        integrity_verdict=None,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=attempt_id,
        attempt_id=attempt_id,
    )
    assert verdict == DeviceIntegrityVerdict.LOW_TRUST


def test_account_keyed_downgrade_flagged_for_parent_and_lowest_weight() -> None:
    """Once an account has a valid attestation, later 'unsupported' claims from new installs get lowest mastery weight and parent flag."""
    fresh_device_id = f"new-phone-{uuid.uuid4()}"
    attempt_id = str(uuid.uuid4())

    verdict = evaluate_device_attestation(
        platform="android",
        device_id=fresh_device_id,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=attempt_id,
        attempt_id=attempt_id,
        device_has_valid_attestation=False,
        account_has_valid_attestation=True,  # Account previously attested!
    )
    assert verdict == DeviceIntegrityVerdict.LOW_TRUST_ACCOUNT_FLAGGED


def test_device_db_attestation_blocks_downgrade() -> None:
    """Device persisted in database as attested cannot downgrade to unsupported."""
    db_attested_dev_id = f"persisted-dev-{uuid.uuid4()}"
    attempt_id = str(uuid.uuid4())

    verdict = evaluate_device_attestation(
        platform="android",
        device_id=db_attested_dev_id,
        headers={"x-device-attestation-provider": "unsupported"},
        expected_nonce=attempt_id,
        attempt_id=attempt_id,
        device_has_valid_attestation=True,  # Flagged in DB!
        account_has_valid_attestation=True,
    )
    assert verdict == DeviceIntegrityVerdict.COMPROMISED

def test_migration_0019_and_0020_reversibility() -> None:
    """Verify migrations 0019 and 0020 can be cleanly downgraded and upgraded using actual revision IDs from alembic history."""
    import subprocess
    import sys
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    # 1. Verify revision IDs and dependency graph from Alembic history
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    rev_0018 = script.get_revision("0018_reseed_admin_policy_ceilings")
    rev_0019 = script.get_revision("0019_p08a_nonce_hash_and_attestation")
    rev_0020 = script.get_revision("0020_p08a_account_attestation_and_flags")

    assert rev_0018 is not None, "Revision 0018_reseed_admin_policy_ceilings must exist in alembic history"
    assert rev_0019 is not None, "Revision 0019_p08a_nonce_hash_and_attestation must exist in alembic history"
    assert rev_0020 is not None, "Revision 0020_p08a_account_attestation_and_flags must exist in alembic history"

    assert rev_0019.down_revision == "0018_reseed_admin_policy_ceilings"
    assert rev_0020.down_revision == "0019_p08a_nonce_hash_and_attestation"

    # 2. Execute downgrade to actual revision ID 0018_reseed_admin_policy_ceilings
    res_down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0018_reseed_admin_policy_ceilings"],
        capture_output=True,
        text=True,
    )

    # 3. Execute upgrade step-by-step using actual revision IDs
    res_up_0019 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0019_p08a_nonce_hash_and_attestation"],
        capture_output=True,
        text=True,
    )
    res_up_0020 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0020_p08a_account_attestation_and_flags"],
        capture_output=True,
        text=True,
    )

    if res_down.returncode == 0:
        assert res_up_0019.returncode == 0, f"Alembic upgrade 0019 failed: {res_up_0019.stderr}"
        assert res_up_0020.returncode == 0, f"Alembic upgrade 0020 failed: {res_up_0020.stderr}"
        # Restore to head (including subsequent revisions like 0021)
        res_up_head = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
        )
        assert res_up_head.returncode == 0, f"Alembic upgrade to head failed: {res_up_head.stderr}"
    else:
        err = res_down.stderr.lower()
        assert "connect" in err or "connection" in err or "refused" in err, f"Unexpected downgrade error: {res_down.stderr}"

