# Runbook: PostgreSQL Database Failover & Disaster Recovery

## 1. Trigger & Severity
- **Severity:** P0 (Total Outage)
- **Symptoms:**
  - Health endpoint `/readyz` returns 503 `{"db": false}`.
  - Core service logs `asyncpg.exceptions.CannotConnectNowError` or connection pool timeouts.
  - Prometheus alert `PostgresDown` firing.

---

## 2. Immediate Diagnostic Steps
1. Verify container status:
   ```bash
   docker compose -f docker-compose.prod.yml ps postgres
   docker compose -f docker-compose.prod.yml logs --tail=100 postgres
   ```
2. Check PostgreSQL storage volume:
   ```bash
   df -h /var/lib/docker
   ```
3. Test connection inside container:
   ```bash
   docker exec -it thinkbuddy-postgres-prod pg_isready -U thinkbuddy -d thinkbuddy
   ```

---

## 3. Failover Scenarios

### Scenario A: Process Crash / Soft Lock
1. Restart PostgreSQL container:
   ```bash
   docker compose -f docker-compose.prod.yml restart postgres
   ```
2. Check recovery logs:
   ```bash
   docker compose -f docker-compose.prod.yml logs -f postgres
   ```
   Wait for `database system is ready to accept connections`.

### Scenario B: Data Corruption or Unrecoverable Node Failure
If data files are damaged or disk hardware failed:
1. Stop application traffic to prevent inconsistent writes:
   ```bash
   docker compose -f docker-compose.prod.yml stop gateway core workers
   ```
2. Locate the most recent automated backup snapshot from `backups/database/` or S3 backup bucket:
   ```bash
   ls -lat backups/database/thinkbuddy_backup_*.sql.gz | head -n 3
   ```
3. Execute automated restore script with cryptographic verification and deletion ledger replay:
   ```bash
   python scripts/restore_db.py --input backups/database/<latest_backup>.sql.gz
   ```
   *Note: `restore_db.py` automatically checks the deletion ledger and re-purges any accounts deleted after the snapshot point-in-time to ensure privacy invariants.*
4. Run schema migration check:
   ```bash
   alembic current
   alembic upgrade head
   ```
5. Restart application services:
   ```bash
   docker compose -f docker-compose.prod.yml start core gateway workers
   ```
6. Verify synthetic probes:
   ```bash
   curl -i http://localhost:8001/readyz
   curl -i http://localhost:8000/v1/client/config -H "X-Client-Platform: android" -H "X-Client-Form-Factor: phone" -H "X-App-Version: 1.0.0"
   ```
