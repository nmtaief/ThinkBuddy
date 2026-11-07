"""Database setup, async engine, sessions, and readiness checks with pgvector support."""

import contextvars
import logging
import os
import sys
import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from core.common.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities in ThinkBuddy."""

    pass


# Global engine and sessionmaker

is_test = settings.ENVIRONMENT.lower() in {"testing", "test"}
is_worker = bool(os.getenv("IS_WORKER") or ("celery" in sys.argv[0].lower() if sys.argv else False))

engine_kwargs: dict[str, Any] = {
    "echo": (settings.ENVIRONMENT == "development" and settings.LOG_LEVEL == "DEBUG"),
}
if is_test:
    engine_kwargs["poolclass"] = NullPool
elif is_worker:
    engine_kwargs["pool_size"] = settings.WORKER_DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.WORKER_DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 1800
else:
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 1800

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

# Context variable for per-request database query tracking (mutable container for cross-task visibility)
db_query_stats_ctx: contextvars.ContextVar[list[float]] = contextvars.ContextVar("db_query_stats", default=[0.0, 0.0])


def reset_db_query_stats() -> None:
    """Reset query count and elapsed query time for the active request task."""
    db_query_stats_ctx.set([0.0, 0.0])


def get_db_query_stats() -> tuple[int, float]:
    """Return (query_count, total_db_time_seconds) for the current request context."""
    stats = db_query_stats_ctx.get()
    return int(stats[0]), stats[1]


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any) -> None:
    conn.info.setdefault("query_start_stack", []).append(time.perf_counter())


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any) -> None:
    stack = conn.info.get("query_start_stack")
    start_time = stack.pop() if stack else time.perf_counter()
    elapsed = max(0.0, time.perf_counter() - start_time)
    stats = db_query_stats_ctx.get()
    stats[0] += 1.0
    stats[1] += elapsed


@event.listens_for(engine.sync_engine, "handle_error")
def handle_error(exception_context: Any) -> None:
    conn = getattr(exception_context, "connection", None)
    stack = conn.info.get("query_start_stack") if conn else None
    if stack:
        start_time = stack.pop()
        elapsed = max(0.0, time.perf_counter() - start_time)
        stats = db_query_stats_ctx.get()
        stats[0] += 1.0
        stats[1] += elapsed


async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Standard alias for session factory
AsyncSessionLocal = async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an asynchronous database session."""
    async with async_session_factory() as session:
        try:
            yield session
            if session.is_active:
                await session.commit()
        except Exception:
            if session.is_active:
                await session.rollback()
            raise


async def check_database_ready() -> tuple[bool, str]:
    """Check database connectivity and verify essential extensions (pgvector)."""
    try:
        async with engine.connect() as conn:
            # Check basic connection
            result = await conn.execute(text("SELECT 1"))
            if result.scalar() != 1:
                return False, "Database check returned unexpected result"

            # Check if vector extension exists
            ext_check = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            has_vector = ext_check.scalar() is not None
            if not has_vector:
                return True, "Connected (warning: 'vector' extension not yet enabled)"

            return True, "Database healthy and vector extension verified"
    except Exception as exc:  # noqa: BLE001
        logger.error("Database readiness check failed: %s", exc)
        return False, str(exc)
