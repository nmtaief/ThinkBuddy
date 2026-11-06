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

---

### Scenario C: Total Infrastructure Catastrophe / Offsite Cold Disaster Recovery

When the primary data center or hosting infrastructure is destroyed or unrecoverable:

#### 1. Key Storage Location & Separation of Duties
- **Encryption Key:** `BACKUP_ENCRYPTION_KEY`
- **Location:** Managed separately in Cloud KMS / AWS Secrets Manager / HashiCorp Vault at path `secret/data/production/database/backup-encryption-key`.
- **Strict Isolation Requirement:** The decryption key is **NEVER** stored in the repository, Docker images, host filesystems, or alongside the backup archives in the offsite bucket. Only designated disaster recovery engineers with audited IAM roles can access the key.

#### 2. Offsite Recovery Steps
1. **Retrieve the Decryption Key:**
   ```bash
   # From AWS Secrets Manager
   export BACKUP_ENCRYPTION_KEY=$(aws secretsmanager get-secret-value --secret-id prod/database/backup-key --query SecretString --output text)
   # Or from HashiCorp Vault
   export BACKUP_ENCRYPTION_KEY=$(vault kv get -field=key secret/production/database/backup-key)
   ```

2. **List and Identify Latest Offsite Backup Archive:**
   ```bash
   # View archives in the offsite disaster recovery bucket
   aws s3 ls s3://thinkbuddy-backups-offsite/database/
   ```

3. **Execute End-to-End Download, Decryption, and Database Restore:**
   ```bash
   python scripts/restore_db.py \
       --download-s3 <backup_filename>.sql.gz.enc \
       --bucket thinkbuddy-backups-offsite \
       --db-name thinkbuddy
   ```
   *The script automatically:*
   - Streams the ciphertext archive from `s3://thinkbuddy-backups-offsite/` into an isolated temporary workspace.
   - Decrypts the archive using AES-256-GCM authenticated encryption with `BACKUP_ENCRYPTION_KEY`.
   - Validates the cryptographic SHA-256 integrity hash against `.manifest.json`.
   - Decompresses and executes standard SQL restore into PostgreSQL.
   - Replays the Deletion Ledger (`replay_deletion_ledger()`) to guarantee post-backup GDPR/privacy purges are immediately re-applied.

4. **Verify Database Integrity and Table Counts:**
   ```bash
   python -c "
   import asyncio, asyncpg
   async def audit():
       conn = await asyncpg.connect('postgresql://thinkbuddy:thinkbuddy_dev_password@localhost:5432/thinkbuddy')
       print('Tables restored:', await conn.fetchval(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\"))
       await conn.close()
   asyncio.run(audit())
   "
   ```

5. **Bring Application Services Online & Verify:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d core gateway workers caddy
   curl -i http://localhost:8001/readyz
   ```

