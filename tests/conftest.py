"""Pytest configuration and test fixtures."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set testing environment variables before application imports
os.environ["ENVIRONMENT"] = "testing"
os.environ["INTERNAL_SERVICE_TOKEN"] = "test_internal_service_token_12345"

from core.main import app as core_app
from gateway.main import app as gateway_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def core_client() -> AsyncClient:
    """Async test client for ThinkBuddy Core."""
    transport = ASGITransport(app=core_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def gateway_client() -> AsyncClient:
    """Async test client for ThinkBuddy Gateway."""
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
