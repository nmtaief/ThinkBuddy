"""API routes for devices module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/devices", tags=["devices"])
