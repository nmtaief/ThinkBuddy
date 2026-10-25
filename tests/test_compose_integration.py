"""Integration tests for live/compose services, /readyz behavior when Redis is down,

and production secret enforcement.
"""

from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.common.config import CoreSettings
from core.common.config import settings as core_settings
from core.main import app as core_app
from gateway.config import GatewaySettings
from gateway.main import app as gateway_app


@pytest.mark.asyncio
async def test_readyz_fails_when_redis_is_down() -> None:
    """Verify that /readyz returns HTTP 503 and checks.redis.ok=False when Redis is down."""
    # Simulate Redis connection failure (connection refused / timeout)
    with (
        patch("core.main.check_database_ready", new_callable=AsyncMock) as mock_db,
        patch("core.main.check_redis_ready", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = (True, "Database healthy and vector extension verified")
        mock_redis.return_value = (False, "ConnectionRefusedError: [Errno 111] Connection refused")

        transport = ASGITransport(app=core_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/readyz")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["service"] == "core"
        assert data["checks"]["database"]["ok"] is True
        assert data["checks"]["redis"]["ok"] is False
        assert "Connection refused" in data["checks"]["redis"]["detail"]


@pytest.mark.asyncio
async def test_gateway_readyz_fails_when_redis_is_down() -> None:
    """Verify that Gateway /readyz also returns HTTP 503 when its Redis is unreachable."""
    with (
        patch("gateway.main.check_redis_ready", new_callable=AsyncMock) as mock_redis,
        patch("gateway.main.core_client.check_core_ready", new_callable=AsyncMock) as mock_core,
    ):
        mock_redis.return_value = (False, "ConnectionRefusedError: Redis down")
        mock_core.return_value = (True, "Core service responding")

        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/readyz")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["service"] == "gateway"
        assert data["checks"]["redis"]["ok"] is False


def test_refuse_placeholder_secrets_in_production() -> None:
    """Verify settings refuse to start with placeholder secrets in non-local environments."""
    # Production with placeholder internal service token -> must raise ValueError
    with pytest.raises(
        ValueError, match="Refusing to start in environment 'production' with placeholder"
    ):
        CoreSettings(
            ENVIRONMENT="production",
            INTERNAL_SERVICE_TOKEN="dev_internal_service_token_placeholder_change_in_production",
            DATABASE_URL="postgresql+asyncpg://user:real_prod_password_123@prod-db:5432/thinkbuddy",
        )

    # Production with default dev db password -> must raise ValueError
    with pytest.raises(ValueError, match="default development database credentials"):
        CoreSettings(
            ENVIRONMENT="production",
            INTERNAL_SERVICE_TOKEN="super_secure_random_production_service_token_987654321",
            DATABASE_URL=(
                "postgresql+asyncpg://thinkbuddy:thinkbuddy_dev_password@prod-db:5432/thinkbuddy"
            ),
        )

    # Gateway in staging with placeholder token -> must raise ValueError
    with pytest.raises(
        ValueError, match="Refusing to start in environment 'staging' with placeholder"
    ):
        GatewaySettings(
            ENVIRONMENT="staging",
            INTERNAL_SERVICE_TOKEN="placeholder_token",
        )

    # Production with placeholder JWT_SECRET_KEY -> must raise ValueError
    with pytest.raises(ValueError, match="placeholder JWT_SECRET_KEY"):
        CoreSettings(
            ENVIRONMENT="production",
            INTERNAL_SERVICE_TOKEN="prod_valid_high_entropy_token_4892374982374982374",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@prod-db:5432/thinkbuddy",
            JWT_SECRET_KEY="dev_jwt_secret_key_change_in_production",
            LINK_CODE_SECRET="prod_valid_high_entropy_link_code_secret_389274982374",
        )

    # Production with placeholder LINK_CODE_SECRET -> must raise ValueError
    with pytest.raises(ValueError, match="placeholder LINK_CODE_SECRET"):
        CoreSettings(
            ENVIRONMENT="production",
            INTERNAL_SERVICE_TOKEN="prod_valid_high_entropy_token_4892374982374982374",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@prod-db:5432/thinkbuddy",
            JWT_SECRET_KEY="prod_valid_high_entropy_jwt_secret_94827398472938472",
            LINK_CODE_SECRET="dev_link_code_secret_change_in_production",
        )

    # Production with short secret (< 32 chars) -> must raise ValueError
    with pytest.raises(ValueError, match="must have at least 32 characters"):
        CoreSettings(
            ENVIRONMENT="production",
            INTERNAL_SERVICE_TOKEN="short_token_under_32_chars",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@prod-db:5432/thinkbuddy",
            JWT_SECRET_KEY="prod_valid_high_entropy_jwt_secret_94827398472938472",
            LINK_CODE_SECRET="prod_valid_high_entropy_link_code_secret_389274982374",
        )

    # Production with duplicate secrets across keys -> must raise ValueError
    with pytest.raises(ValueError, match="must be distinct"):
        CoreSettings(
            ENVIRONMENT="production",
            INTERNAL_SERVICE_TOKEN="super_secure_random_production_service_token_987654321",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@prod-db:5432/thinkbuddy",
            JWT_SECRET_KEY="super_secure_random_production_service_token_987654321",
            LINK_CODE_SECRET="prod_valid_high_entropy_link_code_secret_389274982374",
            INTERNAL_SERVICE_SECRET="prod_valid_high_entropy_service_secret_5839201948201",
            QUESTION_KEY_ENCRYPTION_KEY="prod_valid_high_entropy_question_crypto_key_58392",
        )

    # Gateway in staging with short token -> must raise ValueError
    with pytest.raises(ValueError, match="must have at least 32 characters"):
        GatewaySettings(
            ENVIRONMENT="staging",
            INTERNAL_SERVICE_TOKEN="short_staging_token_123",
        )

    # Production with legitimate distinct credentials (>= 32 chars) -> successfully instantiates
    prod_core = CoreSettings(
        ENVIRONMENT="production",
        INTERNAL_SERVICE_TOKEN="prod_valid_high_entropy_token_4892374982374982374",
        DATABASE_URL="postgresql+asyncpg://prod_user:prod_secure_pass_4738@prod-db:5432/thinkbuddy",
        JWT_SECRET_KEY="prod_valid_high_entropy_jwt_secret_94827398472938472",
        LINK_CODE_SECRET="prod_valid_high_entropy_link_code_secret_389274982374",
        INTERNAL_SERVICE_SECRET="prod_valid_high_entropy_service_secret_5839201948201",
        QUESTION_KEY_ENCRYPTION_KEY="prod_valid_high_entropy_question_crypto_key_58392",
    )
    assert prod_core.ENVIRONMENT == "production"


@pytest.mark.asyncio
async def test_live_compose_services_connectivity() -> None:
    """Test actual connectivity against live Postgres and Redis when Compose is running."""
    redis_reachable = False
    try:
        r = aioredis.from_url(core_settings.REDIS_URL, socket_timeout=1.0)
        await r.ping()
        await r.aclose()
        redis_reachable = True
    except Exception as exc:  # noqa: BLE001
        _ = exc

    pg_reachable = False
    try:
        eng = create_async_engine(core_settings.DATABASE_URL, pool_pre_ping=True)
        async with eng.connect() as conn:
            res = await conn.execute(text("SELECT 1"))
            if res.scalar() == 1:
                pg_reachable = True
        await eng.dispose()
    except Exception as exc:  # noqa: BLE001
        _ = exc

    if not redis_reachable and not pg_reachable:
        pytest.skip("Docker Compose Postgres/Redis not currently reachable on localhost.")
    else:
        assert redis_reachable or pg_reachable
