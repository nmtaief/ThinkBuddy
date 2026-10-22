"""API routes for progress module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/progress", tags=["progress"])
