"""Setup separate database roles for API and Keys/Grading.

Per docs/05_SECURE_QUIZ.md and P04 hardening:
- thinkbuddy_api: Granted access to all tables EXCEPT question_keys; reads questions via v_questions_public.
- thinkbuddy_grading: Granted access to question_keys for isolated scoring worker.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from core.common.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("thinkbuddy.setup_roles")

ROLES_STATEMENTS = [
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thinkbuddy_api') THEN
            EXECUTE 'CREATE ROLE thinkbuddy_api WITH LOGIN PASSWORD ''thinkbuddy_api_password''';
        ELSE
            EXECUTE 'ALTER ROLE thinkbuddy_api WITH LOGIN PASSWORD ''thinkbuddy_api_password''';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thinkbuddy_grading') THEN
            EXECUTE 'CREATE ROLE thinkbuddy_grading WITH LOGIN PASSWORD ''thinkbuddy_grading_password''';
        ELSE
            EXECUTE 'ALTER ROLE thinkbuddy_grading WITH LOGIN PASSWORD ''thinkbuddy_grading_password''';
        END IF;
    END
    $$;
    """,
    "GRANT USAGE ON SCHEMA public TO thinkbuddy_api, thinkbuddy_grading;",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO thinkbuddy_api;",
    "REVOKE ALL ON question_keys FROM thinkbuddy_api;",
    "GRANT SELECT ON v_questions_public TO thinkbuddy_api;",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO thinkbuddy_grading;",
]


async def setup_database_roles() -> None:
    async with AsyncSessionLocal() as session:
        for stmt in ROLES_STATEMENTS:
            await session.execute(text(stmt))
        await session.commit()
        logger.info("Successfully established separate database roles: thinkbuddy_api and thinkbuddy_grading")


if __name__ == "__main__":
    asyncio.run(setup_database_roles())
