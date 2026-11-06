# Runbook: Deletion Ledger Replay After Database Restore

## Purpose & Scope
This runbook defines the operational procedure for restoring the ThinkBuddy production database from a point-in-time snapshot without inadvertently resurrecting deleted accounts, minors' study data, or families who exercised their right to be forgotten (P07b / GDPR Art. 17).

## Problem Statement
When PostgreSQL is restored from a backup snapshot created at time $T_0$, the snapshot state reflects the database at $T_0$. If users or families requested deletion and were purged at time $T_1$ (where $T_1 > T_0$), restoring the $T_0$ backup will resurrect those deleted entities unless an append-only deletion ledger is replayed.

## The Deletion Ledger Architecture
1. **Immutable Ledger (`deletion_ledger` table)**:
   - Schema:
     - `id`: UUID primary key
     - `user_id_hash`: SHA-256 hex digest of the deleted `user_id` or `family_id`
     - `target_type`: `"user"` or `"family"`
     - `purged_at`: UTC timestamp of purge execution
   - **PII Minimization**: The ledger contains no plaintext identifiers (names, emails, phones, or UUIDs), preserving privacy even in audit backups.
2. **Offsite Ledger Mirroring**:
   - The deletion ledger is continuously replicated offsite to append-only object storage (`s3://thinkbuddy-ledger/deletion-ledger-log.jsonl`) via transactional worker events.

## Recovery Procedure

### Step 1: Restore PostgreSQL Database Snapshot
Restore the target backup snapshot to the recovery or primary database instance:
```bash
pg_restore --clean --if-exists -h $PGHOST -U thinkbuddy -d thinkbuddy latest_snapshot.dump
```

### Step 2: Merge Offsite Deletion Ledger Log
Ensure all deletion events up to the incident moment are present in `deletion_ledger`:
```bash
python -m core.privacy.sync_offsite_ledger --source s3://thinkbuddy-ledger/deletion-ledger-log.jsonl
```

### Step 3: Execute Deletion Ledger Replay
Execute the automated replay utility:
```bash
python -m core.privacy.replay_ledger
```
The script performs the following actions:
1. Loads all hashed user and family IDs from `deletion_ledger`.
2. Scans active `users` and `families` tables.
3. Computes `SHA256(str(entity_id))`.
4. If a match is detected (meaning the entity was deleted post-snapshot):
   - Immediately schedules an immediate purge job (`AccountDeletion` record).
   - Invokes `execute_data_purge(db)` to scrub user profiles, sessions, push tokens, study setups, quizzes, chat citations, and family linkages.
   - Clears Redis cache entries matching the resurrected IDs.

### Step 4: Verification Queries
Run the following SQL queries to ensure zero resurrected accounts remain:
```sql
-- Verify no active users match any ledger user hash
SELECT u.id, u.display_name, u.status
FROM users u
JOIN deletion_ledger dl ON encode(digest(u.id::text, 'sha256'), 'hex') = dl.user_id_hash
WHERE dl.target_type = 'user' AND u.status != 'purged';

-- Result must return 0 rows.
```

### Step 5: Resume Traffic
Once verification returns 0 rows, unpause API Gateway traffic and notify the Incident Response Commander.

