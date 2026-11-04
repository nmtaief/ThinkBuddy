"""Test real client IP propagation and rate limit isolation for web BFF proxy (P08 Follow-up).

Verifies that:
1. Trusted proxies are strictly restricted to the web container dedicated address/network and gateway (no hostnames, no whole private ranges).
2. Forwarded IPs are parsed from the right (stepping back through trusted proxies).
3. Browser-supplied X-Forwarded-For headers from untrusted peers are strictly ignored.
4. In the Compose stack, different client IPs hit different rate-limit keys.
"""

from unittest.mock import MagicMock
import pytest
from httpx import AsyncClient

from core.common.config import settings
from gateway.config import settings as gw_settings
from core.common.rate_limit import RateLimiter, build_rate_limit_key, get_trusted_client_ip, is_peer_trusted_proxy


def make_mock_request(peer_ip: str, headers: dict[str, str]) -> MagicMock:
    req = MagicMock()
    req.client.host = peer_ip
    req.headers = {k.lower(): v for k, v in headers.items()}
    return req


def test_trusted_proxy_configuration_restricted() -> None:
    """Ensure trusted proxies only contain explicit fixed addresses/dedicated network, with no hostnames or whole private ranges."""
    # Core trusts strictly the Gateway's specific fixed IP or loopback
    assert "172.29.0.2" in settings.TRUSTED_PROXIES
    assert "127.0.0.1" in settings.TRUSTED_PROXIES
    assert "web" not in settings.TRUSTED_PROXIES
    assert "gateway" not in settings.TRUSTED_PROXIES

    # Gateway trusts strictly the Web container's fixed IP and dedicated edge network
    assert "172.28.0.3" in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "172.28.0.0/29" in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "127.0.0.1" in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "web" not in gw_settings.GATEWAY_TRUSTED_PROXIES

    # Whole private ranges MUST NOT be trusted
    assert "10.0.0.0/8" not in settings.TRUSTED_PROXIES
    assert "172.16.0.0/12" not in settings.TRUSTED_PROXIES
    assert "192.168.0.0/16" not in settings.TRUSTED_PROXIES
    assert "10.0.0.0/8" not in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "172.16.0.0/12" not in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "192.168.0.0/16" not in gw_settings.GATEWAY_TRUSTED_PROXIES

    # Arbitrary private network addresses not in the list are untrusted
    assert not is_peer_trusted_proxy("10.10.10.10")
    assert not is_peer_trusted_proxy("172.25.0.4")
    assert not is_peer_trusted_proxy("192.168.1.50")
    assert not is_peer_trusted_proxy("web")


def test_browser_supplied_x_forwarded_for_is_ignored() -> None:
    """A browser-supplied X-Forwarded-For or X-Real-IP from an untrusted peer MUST be ignored."""
    # Direct browser client connecting to gateway
    req_browser = make_mock_request(
        peer_ip="198.51.100.77",
        headers={
            "x-forwarded-for": "8.8.8.8, 1.1.1.1",
            "x-real-ip": "9.9.9.9",
        },
    )
    # Must return direct peer host, ignoring spoofed headers
    assert get_trusted_client_ip(req_browser) == "198.51.100.77"


def test_forwarded_ips_parsed_from_the_right() -> None:
    """When request arrives from trusted proxy, X-Forwarded-For is parsed from the right."""
    # Case 1: Browser client (203.0.113.55) connects to Web BFF (fixed IP '172.28.0.3'),
    # and browser attempted to spoof X-Forwarded-For: 100.100.100.100.
    # The chain forwarded by Web container is "100.100.100.100, 203.0.113.55".
    req_spoof_attempt = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "100.100.100.100, 203.0.113.55"},
    )
    # Parsing from the right extracts the actual client IP (203.0.113.55), ignoring the spoofed 100.100.100.100
    assert get_trusted_client_ip(req_spoof_attempt) == "203.0.113.55"

    # Case 2: Chain containing an intermediate trusted proxy (127.0.0.1)
    req_multi_proxy = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "1.2.3.4, 203.0.113.99, 127.0.0.1"},
    )
    # Steps over trusted 127.0.0.1 from the right, finding 203.0.113.99, ignoring 1.2.3.4
    assert get_trusted_client_ip(req_multi_proxy) == "203.0.113.99"


def test_compose_stack_different_client_ips_hit_different_rate_limit_keys() -> None:
    """In the Compose stack, different client IPs routed through the web container hit different rate-limit keys."""
    # User 1 and User 2 routed through the dedicated web container fixed IP
    req_user1 = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "203.0.113.10, 172.28.0.3"},
    )
    req_user2 = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "198.51.100.20, 172.28.0.3"},
    )

    ip1 = get_trusted_client_ip(req_user1)
    ip2 = get_trusted_client_ip(req_user2)

    assert ip1 == "203.0.113.10"
    assert ip2 == "198.51.100.20"

    key1 = build_rate_limit_key("auth_exchange", ip1, "user_1")
    key2 = build_rate_limit_key("auth_exchange", ip2, "user_2")

    assert key1 == "rl:auth_exchange:203.0.113.10:user_1"
    assert key2 == "rl:auth_exchange:198.51.100.20:user_2"
    assert key1 != key2


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
        "X-Client-Form-Factor": "desktop",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "web_dev_user_a",
        "Accept-Language": "bn",
        "X-Real-IP": user_a_ip,
        "X-Forwarded-For": f"{user_a_ip}, 127.0.0.1",
    }

    headers_user_b = {
        "X-Client-Platform": "web",
        "X-Client-Form-Factor": "desktop",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "web_dev_user_b",
        "Accept-Language": "bn",
        "X-Real-IP": user_b_ip,
        "X-Forwarded-For": f"{user_b_ip}, 127.0.0.1",
    }

    from unittest.mock import AsyncMock, patch
    import httpx

    mock_core_response = httpx.Response(
        200,
        json={"access_token": "mock_token", "refresh_token": "mock_rt", "token_type": "bearer", "expires_in": 3600},
    )

    with patch("gateway.router.core_client.request", new_callable=AsyncMock, return_value=mock_core_response):
        # Simulate 10 exchange attempts for User A (rate limit ceiling is 10/min)
        for _ in range(10):
            res = await gateway_client.post(
                "/v1/auth/exchange",
                json={"provider_token": "fake:phone:+8801711111111", "role": "parent"},
                headers=headers_user_a,
            )
            assert res.status_code == 200

        # 11th attempt for User A must trigger rate limit (429)
        res_a_blocked = await gateway_client.post(
            "/v1/auth/exchange",
            json={"provider_token": "fake:phone:+8801711111111", "role": "parent"},
            headers=headers_user_a,
        )
        assert res_a_blocked.status_code == 429
        assert res_a_blocked.json()["error"]["code"] in ("RATE_LIMIT_EXCEEDED", "LOCKED_OUT")

        # User B arrives from the SAME web server, but with their own IP
        # User B must NOT be blocked by User A's lockout!
        res_b = await gateway_client.post(
            "/v1/auth/exchange",
            json={"provider_token": "fake:phone:+8801722222222", "role": "parent"},
            headers=headers_user_b,
        )
        assert res_b.status_code == 200
