# Runbook: Redis Cache & Queue Outage Handling

## 1. Trigger & Severity
- **Severity:** P1 (Degraded Caching & Task Queues)
- **Symptoms:**
  - Health endpoint `/readyz` fails with `redis: False`.
  - Rate limiting logs warning `Redis connection failed`.
  - Celery workers pause task execution.

---

## 2. Fail-Safe Behavior by Subsystem

| Subsystem | Redis Down Policy | Rationale |
|---|---|---|
| **Rate Limiter** | Fail-Open for authenticated routes, Fail-Closed on `/auth/*` | Prevent user lockout during flash outage, protect auth from brute force |
| **Re-authentication Token** | **Fail-Closed** (HTTP 503 `REAUTH_CONFIRMATION_FAILED`) | Security requirement: single-use tokens must NEVER be bypassed without Redis confirmation |
| **Today Schedule Cache** | Fallback to direct PostgreSQL query | Students can still view daily plan and tasks |
| **Celery Tasks** | Tasks backlogged until reconnect | Nightly adaptive plan updates resume upon Redis reconnect |

---

## 3. Recovery Procedure

### Step 1: Check Redis Container Health
```bash
docker compose -f docker-compose.prod.yml ps redis
docker compose -f docker-compose.prod.yml logs --tail=100 redis
```

### Step 2: Restart Redis Container
```bash
docker compose -f docker-compose.prod.yml restart redis
```

### Step 3: Check Memory & Disk Exhaustion
If Redis crashed due to OOM (`OOM command not allowed`):
1. Check host disk and memory:
   ```bash
   free -m
   df -h
   ```
2. Inspect `appendonly.aof` size in `/var/lib/docker/volumes/.../data`.
3. If AOF is corrupted, run `redis-check-aof --fix /data/appendonly.aof`.

### Step 4: Verification
Probe readiness:
```bash
curl -i http://localhost:8001/readyz
```
Expected output:
```json
{"status": "ok", "db": true, "redis": true}
```

