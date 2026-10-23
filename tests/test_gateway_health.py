"""Unit and integration tests for ThinkBuddy Gateway healthz, readyz, and client config."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_gateway_healthz(gateway_client: AsyncClient) -> None:
    """Test gateway liveness probe endpoint."""
    response = await gateway_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "gateway"
    assert "X-Request-Id" in response.headers


@pytest.mark.asyncio
async def test_gateway_readyz_healthy(gateway_client: AsyncClient) -> None:
    """Test gateway readiness probe when Redis and Core are healthy."""
    with (
        patch("gateway.main.check_redis_ready", new_callable=AsyncMock) as mock_redis,
        patch("gateway.main.core_client.check_core_ready", new_callable=AsyncMock) as mock_core,
    ):
        mock_redis.return_value = (True, "Redis healthy")
        mock_core.return_value = (True, "Core service responding")

        response = await gateway_client.get("/readyz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["redis"]["ok"] is True
        assert data["checks"]["core"]["ok"] is True


@pytest.mark.asyncio
async def test_gateway_readyz_core_down(gateway_client: AsyncClient) -> None:
    """Test gateway readiness probe returns 503 when Core is unreachable."""
    with (
        patch("gateway.main.check_redis_ready", new_callable=AsyncMock) as mock_redis,
        patch("gateway.main.core_client.check_core_ready", new_callable=AsyncMock) as mock_core,
    ):
        mock_redis.return_value = (True, "Redis healthy")
        mock_core.return_value = (False, "Core unreachable")

        response = await gateway_client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["core"]["ok"] is False


@pytest.mark.asyncio
async def test_client_config_android(gateway_client: AsyncClient) -> None:
    """Test dynamic client config for Android mobile client."""
    response = await gateway_client.get(
        "/v1/client/config",
        headers={
            "X-Client-Platform": "android",
            "X-Client-Form-Factor": "phone",
            "X-App-Version": "1.0.0",
            "X-Device-Id": "device-android-123",
            "Accept-Language": "bn",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["min_supported_version"] == "1.0.0"
    assert data["feature_flags"]["teacher_reviews"] is False  # Flagged off for beta
    assert data["quiz_security"]["allowed_mode"] == "secure_kiosk"
    assert data["quiz_security"]["screen_pinning_required"] is True
    assert data["layout_hints"]["image_size_class"] == "md"


@pytest.mark.asyncio
async def test_client_config_web(gateway_client: AsyncClient) -> None:
    """Test dynamic client config for Web client."""
    response = await gateway_client.get(
        "/v1/client/config",
        headers={
            "X-Client-Platform": "web",
            "X-Client-Form-Factor": "desktop",
            "X-App-Version": "1.0.0",
            "X-Device-Id": "device-web-456",
            "Accept-Language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Web client restricted to practice-only per docs/05_SECURE_QUIZ.md
    assert data["quiz_security"]["allowed_mode"] == "practice_only"
    assert data["layout_hints"]["image_size_class"] == "lg"
