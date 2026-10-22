"""API routes for notifications module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/notifications", tags=["notifications"])
