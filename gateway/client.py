"""Internal HTTP client for Gateway-to-Core communication."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.common.logging import request_id_ctx
from gateway.config import settings

logger = logging.getLogger(__name__)


class CoreServiceClient:
    """HTTP client communicating with Core backend over internal network with service token."""

    def __init__(
        self,
        base_url: str = settings.CORE_INTERNAL_URL,
        service_token: str = settings.INTERNAL_SERVICE_TOKEN,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.transport = transport

    def _get_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "X-Internal-Service-Token": self.service_token,
            "X-Request-Id": request_id_ctx.get() or "",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def check_core_ready(self) -> tuple[bool, str]:
        """Check if Core backend is alive and responding to health check."""
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/healthz")
                if res.status_code == 200:
                    return True, "Core service responding"
                return False, f"Core returned HTTP {res.status_code}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Core readiness probe failed: %s", exc)
            return False, f"Core unreachable: {exc}"

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Forward an internal request to Core."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        merged_headers = self._get_headers(headers)
        async with httpx.AsyncClient(transport=self.transport, timeout=10.0) as client:
            return await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=merged_headers,
            )

    async def stream_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], AsyncIterator[bytes]]:
        """Stream an internal request from Core without buffering tokens."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        merged_headers = self._get_headers(headers)
        client = httpx.AsyncClient(transport=self.transport, timeout=60.0)
        req = client.build_request(
            method=method,
            url=url,
            params=params,
            json=json_data,
            headers=merged_headers,
        )
        resp = await client.send(req, stream=True)

        async def body_stream() -> AsyncIterator[bytes]:
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return resp.status_code, dict(resp.headers), body_stream()


core_client = CoreServiceClient()
