"""API routes for chat module."""

from fastapi import APIRouter

router = APIRouter(prefix="/internal/chat", tags=["chat"])
