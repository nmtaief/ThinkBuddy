"""API routes for questions module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/questions", tags=["questions"])
