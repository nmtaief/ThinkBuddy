"""API routes for reviews module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/reviews", tags=["reviews"])
