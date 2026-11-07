# ThinkBuddy Staging Load Test Plan

**Document Version:** 1.0.0  
**Target Environment:** Staging (Dedicated Cloud Compute)  
**Related Documents:** `docs/01_ARCHITECTURE.md §7`, `reports/P10_beta_readiness_report.md`  

---

## 1. Objectives & Scope

This test plan defines the staging load benchmark required to validate production throughput, resource headroom, and SLA compliance for ThinkBuddy Core and Gateway.

As documented in `reports/P10_beta_readiness_report.md`, previous load benchmarks were conducted on a single development laptop under constrained CPU and RAM (>85% memory utilization) with WSL2 Docker resource limits. This staging plan isolates the load generation onto a separate physical/cloud machine, targets realistic student think time across realistic academic workflows, and defines explicit pass/fail gates.

### Primary Objectives:
1. **10-Minute Steady Run at 50 Concurrent Users:** Measure sustained latency percentiles (p50, p90, p95, p99) and server resource consumption under realistic student pacing (5–15s think time).
2. **Stress Ramp to Failure / Saturation:** Incrementally scale load (50 $\to$ 100 $\to$ 150 $\to$ 200 $\to$ 300 users) to determine the saturation threshold, database connection pool exhaustion point, and latency knee-of-curve.
3. **Database Query Efficiency & Server-Side Timing Verification:** Verify query counts and execution durations for instrumented routes:
   - `POST /v1/auth/exchange`
   - `GET /v1/students/{id}/today`
   - `POST /v1/students/{id}/quizzes`
   - `POST /v1/quizzes/{id}/attempts` (and `/attempts/create`)
4. **Validation of Architectural Targets (docs/01_ARCHITECTURE.md §7):**
   - Non-chat API endpoints: **$\text{p95} < 400\text{ ms}$**
   - Chat SSE stream first-token: **$\text{p95} < 2,500\text{ ms}$**
   - Unhandled error rate: **$0.0\%$**

---

## 2. Infrastructure & Topology

The staging environment must run on dedicated cloud infrastructure fronted by PgBouncer, with a completely separate load-generation machine within the same VPC.

```
┌─────────────────────────────────────────────────────────────┐
│  LOAD GENERATOR INSTANCE (Dedicated, e.g. AWS c6i.2xlarge)  │
│  • 8 vCPUs, 16 GB RAM                                       │
│  • Locust / Distributed Async Benchmark Engine              │
│  • Generates authentic student think time (Poisson dist)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Private VPC Network (<1ms RTT)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGING APPLICATION SERVER (e.g. AWS c6i.xlarge)           │
│  • Caddy Edge Proxy (TLS termination, unbuffered SSE)       │
│  • ThinkBuddy Gateway (FastAPI, 4 Uvicorn workers)          │
│  • ThinkBuddy Core API (FastAPI, 4 Uvicorn workers)         │
│  • Celery Workers (4 concurrency) + Celery Beat             │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│ MANAGED POSTGRESQL 16 + RAG  │ │ REDIS 7 CLUSTER / SENTINEL │
│ • 4 vCPUs, 16 GB RAM         │ │ • Rate Limiting & Auth TTL │
│ • pgvector extension         │ │ • SSE Pub/Sub & Idempotency│
│ • PgBouncer (Tx pool: 50)    │ └────────────────────────────┘
│ • max_connections = 250      │
└──────────────────────────────┘
```

### Server Configuration
- **Application Node:** Linux (Ubuntu 24.04 LTS), 4 vCPUs, 16 GB RAM.
- **Uvicorn Workers:** `WEB_CONCURRENCY=4` (4 worker processes per service: Core & Gateway).
- **Database:** PostgreSQL 16 with `pgvector`, PgBouncer transaction pooling (`default_pool_size=40`, `max_client_conn=250`).
- **SQLAlchemy Pool Settings:** `DB_POOL_SIZE=25`, `DB_MAX_OVERFLOW=15`, `DB_POOL_TIMEOUT=15.0s`.
- **Instrumentation Headers Enabled:** `Server-Timing`, `X-DB-Query-Count`, `X-DB-Time-Ms`, `X-Server-Time-Ms`.

---

## 3. Workload Models & Traffic Profiles

### Scenario A: 10-Minute Steady Run (50 Concurrent Users)
- **User Count:** 50 simulated concurrent students.
- **Ramp-Up:** 60 seconds (1 user every 1.2s).
- **Duration:** 10 minutes (600s) sustained at peak.
- **Think Time:** Random log-normal distribution with $\mu = 8\text{s}$, range $3\text{s}$ to $18\text{s}$ between actions (reading questions, reviewing notes, checking routine).
- **Traffic Mix:**
  - **35% Today Schedule & Study Session:** `GET /v1/students/{id}/today`, mark study progress.
  - **25% Practice Quiz Interaction:** Create practice quiz $\to$ start attempt $\to$ answer 5 questions sequentially with 4s–10s pacing $\to$ complete attempt.
  - **25% AI Study Assistant SSE Chat:** Stream question in science/math, consume streamed tokens with 40ms pacing.
  - **15% Auth & Profile:** Token exchange and profile fetch.

### Scenario B: Stress Ramp Test (Capacity Saturation)
- **Duration:** 20 minutes total.
- **Ramp Schedule:**
  - 0–3 min: 50 users (baseline).
  - 3–6 min: 100 users.
  - 6–9 min: 150 users.
  - 9–12 min: 200 users.
  - 12–15 min: 250 users.
  - 15–18 min: 300 users.
  - 18–20 min: Ramp-down to 0.
- **Objective:** Locate the knee-of-curve where p95 breaches 400ms and determine whether the system fails cleanly (HTTP 503 `DB_CONGESTION_RETRYABLE`) without unhandled 500 errors or cascading connection dropouts.

---

## 4. Metrics to Record & Capture Procedures

### 4.1. Client-Side Latency & Throughput (from Load Generator)
Record for each flow separately:
- **Total Requests & RPS (Requests Per Second)**
- **Error Rate:** Must be 0.0% (except intentional rate-limit 429 tests).
- **Latency Percentiles:** p50, p90, p95, p99, and Max.

| Monitored Route | Target Method & Path | §7 Target p95 | Single-Req Expected Queries |
| :--- | :--- | :--- | :--- |
| **Sign-in / Token Exchange** | `POST /v1/auth/exchange` | $< 400\text{ ms}$ | 2 |
| **Today Schedule** | `GET /v1/students/{id}/today` | $< 400\text{ ms}$ | 5 |
| **Quiz Create** | `POST /v1/students/{id}/quizzes` | $< 400\text{ ms}$ | 2 |
| **Attempt Start** | `POST /v1/quizzes/{id}/attempts` | $< 400\text{ ms}$ | 3 |
| **Quiz Item Answer** | `POST /v1/quizzes/{id}/attempts/{id}/items/{pos}/answer` | $< 400\text{ ms}$ | 3–4 |
| **Chat SSE First-Token** | `POST /v1/chat/sessions/{id}/messages` (TTFT) | $< 2,500\text{ ms}$ | 3 |

### 4.2. Server-Side Timing & Database Headers
During the 10-minute steady run, sample and record the returned HTTP response headers:
- `Server-Timing`: Parse `app;dur=<ms>` and `db;dur=<ms>`.
- `X-DB-Query-Count`: Compare observed live query counts against the theoretical baseline.
- `X-DB-Time-Ms`: Confirm database query time remains $< 30\text{ ms}$ per request under load.

### 4.3. Database Diagnostics
Capture before, during, and after each run:
1. **`pg_stat_statements` Snapshot:**
   ```sql
   SELECT query, calls, total_exec_time, mean_exec_time, max_exec_time
   FROM pg_stat_statements
   ORDER BY total_exec_time DESC
   LIMIT 15;
   ```
2. **Lock Wait Snapshot (`pg_locks`):**
   ```sql
   SELECT count(*) FROM pg_locks WHERE NOT granted;
   ```
3. **Active Connection Count by Component:**
   ```sql
   SELECT client_addr, application_name, state, count(*)
   FROM pg_stat_activity
   GROUP BY client_addr, application_name, state;
   ```

### 4.4. Host & Process Resources
- **CPU Utilization:** Core API processes, Gateway processes, PostgreSQL, PgBouncer, Redis.
- **Memory RSS:** Check for progressive memory leaks across the 10-minute steady run.
- **Open File Descriptors & Socket States:** Monitor `netstat -an | grep TIME_WAIT` to detect socket exhaustion.

---

## 5. Execution Steps

1. **Pre-flight Check:**
   - Seed staging database with 2,000 realistic NCTB curriculum questions and 500 test student profiles.
   - Run Alembic migration check: `alembic current` matches latest migration.
   - Verify Redis connectivity and clear existing rate limit keys.
   - Verify Celery beat worker is running `cleanup_expired_idempotency_records_task`.
2. **Execute Steady 10-Minute Run:**
   - Launch load generator from the separate machine:
     ```bash
     python scripts/run_load_test.py --host https://staging-api.thinkbuddy.local \
       --users 50 --duration 600 --think-time 8.0 --output reports/staging_steady_50u.json
     ```
3. **Execute Stress Ramp:**
   - Run stepped ramp up to 300 users:
     ```bash
     python scripts/run_load_test.py --host https://staging-api.thinkbuddy.local \
       --ramp-schedule "50:180,100:180,150:180,200:180,250:180,300:180" \
       --output reports/staging_stress_ramp.json
     ```
4. **Collect Artifacts & Generate Report:**
   - Export Prometheus metrics graphs for `ROUTE_DB_QUERIES`, `ROUTE_DB_DURATION_SECONDS`, and `http_request_duration_seconds`.
   - Collate `pg_stat_statements` diff.
   - Fill out the readiness report staging section.

---

## 6. Acceptance Criteria (Pass / Fail Gates)

The staging load test will be marked **PASS** if and only if all of the following conditions are met:

- [ ] **Zero Unhandled Errors:** 0.0% HTTP 500 errors across the entire 10-minute steady run.
- [ ] **SLA Latency Compliance (p95):**
  - `POST /v1/auth/exchange`: p95 $< 400\text{ ms}$
  - `GET /v1/students/{id}/today`: p95 $< 400\text{ ms}$
  - `POST /v1/students/{id}/quizzes`: p95 $< 400\text{ ms}$
  - `POST /v1/quizzes/{id}/attempts`: p95 $< 400\text{ ms}$
  - `POST /v1/quizzes/{id}/attempts/{id}/items/{pos}/answer`: p95 $< 400\text{ ms}$
  - `POST /v1/chat/sessions/{id}/messages` (First Token): p95 $< 2,500\text{ ms}$
- [ ] **No Unchecked Query Inflation:** Query counts for instrumented routes match the target:
  - Auth exchange $\le 2$ queries
  - Today schedule $\le 5$ queries
  - Quiz create $\le 2$ queries
  - Attempt start $\le 3$ queries
- [ ] **Zero Deadlocks / Unresolved Lock Waits:** `pg_locks` reports 0 ungranted locks.
- [ ] **Memory Stability:** Worker process memory does not grow monotonically (zero memory leak in ASGI worker processes).

