# Docker Container Infrastructure

## Service Images
- `Dockerfile.core`: ThinkBuddy Core service (FastAPI, SQLAlchemy, pgvector, multilingual RAG).
- `Dockerfile.gateway`: ThinkBuddy API Gateway (reverse proxy, rate limiter, auth header termination).
- `Dockerfile.workers`: Background worker processes (asynchronous ingestion, spaced revision jobs).

## Base Image & Security Maintenance
All services are built upon `python:3.12-slim` (Debian Linux base).

### Pre-Deployment Requirement
> **CRITICAL:** Base images **MUST be rebuilt with `--no-cache` prior to each production deployment**:
> ```bash
> docker compose build --no-cache
> ```
> This guarantees that the latest Debian upstream security patches and package updates are incorporated immediately before deployment.

### Vulnerability Management
- Base image vulnerabilities identified by Trivy are tracked in `.trivyignore` with explicit justifications.
- All application processes execute under an unprivileged non-root user (`UID 10001`, `thinkbuddy`).
- Containers run in isolated internal networks with ports strictly bound to `127.0.0.1`.
