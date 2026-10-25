# ThinkBuddy – Engineering Questions & Decisions Log

This document records ambiguities, questions, and the chosen defaults according to `AGENT_RULES.md` Rule 16.

---

### [P00] Local Docker Daemon Availability
- **Context:** The development host environment (Windows) currently does not have `docker` or `docker compose` available in the system PATH.
- **Documented Default:** We provide complete, production-ready `docker-compose.yml` and Dockerfiles for `gateway`, `core`, and `workers` along with Postgres 16 + pgvector, Redis 7, MinIO, and Mailpit. For testing and local validation in this environment, tests run directly with `pytest` using ASGI transports and mock/configurable DB and Redis adapters.
- **Status:** Documented default in use.

### [P00] Task Runner on Windows Environments
- **Context:** Standard `make` utility is not natively installed on Windows.
- **Documented Default:** Provide both a canonical `Makefile` for Unix/CI and an equivalent cross-platform task runner `scripts/run.py` so that commands (`test`, `lint`, `migrate`, `export-openapi`) run seamlessly everywhere via `python scripts/run.py <task>`.
- **Status:** Documented default in use.

### [P07-Tail] Ceilings Table by Class Band and Day Type
- **Context:** User requested: "seed ceilings per class band and day type as default, auto ceiling, and hard limit from the table I give you".
- **Documented Default:** Based on previously established limits and budgets across P03, P06, and P07 prompts, we align the policy limits as:
  - **Class Band 6–8:**
    - `school_day`: default = 60m, auto ceiling = 120m, hard limit = 180m
    - `holiday`: default = 120m, auto ceiling = 180m, hard limit = 240m
  - **Class Band 9–10:**
    - `school_day`: default = 90m, auto ceiling = 180m, hard limit = 240m
    - `holiday`: default = 150m, auto ceiling = 240m, hard limit = 300m
  - **Class Band 11–12:**
    - `school_day`: default = 120m, auto ceiling = 240m, hard limit = 300m
    - `holiday`: default = 180m, auto ceiling = 300m, hard limit = 360m
  - Invariant rules enforced: auto mode never lowers a parent setting (`final_mins >= parent_setting`), never raises above the auto ceiling (`final_mins <= auto_ceiling`), and leaves any parent setting that is already above the auto ceiling unchanged.
- **Status:** Documented default in use.

