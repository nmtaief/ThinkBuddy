"""API routes for revision module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/revision", tags=["revision"])
