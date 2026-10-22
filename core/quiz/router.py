"""API routes for quiz module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/quiz", tags=["quiz"])
