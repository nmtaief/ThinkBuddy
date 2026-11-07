"""Unit tests for server-side timing and database query count instrumentation."""

from __future__ import annotations

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

