"""API routes for audit module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/audit", tags=["audit"])
