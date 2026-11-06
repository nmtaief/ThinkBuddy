"""Pytest configuration and test fixtures."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set testing environment variables before application imports
os.environ["ENV"] = "local"
os.environ["ENVIRONMENT"] = "local"
os.environ["INTERNAL_SERVICE_TOKEN"] = "test_internal_service_token_12345"

from collections.abc import AsyncGenerator

import gateway.client
from core.common.rate_limit import RateLimiter
from core.main import app as core_app
from gateway.main import app as gateway_app


@pytest.fixture(autouse=True)
async def wire_gateway_and_reset_rate_limits() -> AsyncGenerator[None, None]:
    """Wire gateway internal client directly to in-process core ASGI app and clear rate limits."""
    from core.common.database import engine

    original_transport = gateway.client.core_client.transport
    original_url = gateway.client.core_client.base_url

    core_app.dependency_overrides.clear()
    gateway_app.dependency_overrides.clear()
    gateway.client.core_client.transport = ASGITransport(app=core_app)
    gateway.client.core_client.base_url = "http://testserver"
    await RateLimiter.reset()

    yield

    core_app.dependency_overrides.clear()
    gateway_app.dependency_overrides.clear()
    gateway.client.core_client.transport = original_transport
    gateway.client.core_client.base_url = original_url
    await RateLimiter.reset()
    await engine.dispose()
    from core.common.redis import close_redis
    await close_redis()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def core_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client for ThinkBuddy Core."""
    transport = ASGITransport(app=core_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def gateway_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client for ThinkBuddy Gateway."""
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
