# P00 – Repo & Infrastructure Scaffold

**Read first:** `AGENT_RULES.md`, `docs/01_ARCHITECTURE.md`, `docs/04_API_CONTRACT.md` (conventions only).

## Role
You are a senior backend/platform engineer setting up the ThinkBuddy monorepo.

## Task
Create the repository structure and a local environment that boots with one command.

## Deliverables
1. Monorepo layout: `/gateway`, `/core` (modular monolith with one package per module listed in architecture §4), `/rag`, `/workers`, `/android`, `/infra`, `/thinkbuddy-docs`.
2. `docker-compose.yml` with: Postgres 16 + pgvector, Redis 7, gateway, core, workers, local S3-compatible store (pgsty/silo), Mailpit optional.
3. Python 3.12 project setup (uv or poetry), linting (ruff), typing (mypy), pytest, pre-commit.
4. FastAPI apps for gateway and core with `/healthz` and `/readyz` (checks DB and Redis).
5. Alembic initialized; first migration enables `pgvector`, `pg_trgm`, and creates an empty baseline.
6. Config via environment (pydantic-settings), `.env.example`, no secrets committed.
7. Structured JSON logging with request ID middleware; OpenTelemetry hooks stubbed.
8. CI workflow: lint, type-check, tests, OpenAPI export check.
9. `Makefile` (or task runner) with: `up`, `down`, `migrate`, `test`, `lint`.

## Constraints
- Do not implement business features yet.
- Gateway → core communication over internal HTTP with a service token.

## Acceptance
- `make up` boots everything; `/readyz` is green on both services.
- `make test` runs and passes (health tests at minimum).
- OpenAPI JSON is exported to `/docs-generated/openapi.json` in CI.
