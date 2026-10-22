"""Internal service authentication for gateway-to-core communication."""

import hmac

from fastapi import Header, HTTPException, status

from core.common.config import settings


async def verify_internal_service_token(
    x_internal_service_token: str = Header(..., alias="X-Internal-Service-Token"),
) -> str:
    """Verify that incoming internal request comes from an authorized service (gateway/worker).

    Uses constant-time comparison to prevent timing attacks.
    """
    if not hmac.compare_digest(
        x_internal_service_token.encode("utf-8"),
        settings.INTERNAL_SERVICE_TOKEN.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN_INTERNAL_ACCESS",
                    "message": "Invalid or missing internal service token",
                }
            },
        )
    return x_internal_service_token
