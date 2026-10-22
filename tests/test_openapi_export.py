"""Tests for OpenAPI schema export verification."""

import json
from pathlib import Path

from scripts.export_openapi import export_openapi


def test_openapi_export_generation() -> None:
    """Verify that export_openapi creates a valid JSON artifact."""
    export_openapi()

    artifact_path = Path("docs-generated/openapi.json")
    assert artifact_path.exists()

    content = artifact_path.read_text(encoding="utf-8")
    schema = json.loads(content)

    assert "openapi" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "ThinkBuddy API Gateway"
    assert "/healthz" in schema["paths"]
    assert "/readyz" in schema["paths"]
    assert "/v1/client/config" in schema["paths"]
