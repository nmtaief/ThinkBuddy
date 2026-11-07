"""Chat module endpoints with Secure Quiz lockout and SSE streaming support.

Per docs/04_API_CONTRACT.md §2, §3 and docs/05_SECURE_QUIZ.md §2:
- Chat lockout during active assessed quiz
- Quota enforcement per student daily limits
- Streaming SSE support when Accept: text/event-stream or stream=true
- Non-stream JSON fallback when stream=false
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import require_role
from core.auth.models import User
from core.chat.orchestrator import ChatOrchestrator
from core.chat.schemas import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
)
from core.chat.service import ChatService
from core.common.database import get_db_session

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_chat_session(
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: ChatSessionCreateRequest | None = None,
) -> ChatSessionResponse:
    """Create a new chat session (locked during active assessed quiz or pending deletion)."""
    if current_user.status == "pending_deletion":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCOUNT_PENDING_DELETION",
                "message": (
                    "Account is pending deletion. "
                    "Chat processing is suspended during the grace period."
                ),
            },
        )
    if not current_user.has_parental_consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CONSENT_WITHDRAWN",
                "message": (
                    "Parental consent is required to process minor student data. "
                    "Processing is suspended."
                ),
            },
        )
    orchestrator = ChatOrchestrator(db)
    await orchestrator.assert_no_active_assessed_quiz(current_user.id)

    chat_service = ChatService(db)
    title = (payload.title if payload and payload.title else "New Conversation")
    subject = payload.subject if payload else None

    session = await chat_service.get_or_create_session(
        student_id=current_user.id,
        title=title,
        subject=subject,
    )
    return ChatSessionResponse.model_validate(session)


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List active chat sessions for the current student",
)
async def list_chat_sessions(
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ChatSessionResponse]:
    """List chat sessions owned by current student."""
    chat_service = ChatService(db)
    sessions = await chat_service.list_sessions(
        student_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return [ChatSessionResponse.model_validate(s) for s in sessions]


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chat session details and message history",
)
async def get_chat_session(
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChatSessionDetailResponse:
    """Fetch session history with messages and citations (verifying ownership)."""
    chat_service = ChatService(db)
    session = await chat_service.get_session(
        session_id=session_id,
        student_id=current_user.id,
    )
    return ChatSessionDetailResponse.model_validate(session)


@router.post(
    "/sessions/{session_id}/messages",
    status_code=status.HTTP_200_OK,
    summary="Send a message to the AI tutor",
)
async def send_chat_message(
    session_id: uuid.UUID,
    payload: ChatMessageCreateRequest,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
    accept: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Any:
    """Send message to AI tutor with idempotency protection.

    Returns:
        - SSE StreamingResponse when Accept: text/event-stream or payload.stream == True
        - ChatMessageResponse JSON when payload.stream == False and Accept != text/event-stream
    """
    if current_user.status == "pending_deletion":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCOUNT_PENDING_DELETION",
                "message": (
                    "Account is pending deletion. "
                    "Chat processing is suspended during the grace period."
                ),
            },
        )
    if not current_user.has_parental_consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CONSENT_WITHDRAWN",
                "message": (
                    "Parental consent is required to process minor student data. "
                    "Processing is suspended."
                ),
            },
        )
    orchestrator = ChatOrchestrator(db)

    # Determine streaming vs JSON fallback
    wants_sse = (accept is not None and "text/event-stream" in accept) or payload.stream

    # Check for idempotent retry: if already processed, return cached turn
    # without double-spending student message quota
    eff_key = idempotency_key or payload.client_turn_id
    if eff_key:
        cached = await orchestrator.get_cached_turn(current_user.id, session_id, eff_key)
        if cached:
            if wants_sse:
                async def cached_stream() -> AsyncIterator[str]:
                    if cached.get("meta"):
                        yield f"event: meta\ndata: {json.dumps(cached['meta'])}\n\n"
                    if cached.get("content"):
                        delta_json = json.dumps({"delta": cached["content"]})
                        yield f"event: token\ndata: {delta_json}\n\n"
                    for cit in cached.get("citations", []):
                        yield f"event: citation\ndata: {json.dumps(cit)}\n\n"
                    if cached.get("done"):
                        yield f"event: done\ndata: {json.dumps(cached['done'])}\n\n"

                return StreamingResponse(
                    cached_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                )
            if "response" in cached:
                return ChatMessageResponse(**cached["response"])

    # Active Quiz Lockout Check and Quota Check MUST run before stream opens
    # to return real HTTP 403 and 429 status codes
    await orchestrator.assert_no_active_assessed_quiz(current_user.id)
    await orchestrator.check_quota(current_user.id)

    if wants_sse:
        generator = orchestrator.stream_chat_turn(
            student_id=current_user.id,
            session_id=session_id,
            payload=payload,
            request=request,
            idempotency_key=eff_key,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # Non-streaming JSON fallback
    return await orchestrator.handle_message_json(
        student_id=current_user.id,
        session_id=session_id,
        payload=payload,
        idempotency_key=eff_key,
    )
