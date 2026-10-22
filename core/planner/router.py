"""API routes for planner module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/planner", tags=["planner"])
