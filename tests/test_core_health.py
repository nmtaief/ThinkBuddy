"""Unit and integration tests for ThinkBuddy Core healthz, readyz, and internal security."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_core_healthz(core_client: AsyncClient) -> None:
    """Test core liveness probe endpoint."""
    response = await core_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "core"
    assert "X-Request-Id" in response.headers


@pytest.mark.asyncio
async def test_core_readyz_healthy(core_client: AsyncClient) -> None:
    """Test core readiness probe when dependencies are healthy."""
    with (
        patch("core.main.check_database_ready", new_callable=AsyncMock) as mock_db,
        patch("core.main.check_redis_ready", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = (True, "Database healthy and vector extension verified")
        mock_redis.return_value = (True, "Redis healthy")

        response = await core_client.get("/readyz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"]["ok"] is True
        assert data["checks"]["redis"]["ok"] is True


@pytest.mark.asyncio
async def test_core_readyz_unhealthy_db(core_client: AsyncClient) -> None:
    """Test core readiness probe returns 503 when database is down."""
    with (
        patch("core.main.check_database_ready", new_callable=AsyncMock) as mock_db,
        patch("core.main.check_redis_ready", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = (False, "Connection refused")
        mock_redis.return_value = (True, "Redis healthy")

        response = await core_client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["ok"] is False


@pytest.mark.asyncio
async def test_core_internal_service_token_auth(core_client: AsyncClient) -> None:
    """Verify internal routes enforce internal service token."""
    # 1. No token provided
    res_no_token = await core_client.get("/internal/auth/status")
    assert res_no_token.status_code in (403, 422)

    # 2. Invalid token provided
    res_bad_token = await core_client.get(
        "/internal/auth/status",
        headers={"X-Internal-Service-Token": "invalid_wrong_token"},
    )
    assert res_bad_token.status_code == 403

    # 3. Valid token provided
    res_valid = await core_client.get(
        "/internal/auth/status",
        headers={"X-Internal-Service-Token": "test_internal_service_token_12345"},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["module"] == "auth"


@pytest.mark.asyncio
async def test_request_id_header_propagation(core_client: AsyncClient) -> None:
    """Test that incoming X-Request-Id is respected and propagated."""
    custom_id = "test-custom-request-id-999"
    response = await core_client.get("/healthz", headers={"X-Request-Id": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == custom_id
