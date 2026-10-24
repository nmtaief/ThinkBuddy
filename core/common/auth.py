"""Internal service authentication for gateway-to-core communication."""

import hmac

from fastapi import Header, HTTPException, status

from core.common.config import settings
from core.common.service_token import verify_internal_service_token as verify_jwt_service_token


async def verify_internal_service_token(
    x_internal_service_token: str = Header(..., alias="X-Internal-Service-Token"),
) -> str:
    """Verify that incoming internal request comes from an authorized service.

    Supports signed JWT service tokens (HS256) and fallback static service tokens.
    """
    # 1. If JWT format (header.payload.signature), verify cryptographic claims
    if "." in x_internal_service_token:
        verify_jwt_service_token(x_internal_service_token)
        return x_internal_service_token

    # 2. Fallback static token comparison using constant-time check
    if hmac.compare_digest(
        x_internal_service_token.encode("utf-8"),
        settings.INTERNAL_SERVICE_TOKEN.encode("utf-8"),
    ):
        return x_internal_service_token

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": "FORBIDDEN_INTERNAL_ACCESS",
                "message": "Invalid or missing internal service token",
            }
        },
    )
