"""API routes for admin module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/admin", tags=["admin"])
