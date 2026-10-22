"""API routes for entitlements module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/entitlements", tags=["entitlements"])
