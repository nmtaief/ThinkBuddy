# P10 – Hardening, Observability, Deployment

**Read first:** `AGENT_RULES.md`, `docs/01_ARCHITECTURE.md` (§7, §8), `docs/05_SECURE_QUIZ.md` (§8).

## Task
Prepare the system for a beta launch.

## Deliverables
1. Production Docker images, Compose/stack for a single VM, Caddy/Nginx with TLS, Cloudflare setup notes (SSE-friendly: buffering off, long timeouts).
2. Secrets management, DB backups (automated, restore tested), migration runbook.
3. Observability: request IDs, OpenTelemetry traces across gateway → RAG → LLM → DB, dashboards (latency, error rate, LLM cost, quota use), Sentry.
4. Security review checklist: authz tests for every route, dependency scanning, rate-limit tuning, CORS, upload validation, PII minimization, audit log verification.
5. Load tests: auth, today payload, quiz answer submission, chat streaming (concurrent streams).
6. Data lifecycle: retention jobs, account deletion/export for family.
7. Runbooks: LLM provider outage (fallback model), Redis down, DB failover, bad content batch rollback.
8. Beta readiness report: results of all acceptance checks from P00–P09.

## Acceptance
- Staging deploys from CI with one command and rolls back cleanly.
- Load test results meet the targets in `01_ARCHITECTURE.md §7` or the report lists gaps.
- Full leakage and authorization test suites pass in CI.
