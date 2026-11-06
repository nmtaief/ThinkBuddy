# Database Migration Runbook for ThinkBuddy

## 1. Principles & Standing Rules
- **Rule 10:** Migrations ONLY through Alembic. No manual schema edits. Every migration reversible.
- **Rule 11:** Tests are part of done. Every migration must have automated forward and backward reversibility tests.
- **Rule 13:** Bangla and English everywhere: text columns must handle UTF-8 Unicode properly without collation/encoding loss.
- **Zero-Downtime Rule:** Backward-compatible migrations in production. Expand-and-contract pattern:
  1. Expand: Add new nullable columns or tables.
  2. Write/Dual-write: Application updates write to both old and new representations.
  3. Backfill: Historical rows backfilled via idempotent batch jobs.
  4. Contract: Drop unused columns in a subsequent deployment.

---

## 2. Pre-Migration Checklist
Before applying any migration to staging or production:
1. **Take an automated pre-migration database snapshot:**
   ```bash
   python scripts/backup_db.py --output backups/snapshots/pre_migration_$(date +%Y%m%d_%H%M%S).sql.gz
   ```
2. **Verify current database revision:**
   ```bash
   alembic current
   ```
3. **Inspect the pending migration SQL without executing:**
   ```bash
   alembic upgrade head --sql
   ```
4. **Check for table lock risks:** Ensure no long-running analytical queries or unindexed foreign keys cause table locks (`ACCESS EXCLUSIVE`).

---

## 3. Applying Migrations
Execute migration to the latest head revision:
```bash
alembic upgrade head
```

Verify migration status:
```bash
alembic current
```

---

## 4. Rollback Procedure
If a migration fails or issues arise immediately post-deployment:
1. **Step back one revision:**
   ```bash
   alembic downgrade -1
   ```
2. **Or downgrade to a specific known stable revision:**
   ```bash
   alembic downgrade <revision_id>
   ```
3. **Emergency Point-in-Time Restore:**
   If a migration damaged data or cannot be cleanly downgraded:
   ```bash
   python scripts/restore_db.py --input backups/snapshots/<pre_migration_snapshot>.sql.gz
   ```
   *Note: `restore_db.py` automatically replays the GDPR deletion ledger to maintain privacy compliance.*

---

## 5. Automated Verification in CI
Run the migration reversibility test suite:
```bash
pytest tests/ -k "migration"
```
Every migration in `migrations/versions/` is tested for `upgrade()` -> `downgrade()` -> `upgrade()` cycles against live PostgreSQL.
