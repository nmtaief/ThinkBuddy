# ThinkBuddy – Engineering Questions & Decisions Log

This document records ambiguities, questions, and the chosen defaults according to `AGENT_RULES.md` Rule 16.

---

### [P00] Local Docker Daemon Availability
- **Context:** The development host environment (Windows) currently does not have `docker` or `docker compose` available in the system PATH.
- **Documented Default:** We provide complete, production-ready `docker-compose.yml` and Dockerfiles for `gateway`, `core`, and `workers` along with Postgres 16 + pgvector, Redis 7, MinIO, and Mailpit. For testing and local validation in this environment, tests run directly with `pytest` using ASGI transports and mock/configurable DB and Redis adapters.
- **Status:** Documented default in use.

### [P00] Task Runner on Windows Environments
- **Context:** Standard `make` utility is not natively installed on Windows.
- **Documented Default:** Provide both a canonical `Makefile` for Unix/CI and an equivalent cross-platform task runner `scripts/run.py` so that commands (`test`, `lint`, `migrate`, `export-openapi`) run seamlessly everywhere via `python scripts/run.py <task>`.
- **Status:** Documented default in use.
