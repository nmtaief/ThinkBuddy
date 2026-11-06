# Secrets Management & Key Rotation Guide for ThinkBuddy

## 1. Principles & Standing Rules
- **Rule 12:** No secrets in the repository. Use environment variables and a `.env.example`.
- **Rule 15:** Log, don't leak. Structured logs with request IDs. Never log tokens, OTPs, answer keys, or chat content.
- **Rule 17:** Client token isolation. Auth tokens never stored in browser localStorage/sessionStorage. Mobile clients use hardware-backed Keystore/Keychain.

---

## 2. Environment Variables & Secret Inventory

| Variable Name | Purpose | Rotation Frequency | Blast Radius |
|---|---|---|---|
| `JWT_SECRET_KEY` | HMAC signing of short-lived gateway access tokens | 90 days | Requires user re-login or graceful dual-key transition |
| `INTERNAL_SERVICE_TOKEN` | Authenticates internal traffic between Gateway, Core, and Workers | 90 days | Core/Gateway restart required |
| `POSTGRES_PASSWORD` | PostgreSQL master password | 180 days | Zero client impact; update `.env` & DB |
| `REDIS_PASSWORD` | Redis cache & queue authentication | 180 days | Update `.env` & Redis config |
| `ENCRYPTION_MASTER_KEY` | 32-byte AES-256-GCM key for encrypted data exports at rest | 365 days | Re-encrypt pending exports if active |
| `FIREBASE_SERVICE_ACCOUNT_JSON`| Firebase Auth phone OTP & FCM push credentials | As needed | Push notifications & auth exchange |
| `SENTRY_DSN` | Sentry error monitoring | Permanent | Error telemetry reporting |

---

## 3. Secret Injection in Production
In production single-VM deployment:
1. Secrets are stored in a dedicated file outside source control: `/etc/thinkbuddy/production.env` with permissions `chmod 600`.
2. Loaded into Docker Compose via `env_file`:
   ```bash
   docker compose --env-file /etc/thinkbuddy/production.env -f docker-compose.prod.yml up -d
   ```
3. In cloud orchestrators (AWS ECS, GCP Cloud Run, Kubernetes), inject via AWS Secrets Manager, Google Secret Manager, or Vault as environment variables at container runtime.

---

## 4. Key Rotation Procedures

### 4.1. Rotating `JWT_SECRET_KEY` (Dual-Key Verification)
To rotate JWT signing keys without forcing active users out:
1. Set `JWT_PREVIOUS_SECRET_KEYS` with the old key, and `JWT_SECRET_KEY` with the newly generated 256-bit key.
2. Gateway signs all new tokens with the new key, but accepts tokens signed with any key in `JWT_PREVIOUS_SECRET_KEYS` until old tokens expire (default 15 minutes).
3. After 15 minutes, remove the old key from `JWT_PREVIOUS_SECRET_KEYS`.

### 4.2. Rotating `INTERNAL_SERVICE_TOKEN`
1. Update `INTERNAL_SERVICE_TOKEN` across `core`, `gateway`, and `workers` in production `.env`.
2. Execute rolling restart:
   ```bash
   docker compose -f docker-compose.prod.yml restart gateway core workers
   ```

### 4.3. Emergency Revocation
If a token or secret is suspected of exposure:
1. Change the secret in `/etc/thinkbuddy/production.env`.
2. Restart all services.
3. Flush Redis sessions: `redis-cli -a $REDIS_PASSWORD flushdb`.
4. All active sessions are terminated immediately, forcing fresh authentication.
