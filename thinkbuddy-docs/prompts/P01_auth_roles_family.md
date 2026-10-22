# P01 – Auth, Roles, Family Linking, Devices, Client Config

**Read first:** `AGENT_RULES.md`, `docs/02_PRODUCT_FLOWS.md` (§1–3), `docs/03_DATA_MODEL.md` (§1), `docs/04_API_CONTRACT.md`.

## Task
Implement identity for Student and Parent, with Teacher/Admin present in RBAC but disabled by feature flag.

## Deliverables
1. `AuthProvider` interface + Firebase implementation (phone OTP + Google). Add a **fake provider** for tests and local dev.
2. `POST /auth/exchange`, `/auth/refresh`, `/auth/logout`, `GET /me`. Short-lived access JWT, rotating refresh tokens stored hashed.
3. Role-based access dependency + ownership policy function (`can_access_student(user, student_id)`), used everywhere.
4. Families: parent creates family, adds child (`student_profiles`), generates link code/QR (hashed in DB, expiring), student redeems code; parent can revoke.
5. Devices: register/update, store platform, form factor, app version, push token.
6. `GET /client/config`: feature flags (teacher off), entitlements, min version, quiz security mode per platform (web = practice-only), layout hints, polling intervals.
7. Middleware requiring client headers; reject missing/invalid with a stable error code.
8. Audit log for link/unlink and role-sensitive actions.
9. Rate limits: OTP exchange and link redemption are strictly limited.

## Constraints
- A student cannot link to a family without a valid code; codes are single-use.
- Passwords are not used. Never log tokens or OTPs.

## Acceptance
- Tests: parent can read only linked children; revoked link immediately blocks access; student cannot read other students; teacher routes return 404/403 while flag is off.
- Brute-force test on link code is rate-limited.
- `/client/config` returns different `quiz_security_mode` for `android` vs `web`.
