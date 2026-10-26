"""Test real client IP propagation and rate limit isolation for web BFF proxy (P08 Task 2).

Verifies that:
1. Web server container hosts ('web', 'thinkbuddy-web') and local proxies are recognized as trusted proxies.
2. The gateway/core extracts the origin client IP from X-Forwarded-For when forwarded by trusted proxies.
3. Untrusted peers cannot spoof X-Forwarded-For.
4. Per-IP rate limits apply per individual user IP, not collectively against the web server IP.
"""

from unittest.mock import MagicMock
import pytest
from httpx import AsyncClient

from core.common.config import settings
from core.common.rate_limit import RateLimiter, build_rate_limit_key, get_trusted_client_ip


def make_mock_request(peer_ip: str, headers: dict[str, str]) -> MagicMock:
    req = MagicMock()
    req.client.host = peer_ip
    req.headers = {k.lower(): v for k, v in headers.items()}
    return req


def test_trusted_proxy_configuration() -> None:
    """Ensure web and thinkbuddy-web container hosts are in TRUSTED_PROXIES."""
    assert "web" in settings.TRUSTED_PROXIES
    assert "thinkbuddy-web" in settings.TRUSTED_PROXIES
    assert "127.0.0.1" in settings.TRUSTED_PROXIES
    assert "gateway" in settings.TRUSTED_PROXIES


def test_trusted_client_ip_extraction_from_web_proxy() -> None:
    """When request arrives from trusted web container, real client IP is parsed from X-Forwarded-For."""
    # Simulating request from Next.js BFF container 'web'
    req_web = make_mock_request(
        peer_ip="web",
        headers={"x-forwarded-for": "203.0.113.55, 10.0.0.1", "x-real-ip": "203.0.113.55"},
    )
    assert get_trusted_client_ip(req_web) == "203.0.113.55"

    # Simulating request from docker network IP 172.18.0.4
    req_docker = make_mock_request(
        peer_ip="172.18.0.4",
        headers={"x-forwarded-for": "198.51.100.99"},
    )
    assert get_trusted_client_ip(req_docker) == "198.51.100.99"

    # Untrusted external IP attempting to spoof X-Forwarded-For must be ignored
    req_untrusted = make_mock_request(
        peer_ip="185.220.101.5",
        headers={"x-forwarded-for": "1.1.1.1"},
    )
    assert get_trusted_client_ip(req_untrusted) == "185.220.101.5"


@pytest.mark.asyncio
async def test_per_ip_rate_limits_apply_per_user_not_per_web_server(gateway_client: AsyncClient) -> None:
    """Verify that when requests arrive via the web server proxy, rate limits apply per user IP.

    If User A from IP 203.0.113.10 exceeds rate limits, User B from IP 198.51.100.20
    through the same web server proxy must NOT be rate limited.
    """
    await RateLimiter.reset()

    user_a_ip = "203.0.113.10"
    user_b_ip = "198.51.100.20"

    headers_user_a = {
        "X-Client-Platform": "web",
        "X-Client-Form-Factor": "expanded",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "web_dev_user_a",
        "X-Real-IP": user_a_ip,
        "X-Forwarded-For": f"{user_a_ip}, 127.0.0.1",
    }

    headers_user_b = {
        "X-Client-Platform": "web",
        "X-Client-Form-Factor": "expanded",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "web_dev_user_b",
        "X-Real-IP": user_b_ip,
        "X-Forwarded-For": f"{user_b_ip}, 127.0.0.1",
    }

    # Simulate 5 invalid exchange attempts for User A
    for _ in range(5):
        await gateway_client.post(
            "/v1/auth/exchange",
            json={"auth_provider": "fake", "id_token": "bad_token", "role": "student"},
            headers=headers_user_a,
        )

    # 6th attempt for User A must trigger rate limit lockout (429)
    res_a_blocked = await gateway_client.post(
        "/v1/auth/exchange",
        json={"auth_provider": "fake", "id_token": "bad_token", "role": "student"},
        headers=headers_user_a,
    )
    assert res_a_blocked.status_code == 429
    assert res_a_blocked.json()["error"]["code"] in ("RATE_LIMIT_EXCEEDED", "LOCKED_OUT")

    # User B arrives from the SAME web server, but with their own IP
    # User B must NOT be blocked by User A's lockout!
    res_b = await gateway_client.post(
        "/v1/auth/exchange",
        json={"auth_provider": "fake", "id_token": "bad_token", "role": "student"},
        headers=headers_user_b,
    )
    assert res_b.status_code != 429
