"""Tests for structured JSON logging and sensitive data masking."""

import json
import logging

from core.common.logging import JSONFormatter, mask_sensitive_data


def test_mask_sensitive_data_keys() -> None:
    """Verify that credentials, tokens, OTPs, and answer keys are masked."""
    sample = {
        "user_id": 123,
        "password": "secret_password",
        "access_token": "jwt.secret.token",
        "otp": "123456",
        "answer_key": {"q1": "A", "q2": "B"},
        "nested": {
            "token": "inner_token",
            "safe_field": "visible",
        },
    }

    masked = mask_sensitive_data(sample)
    assert masked["user_id"] == 123
    assert masked["password"] == "***MASKED***"
    assert masked["access_token"] == "***MASKED***"
    assert masked["otp"] == "***MASKED***"
    assert masked["answer_key"] == "***MASKED***"
    assert masked["nested"]["token"] == "***MASKED***"
    assert masked["nested"]["safe_field"] == "visible"


def test_json_formatter_output() -> None:
    """Verify JSONFormatter creates valid structured JSON with request correlation."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test event logged",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-12345"

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test event logged"
    assert parsed["request_id"] == "req-12345"
