"""API routes for auth module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/auth", tags=["auth"])


@router.get("/status")
async def auth_status() -> dict[str, str]:
    return {"module": "auth", "status": "active"}
