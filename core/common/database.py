"""Database setup, async engine, sessions, and readiness checks with pgvector support."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.common.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities in ThinkBuddy."""

    pass


# Global engine and sessionmaker
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development" and settings.LOG_LEVEL == "DEBUG"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an asynchronous database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
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
