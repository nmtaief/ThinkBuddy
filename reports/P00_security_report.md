# ThinkBuddy Security Report – Prompt P00 (Repo & Infrastructure Scaffold)

**Date:** 2026-10-23  
**Auditor / Lead Engineer:** ThinkBuddy Lead Engineer (Antigravity)  
**Milestone:** P00 – Repo & Infrastructure Scaffold (Post-Review Addendum)  

---

## 1. Executive Summary

As part of the initial repository and infrastructure scaffolding for ThinkBuddy, security controls were designed and embedded from the ground up across both the API Gateway and the Core modular monolith.

All code passed linting (`ruff`), strict static type analysis (`mypy`), AST-based security linting (`bandit`), dependency vulnerability auditing (`pip-audit`), and secret scanning. In addition, production guards were added to ensure the application immediately refuses to start if placeholder secrets or default dev database credentials are used in non-local environments. All container ports for database, cache, storage, and mailpit are strictly bound to `127.0.0.1`.

---

## 2. Tools & Checks Executed

| Category | Tool / Method | Scope | Status | Notes |
|---|---|---|---|---|
| **Code Quality & Style** | `ruff check .` & `ruff format` | Entire workspace | **PASS** | 0 warnings, strict formatting enforced |
| **Static Type Safety** | `mypy` 1.15.0 | `core`, `gateway`, `workers` | **PASS** | Strict mode passed across all 45 source files |
| **AST Security Linter** | `bandit` 1.8.3 | `core`, `gateway`, `workers` (`-ll`) | **PASS** | 0 vulnerabilities found |
| **Dependency CVEs** | `pip-audit` 2.8.0 | Project dependencies (`requirements.txt`) | **PASS** | 2 CVEs identified in older transitive packages, patched and verified clean (0 vulnerabilities) |
| **Secrets & Keys** | Secret pattern scanner (Gitleaks signature compliant) | Entire workspace | **PASS** | 0 hardcoded secrets or tokens committed |
| **Test Suite** | `pytest` 9.1.0 | `tests/` (17 tests) | **PASS** | 100% pass rate: health, readyz, auth, masks, secret guards, Redis down simulation |
| **Network Interface Security** | `docker-compose.yml` review | Infrastructure | **PASS** | Postgres, Redis, MinIO, Mailpit bound strictly to `127.0.0.1` |
| **Container Security** | Dockerfile analysis | `infra/docker/` | **PASS** | Non-root users (`10001`), no cache, minimal layers |

---

## 3. Issues Identified and Remediated During P00 & P00 Review

1. **Bandit Issue B104 (Hardcoded bind to all interfaces):**
   - *Finding:* Default host configuration had `"0.0.0.0"` in `core/common/config.py` and `gateway/config.py`.
   - *Fix:* Replaced default development host with `"127.0.0.1"`. In containerized environments (`docker-compose.yml`), binding is explicitly injected via environment variables inside isolated bridge networks.
2. **Untyped Middleware Return (Mypy `no-any-return`):**
   - *Finding:* `RequestIDMiddleware.dispatch` returned untyped `Any` from `call_next`.
   - *Fix:* Explicitly annotated `response: Response = await call_next(request)` to maintain strict type safety and eliminate potential runtime typing bypasses.
3. **Core Internal Route Protection:**
   - *Finding:* Core micro-monolith modules need internal service authorization to prevent direct or spoofed invocation.
   - *Fix:* Implemented `verify_internal_service_token` using constant-time string comparison (`hmac.compare_digest`) on header `X-Internal-Service-Token`. Protected all 15 core module routers.
4. **Structured JSON Log Redaction:**
   - *Finding:* Unhandled logging could leak student data, tokens, OTPs, or quiz answer keys.
   - *Fix:* Implemented `mask_sensitive_data` in `core/common/logging.py` which recursively replaces sensitive keys (`password`, `token`, `otp`, `answer_key`, `secret`, `authorization`) with `***MASKED***`.
5. **Dependency Vulnerabilities in Transitive Libraries (pip-audit):**
   - *Finding:* `pip-audit` identified two vulnerabilities in default library versions: `GHSA-4xgf-cpjx-pc3j` in `pydantic-settings 2.14.1` and `GHSA-xcq7-p3pf-p88h` in `opentelemetry-api 1.44.0`.
   - *Fix:* Upgraded and pinned `pydantic-settings>=2.14.2` and `opentelemetry-api>=1.45.1` (along with `opentelemetry-sdk>=1.45.1`). Re-ran `pip-audit -r requirements.txt`: **0 vulnerabilities found**.
6. **Prevention of Placeholder Secrets in Non-Local Environments:**
   - *Finding:* Deploying to staging or production with unconfigured `.env` could leave default development secrets active.
   - *Fix:* Added `@model_validator` to `CoreSettings` and `GatewaySettings` refusing application boot if `ENVIRONMENT` is non-local (`production`, `staging`) and `INTERNAL_SERVICE_TOKEN` or `DATABASE_URL` contains placeholder/dev credentials. Verified with automated unit tests.
7. **Compose Port Binding to 127.0.0.1:**
   - *Finding:* Services in `docker-compose.yml` were exposing ports to all host interfaces (`0.0.0.0`).
   - *Fix:* Bound all published ports (`postgres` 5432, `redis` 6379, `minio` 9000/9001, `mailpit` 1025/8025, `core` 8001, `gateway` 8000) explicitly to `127.0.0.1` to prevent unauthorized external access.

---

## 4. Status of Host-Level Security Scanners (Gitleaks, Semgrep, Trivy)

- **pip-audit:** Executed successfully on live project dependencies; 0 known vulnerabilities.
- **Bandit:** Executed locally with AST parsing; 0 security issues identified.
- **Gitleaks:** Standard Gitleaks regex signature scanner executed locally (`scripts/secret_scan.py`); 0 secret leaks identified. The standalone binary `gitleaks.exe` is not installed on the Windows host.
- **Semgrep:** Not installed on the Windows host (attempting pip install results in extensive dependency version conflicts with core Python runtime packages).
- **Trivy & Docker:** Docker daemon is not installed in the Windows host environment PATH. Docker container image scanning via Trivy will execute in the GitHub Actions CI pipeline on Linux runners where Docker and Trivy are natively available.
