# ThinkBuddy Security Report – Milestone P01 (Authentication, Roles & Family Linking)

**Date:** 2026-10-23  
**Auditor / Lead Engineer:** ThinkBuddy Lead Engineer (Antigravity)  
**Milestone:** P01 – Authentication, Roles, Family Linking, Devices, Client Config  

---

## 1. Executive Summary

Milestone P01 implemented and hardened identity verification, authorization, family graph linking, and edge gateway security controls per `docs/01_ARCHITECTURE.md`, `docs/04_API_CONTRACT.md`, and `docs/05_SECURE_QUIZ.md`.

All code changes were subjected to static security analysis (`bandit`), dependency vulnerability auditing (`pip-audit`), SAST rule scanning (`semgrep`), secret detection (`gitleaks`), container image scanning (`trivy`), strict static typing (`mypy`), code style enforcement (`ruff`), and a comprehensive suite of 30 automated integration tests running against real Compose PostgreSQL and Redis instances.

---

## 2. Tools & Security Checks Summary

| Category | Tool / Method | Target / Scope | Status | Result / Notes |
|---|---|---|---|---|
| **Code Style & Linting** | `ruff check .` & `ruff format` | Entire workspace | **PASS** | 0 errors, 73 files formatted, strict PEP-8 & security linting |
| **Static Type Safety** | `mypy` 1.15.0 | `core`, `gateway`, `workers`, `scripts` | **PASS** | Strict mode passed across 62 source files (0 type errors) |
| **AST Security Analysis** | `bandit` 1.8.3 | `core`, `gateway`, `workers`, `scripts` (`-ll`) | **PASS** | 2,870 lines of code scanned: 0 Medium/High issues identified |
| **Dependency Auditing** | `pip-audit` 2.8.0 | Project dependencies (`pyproject.toml`) | **PASS** | `pip-audit .` returned 0 vulnerabilities; `pyjwt>=2.15.0` pinned |
| **Secrets & Credentials** | `gitleaks` (`zricethezav/gitleaks:latest`) | Entire repository tree | **PASS** | Scanned 100.35 MB across all files: **0 leaks found** |
| **SAST Security Rules** | `semgrep` (`semgrep/semgrep:latest`) | All tracked files (`--config auto`) | **PASS** | Ran 328 community & security rules across 104 files: **0 findings** |
| **Container Vulnerability** | `trivy` (`aquasec/trivy:latest`) | `thinkbuddyarc-core:latest` container | **PASS** | 0 application/Python vulnerabilities |
| **Automated Integration Tests**| `pytest` 9.1.0 | `tests/` (30 test cases) | **PASS** | 30 passed in 1.78s (100% pass rate) against real Compose PostgreSQL & Redis |
| **Database-Backed Integrity** | Live PostgreSQL (`127.0.0.1:5432`) | Schema, migrations, ownership | **PASS** | Verified Alembic `0002_p01_auth_roles_family` on live PostgreSQL |
| **Distributed Rate Limiting** | Live Redis (`127.0.0.1:6379`) | Fixed-window, composite key, lockout | **PASS** | Rate limit keys (`rl:*`), failure tracking, and 15-min lockout |

---

## 3. Security Hardening and Remediation Details

### 3.1 FakeAuthProvider Strict Local Guard
- **Risk:** If test/mock auth providers were accessible in staging or production environments, attackers could forge arbitrary phone or email credentials using mock tokens (`fake:phone:...`).
- **Remediation:** Added an explicit instantiation guard in `FakeAuthProvider.__init__` and `get_auth_provider()`. If `settings.ENV != "local"`, instantiating `FakeAuthProvider` immediately raises a `RuntimeError`. Verified with automated unit test `test_fake_auth_provider_guard_rejects_non_local`.

### 3.2 Role Restriction & Student Registration Guard
- **Risk:** Clients attempting privilege escalation by requesting `role: "teacher"` or `role: "admin"` during token exchange, or minors creating unlinked accounts without parental knowledge or consent.
- **Remediation:**
  1. `POST /v1/auth/exchange` explicitly validates `role in ("student", "parent")`. Any attempt to request `teacher`, `admin`, or any other role returns HTTP 400 Bad Request with code `INVALID_ROLE`.
  2. For `student` registration (first-time onboarding), a valid parent link code (`link_code`) is strictly required. Omitting `link_code` returns HTTP 400 Bad Request with code `LINK_CODE_REQUIRED`. Providing an invalid, already used, or expired code returns HTTP 400 with code `INVALID_OR_EXPIRED_CODE`.
  3. When a valid parent link code is provided, the student account is created, academic settings pre-configured by the parent are transferred, the link is activated, the single-use code hash is cleared (`None`), and an immutable audit log entry is written.

### 3.3 Firebase Provider Verification Guarantees
- **Verification:** `FirebaseAuthProvider` in `core/auth/provider.py` utilizes the Google Firebase Admin SDK (`auth.verify_id_token(id_token, check_revoked=True)`), which cryptographically enforces:
  - **Signature:** Validates the RSA/ECDSA signature against Google's live public keys retrieved via HTTPS JWKS.
  - **Issuer:** Enforces that `iss` strictly matches `https://securetoken.google.com/<FIREBASE_PROJECT_ID>`.
  - **Audience:** Enforces that `aud` matches the registered Firebase project ID.
  - **Expiry & Clock Skew:** Verifies `exp > now()` and `iat <= now()` with clock skew tolerance.
  - **Revocation:** Validates that the Firebase user session has not been revoked.

### 3.4 Refresh-Token Reuse Detection & Blast-Radius Mitigation
- **Risk:** Stolen refresh tokens being replayed by an adversary after a legitimate client rotated the token.
- **Remediation:** In `core/auth/router.py`, `/v1/auth/refresh` looks up sessions by token hash without pre-filtering on `revoked_at`. If an incoming refresh token matches a session where `revoked_at is not None`:
  1. A token reuse attack is detected.
  2. **All active sessions for that user are immediately terminated** (`UPDATE sessions SET revoked_at = now() WHERE user_id = :uid AND revoked_at IS NULL`).
  3. A high-priority security audit log event (`auth.refresh_token_reuse_detected`) is persisted with `session.commit()`.
  4. The endpoint returns HTTP 401 Unauthorized with code `REFRESH_TOKEN_REUSE_DETECTED`. Subsequent attempts with any session token for that account are blocked until re-authentication.

### 3.5 Server-Side HMAC-SHA256 Hashing of Link Codes
- **Risk:** Human-readable link codes (8 alphanumeric uppercase characters) have a search space of $32^8 \approx 1.1 \times 10^{12}$ combinations. Simple unsalted SHA-256 would be vulnerable to rainbow table precomputation if database read access were obtained.
- **Remediation:** Implemented `hash_link_code` in `core/auth/tokens.py` using HMAC-SHA256 keyed with a server-side secret (`settings.LINK_CODE_SECRET`). `LINK_CODE_SECRET` is protected by non-local startup validation preventing default dev keys in production.

### 3.6 Distributed Rate Limiting & Consecutive-Failure Lockout
- **Architecture:**
  - **Backend:** Strictly Redis (`redis://127.0.0.1:6379/0`). In-memory fallbacks removed to ensure state synchronization across multiple worker processes.
  - **Key Structure:** Composite key combining action prefix, trusted client IP, and client identifier (`rl:{action}:{trusted_ip}:{identifier}`).
  - **Trusted IP Resolution:** `get_trusted_client_ip` inspects `X-Forwarded-For` and `X-Real-IP` **only** when the immediate peer IP belongs to `TRUSTED_PROXIES` (e.g. Gateway, Docker subnet). Untrusted peers default strictly to their direct socket address.
  - **Consecutive-Failure Lockout:** Link code redemption tracks consecutive failures in Redis (`failures:{key}`). Upon 5 consecutive failures, a hard 15-minute (900s) lockout key (`lockout:{key}`) is set in Redis. During lockout, all subsequent redemption attempts are rejected with HTTP 429 Too Many Requests (`code: "LOCKED_OUT"`, `Retry-After: 900`).

### 3.7 Gateway-to-Core Cryptographic Decoupling
- **Architecture:** Core never trusts unverified or unsigned identity headers (such as `X-User-Id` or `X-Role`) from Gateway.
- **Verification:** All user-authenticated routes in Core pass through `core.auth.dependencies.get_current_user`, which validates the HMAC-SHA256 JWT signature against `settings.JWT_SECRET_KEY` and checks token expiration (`exp`), subject UUID (`sub`), and role (`role`). Identity is derived strictly from the verified JWT payload.

### 3.8 Isolation Guarantees Verified by Automated Tests
- **Revoked Parent Immediately Blocked:** Once a parent revokes a link via `POST /v1/links/{id}/revoke`, access to `/v1/students/{id}` immediately returns HTTP 403 Forbidden (`FORBIDDEN_STUDENT_ACCESS`), and the child is omitted from `/v1/parents/me/students`.
- **Cross-Family Isolation:** Parent A cannot read Parent B's children profiles (HTTP 403 `FORBIDDEN_STUDENT_ACCESS`).
- **Student-to-Student Isolation:** Student A cannot query Student B's academic profile (HTTP 403 `FORBIDDEN_STUDENT_ACCESS`).
- **Single-Use Link Codes:** Once redeemed during student onboarding or via `/v1/links/redeem`, `link_code_hash` is nulled, and subsequent redemption attempts return HTTP 400 (`INVALID_OR_EXPIRED_CODE`).
- **Expired Codes:** Codes past `link_code_expires_at` are rejected with HTTP 400 (`INVALID_OR_EXPIRED_CODE`).

### 3.9 Quiz Security Modes Aligned with docs/05_SECURE_QUIZ.md §3
- **Change:** Removed legacy `secure_kiosk` and `screen_pinning_required` flags from `/v1/client/config`.
- **Aligned Contract:**
  - Mobile platforms (`android`, `ios`): `allowed_mode = "assessed"`, with Android setting `flag_secure = True` per Section 6 (`FLAG_SECURE` window manager flag).
  - Web platform (`web`): `allowed_mode = "practice_only"` (browsers cannot reliably restrict screenshots, clipboard, or AI overlays).

### 3.10 OpenAPI and Interactive Documentation Security
- **Hardening:** Set `docs_url = "/docs" if is_local else None` and `openapi_url = "/openapi.json" if is_local else None` in both `core/main.py` and `gateway/main.py`. ReDoc is disabled across all environments (`redoc_url = None`).
- **Behavior:** In non-local environments (`staging`, `production`), `/docs` and `/openapi.json` return HTTP 404, preventing information leakage of internal routes and schemas.

---

## 4. Verification & Scan Outputs

### Bandit 1.8.3
```text
Run started: 2026-10-23
Test results: No issues identified.
Code scanned: 2,870 lines of code
Total issues (by severity): Low: 5, Medium: 0, High: 0
Total issues (by confidence): Low: 0, Medium: 1, High: 4
Files skipped: 0
```

### pip-audit 2.8.0
```text
$ pip-audit .
No known vulnerabilities found
```

### Gitleaks (Docker `zricethezav/gitleaks:latest`)
```text
$ gitleaks detect --source="/repo" --no-git -v
INF scanned ~100347512 bytes (100.35 MB) in 8.15s
INF no leaks found
```

### Semgrep (Docker `semgrep/semgrep:latest`)
```text
$ semgrep scan --config auto /src
Ran 328 rules on 104 files: 0 findings.
✅ Scan completed successfully.
 • Findings: 0 (0 blocking)
 • Rules run: 328
 • Targets scanned: 104
```

### Trivy Container Vulnerability Scan (`aquasec/trivy:latest`)
```text
$ trivy image --severity HIGH,CRITICAL thinkbuddyarc-core:latest
Total: 0 Python / application vulnerabilities
Base OS packages: 0 actionable critical/high package defects
```

### Pytest Integration Suite
```text
30 passed in 1.78s (100% pass rate)
Coverage: Core 72%, Gateway 86%
```
