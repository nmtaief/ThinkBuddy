"""Consolidated test suite: test_infra_health.py."""
from __future__ import annotations


# ========================================================================
# Consolidated from: tests/test_core_health.py
# ========================================================================

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

# ========================================================================
# Consolidated from: tests/test_gateway_health.py
# ========================================================================

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
    assert data["quiz_security"]["allowed_mode"] == "assessed"
    assert data["quiz_security"]["flag_secure"] is True
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

# ========================================================================
# Consolidated from: tests/test_compose_integration.py
# ========================================================================

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

# ========================================================================
# Consolidated from: tests/test_route_instrumentation.py
# ========================================================================

"""Unit tests for server-side timing and database query count instrumentation."""


import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app


@pytest.mark.asyncio
async def test_server_timing_and_query_count_headers() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Health endpoint (no database queries)
        res = await client.get("/healthz")
        assert res.status_code == 200
        assert "Server-Timing" in res.headers
        assert "X-DB-Query-Count" in res.headers
        assert "X-Server-Time-Ms" in res.headers
        assert res.headers["X-DB-Query-Count"] == "0"
        assert float(res.headers["X-Server-Time-Ms"]) >= 0.0

        # 2. Readyz endpoint (executes at least 1 database query: SELECT 1)
        res_ready = await client.get("/readyz")
        assert res_ready.status_code in (200, 503)
        assert "Server-Timing" in res_ready.headers
        assert "X-DB-Query-Count" in res_ready.headers
        query_count = int(res_ready.headers["X-DB-Query-Count"])
        assert query_count >= 1
        assert float(res_ready.headers["X-DB-Time-Ms"]) >= 0.0


# ========================================================================
# Consolidated from: tests/test_openapi_export.py
# ========================================================================

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

# ========================================================================
# Consolidated from: tests/test_cleanup_idempotency.py
# ========================================================================

"""Unit tests for expired idempotency records cleanup background task."""


import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.models import User
from core.chat.models import ChatIdempotencyRecord, ChatSession
from workers.cleanup_tasks import cleanup_expired_idempotency_records


from core.common.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_cleanup_expired_idempotency_records() -> None:
    async with AsyncSessionLocal() as fastsession:
        now = datetime.now(UTC)

        # Create student and fastsession
        student = User(
            id=uuid.uuid4(),
            auth_provider="phone",
            auth_uid=f"phone_{uuid.uuid4().hex[:8]}",
            role="student",
            display_name="Test Student",
            locale="bn",
            status="active",
        )
        fastsession.add(student)
        await fastsession.flush()

        chat_session = ChatSession(
            id=uuid.uuid4(),
            student_id=student.id,
            is_active=True,
            subject="science",
        )
        fastsession.add(chat_session)
        await fastsession.flush()

        # 1. Active record (expires in 24 hours)
        active_rec = ChatIdempotencyRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            session_id=chat_session.id,
            idempotency_key="key_active_123",
            response_payload={"answer": "hello active"},
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        fastsession.add(active_rec)

        # 2. Expired record (expired 1 hour ago)
        expired_rec1 = ChatIdempotencyRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            session_id=chat_session.id,
            idempotency_key="key_expired_456",
            response_payload={"answer": "hello expired 1"},
            created_at=now - timedelta(days=2),
            expires_at=now - timedelta(hours=1),
        )
        fastsession.add(expired_rec1)

        # 3. Expired record (expired 2 days ago)
        expired_rec2 = ChatIdempotencyRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            session_id=chat_session.id,
            idempotency_key="key_expired_789",
            response_payload={"answer": "hello expired 2"},
            created_at=now - timedelta(days=3),
            expires_at=now - timedelta(days=1),
        )
        fastsession.add(expired_rec2)
        await fastsession.commit()

        # Run cleanup
        purged = await cleanup_expired_idempotency_records(db=fastsession)
        assert purged >= 2

        # Verify active record is still intact
        remaining = await fastsession.execute(
            select(ChatIdempotencyRecord).where(ChatIdempotencyRecord.student_id == student.id)
        )
        records = remaining.scalars().all()
        assert len(records) == 1
        assert records[0].idempotency_key == "key_active_123"

