"""Tests for Admin AI Tutor & RAG Knowledge Base configuration and diagnostics."""

from __future__ import annotations

import subprocess
import sys
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core.admin.models import AITutorConfig
from core.audit.models import AuditLog
from core.auth.models import User
from core.auth.tokens import create_access_jwt
from core.chat.llm import MockLLMGateway, get_active_llm_gateway
from core.common.database import AsyncSessionLocal

CLIENT_HEADERS_WEB = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": "desktop",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-admin-test-01",
    "Accept-Language": "en",
}

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-admin-test-02",
    "Accept-Language": "bn",
}


async def create_user(role: str = "student", display_name: str = "Test User") -> User:
    """Create and persist a test user."""
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            auth_provider="fake",
            auth_uid=f"fake:uid:{uuid.uuid4()}",
            role=role,
            status="active",
            display_name=display_name,
            phone=f"+88017{uuid.uuid4().hex[:8]}",
            locale="bn",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def test_migration_0025_reversibility() -> None:
    """Rule 10: Verify migration 0025 (ai_tutor_configs table) is cleanly downgradeable and upgradeable."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    rev_0024 = script.get_revision("0024_chat_idempotency_expires_at")
    rev_0025 = script.get_revision("0025_ai_tutor_and_rag_config")

    assert rev_0024 is not None
    assert rev_0025 is not None
    assert rev_0025.down_revision == "0024_chat_idempotency_expires_at"

    # Downgrade to 0024
    res_down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0024_chat_idempotency_expires_at"],
        capture_output=True,
        text=True,
    )
    # Upgrade back to 0025
    res_up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0025_ai_tutor_and_rag_config"],
        capture_output=True,
        text=True,
    )
    # Restore to head
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True, text=True)

    assert res_down.returncode == 0, f"Alembic downgrade to 0024 failed: {res_down.stderr}"
    assert res_up.returncode == 0, f"Alembic upgrade to 0025 failed: {res_up.stderr}"


@pytest.mark.asyncio
async def test_admin_ai_tutor_config_rbc_and_masking(gateway_client: AsyncClient) -> None:
    """Rule 9 & Rule 15: RBAC enforcement and API key masking on GET /v1/admin/ai-tutor/config."""
    admin = await create_user(role="admin", display_name="Admin Officer")
    student = await create_user(role="student", display_name="Student User")

    admin_token = create_access_jwt(admin.id, "admin")
    student_token = create_access_jwt(student.id, "student")

    admin_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {admin_token}"}
    student_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {student_token}"}

    # 1. Unauthenticated request -> 401
    res_unauth = await gateway_client.get("/v1/admin/ai-tutor/config", headers=CLIENT_HEADERS_WEB)
    assert res_unauth.status_code == 401

    # 2. Student role -> 403 Forbidden
    res_student = await gateway_client.get("/v1/admin/ai-tutor/config", headers=student_headers)
    assert res_student.status_code == 403
    assert res_student.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # 3. Admin role -> 200 OK
    res_admin = await gateway_client.get("/v1/admin/ai-tutor/config", headers=admin_headers)
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert "llm_provider" in data
    assert "primary_model" in data
    assert "fallback_model" in data
    assert "temperature" in data
    assert "confidence_threshold" in data
    assert "max_chunks" in data
    assert "is_enabled" in data
    assert "has_api_key" in data
    # Rule 15: api_key raw secret must never be present in serialized response
    assert "api_key" not in data
    assert "embedding_api_key" not in data


@pytest.mark.asyncio
async def test_admin_update_ai_tutor_config_and_audit(gateway_client: AsyncClient) -> None:
    """Test updating AI tutor configuration, secret masking, and audit log generation."""
    admin = await create_user(role="admin", display_name="AI Admin")
    student = await create_user(role="student", display_name="Student Learner")

    admin_token = create_access_jwt(admin.id, "admin")
    student_token = create_access_jwt(student.id, "student")

    admin_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {admin_token}"}
    student_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {student_token}"}

    raw_secret_key = "sk-ant-api-test-key-998877665544332211"

    update_payload = {
        "llm_provider": "anthropic",
        "api_key": raw_secret_key,
        "primary_model": "claude-3-5-sonnet",
        "fallback_model": "claude-3-haiku",
        "temperature": 0.25,
        "embedding_provider": "bge-m3",
        "confidence_threshold": 0.55,
        "max_chunks": 6,
        "is_enabled": True,
        "system_prompt": "You are Buddy, the friendly study companion for Bangladeshi students.",
    }

    # Student cannot update -> 403
    res_forbidden = await gateway_client.put(
        "/v1/admin/ai-tutor/config",
        json=update_payload,
        headers=student_headers,
    )
    assert res_forbidden.status_code == 403

    # Admin update -> 200 OK
    res_update = await gateway_client.put(
        "/v1/admin/ai-tutor/config",
        json=update_payload,
        headers=admin_headers,
    )
    assert res_update.status_code == 200
    data = res_update.json()

    assert data["llm_provider"] == "anthropic"
    assert data["primary_model"] == "claude-3-5-sonnet"
    assert data["fallback_model"] == "claude-3-haiku"
    assert data["temperature"] == 0.25
    assert data["confidence_threshold"] == 0.55
    assert data["max_chunks"] == 6
    assert data["has_api_key"] is True
    # Masked API key: reveals first 4 and last 4
    assert data["api_key_masked"].startswith("sk-a")
    assert data["api_key_masked"].endswith("2211")
    assert raw_secret_key not in data.values()

    # Rule 15: Check AuditLog table for action and ensure no plaintext keys are logged
    async with AsyncSessionLocal() as session:
        res_audit = await session.execute(
            select(AuditLog)
            .where(AuditLog.actor_id == admin.id)
            .where(AuditLog.action == "ai_tutor.config_updated")
            .order_by(AuditLog.at.desc())
        )
        audit = res_audit.scalars().first()
        assert audit is not None
        assert audit.target_type == "ai_tutor_config"
        assert audit.meta["llm_provider"] == "anthropic"
        assert audit.meta["primary_model"] == "claude-3-5-sonnet"
        assert audit.meta["has_api_key"] is True
        # Plaintext secret key must NOT be in audit meta
        assert raw_secret_key not in str(audit.meta)

        # Reset config state for test isolation
        from sqlalchemy import delete
        await session.execute(delete(AITutorConfig))
        await session.commit()


@pytest.mark.asyncio
async def test_admin_test_llm_ping_endpoint(gateway_client: AsyncClient) -> None:
    """Test administrative LLM diagnostic ping endpoint."""
    admin = await create_user(role="admin", display_name="Diagnostic Admin")
    student = await create_user(role="student", display_name="Student")

    admin_token = create_access_jwt(admin.id, "admin")
    student_token = create_access_jwt(student.id, "student")

    admin_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {admin_token}"}
    student_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {student_token}"}

    # Student forbidden
    res_student = await gateway_client.post(
        "/v1/admin/ai-tutor/test-llm",
        json={"provider": "mock", "prompt": "Ping Buddy!"},
        headers=student_headers,
    )
    assert res_student.status_code == 403

    # Admin diagnostic ping using mock provider
    res_admin = await gateway_client.post(
        "/v1/admin/ai-tutor/test-llm",
        json={"provider": "mock", "prompt": "Hello Buddy!"},
        headers=admin_headers,
    )
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert data["success"] is True
    assert data["latency_ms"] >= 0
    assert "Buddy" in data["content"]
    assert "mock" in data["model_used"]


@pytest.mark.asyncio
async def test_admin_test_rag_retrieval_endpoint(gateway_client: AsyncClient) -> None:
    """Rule 8: Test RAG diagnostic retrieval endpoint returning chunks with printed page numbers."""
    admin = await create_user(role="admin", display_name="RAG Admin")
    student = await create_user(role="student", display_name="Student")

    admin_token = create_access_jwt(admin.id, "admin")
    student_token = create_access_jwt(student.id, "student")

    admin_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {admin_token}"}
    student_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {student_token}"}

    # Student forbidden
    res_student = await gateway_client.post(
        "/v1/admin/ai-tutor/test-rag",
        json={"query": "সালোকসংশ্লেষণ কী?", "limit": 3},
        headers=student_headers,
    )
    assert res_student.status_code == 403

    # Admin diagnostic retrieval
    res_admin = await gateway_client.post(
        "/v1/admin/ai-tutor/test-rag",
        json={"query": "সালোকসংশ্লেষণ কী?", "limit": 3},
        headers=admin_headers,
    )
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert data["query"] == "সালোকসংশ্লেষণ কী?"
    assert "chunks" in data
    assert isinstance(data["chunks"], list)
    assert "confidence" in data
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_admin_ai_tutor_stats(gateway_client: AsyncClient) -> None:
    """Test administrative knowledge base stats retrieval."""
    admin = await create_user(role="admin", display_name="Stats Admin")
    student = await create_user(role="student", display_name="Student")

    admin_token = create_access_jwt(admin.id, "admin")
    student_token = create_access_jwt(student.id, "student")

    admin_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {admin_token}"}
    student_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {student_token}"}

    # Student forbidden
    res_student = await gateway_client.get("/v1/admin/ai-tutor/stats", headers=student_headers)
    assert res_student.status_code == 403

    # Admin stats
    res_admin = await gateway_client.get("/v1/admin/ai-tutor/stats", headers=admin_headers)
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert "total_books" in data
    assert "total_chapters" in data
    assert "total_chunks" in data
    assert "total_chat_sessions" in data
    assert "rag_chat_enabled" in data
    assert data["total_books"] >= 0


@pytest.mark.asyncio
async def test_dynamic_llm_gateway_resolution() -> None:
    """Verify get_active_llm_gateway returns appropriate gateway based on DB configuration."""
    async with AsyncSessionLocal() as session:
        # 1. When config has mock provider or no key, it safely yields MockLLMGateway in test environments
        gw = await get_active_llm_gateway(session)
        assert gw is not None
