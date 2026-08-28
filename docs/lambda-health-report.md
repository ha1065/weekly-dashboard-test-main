# Lambda Health Report
**Date:** 2026-05-13  
**Account:** 961341524729 | **Region:** us-east-1

---

## Summary Table

| Function | Invocations (7d) | Errors (7d) | Error Rate | Trigger | Status |
|---|---|---|---|---|---|
| `production-clockify-import` | 104 | 37 | **35.6%** | EventBridge (3 rules) | ⚠️ DEGRADED |
| `jira-data-pull-lambda` | 8 | 1 | **12.5%** | EventBridge (`jira-data-pull`) | 🔴 BROKEN |
| `clockify-data-processor` | 2 | 2 | **100%** | None (orphaned) | 🔴 BROKEN |
| `production-archera-proxy` | 0 | 0 | N/A | None | ⚪ IDLE |

> All other Lambdas in the account (Amplify CDK helpers, `AWS-DevOpsAgent-test-lambda`, `delete-name-tags-*`, `funding-program-advisor-lambda-1`, `purity-health-lambda`, `test-lambda-g3-bol`, `aws-funding-rag-api`) are unrelated to the weekly-reporting project and are excluded from this report.

---

## Healthy Functions

None of the weekly-reporting Lambdas are fully healthy. `production-clockify-import` is partially functional — it successfully completes Jira imports and Clockify data ingestion — but fails on a subset of invocations due to two distinct bugs (see Broken section).

---

## Broken / Inactive Functions

### 🔴 `jira-data-pull-lambda` — BROKEN (100% init failure on recent invocations)

**Last invocation:** 2026-05-13  
**Error:** `ValueError: Database configuration not found. Set DATABASE_URL or DB_HOST/DB_PASSWORD environment variables.`  
**Failure point:** Module import at init time — `src/database/config.py` raises on startup before any handler code runs.

The function has `S3_BUCKET`, `SECRET_NAME`, `JIRA_EMAIL`, and `JIRA_DOMAIN` configured, but is missing `DB_HOST`, `DB_PASSWORD` (or `DATABASE_URL`). The code attempts to build a database URL at module load time and raises immediately if those vars are absent. Every invocation fails with `INIT_REPORT Status: error`.

> Note: 8 invocations recorded in the 7-day window with only 1 error in CloudWatch metrics — this discrepancy is because the most recent invocations (today, 2026-05-13) show 100% failure in logs. The metric window may include earlier successful runs before the current code was deployed.

---

### 🔴 `clockify-data-processor` — BROKEN (100% error rate, no trigger)

**Last invocation:** 2026-05-13  
**Error:** `ValueError: Database configuration not found. Set DATABASE_URL or DB_HOST/DB_PASSWORD environment variables.`  
**Failure point:** Same as `jira-data-pull-lambda` — `src/database/config.py` raises at module import time.

The function has `S3_BUCKET`, `SECRET_NAME`, `CLOCKIFY_WORKSPACE_ID`, `SNS_TOPIC_ARN`, and `QUICKSIGHT_ACCOUNT_ID` configured, but is missing `DB_HOST`/`DB_PASSWORD`. Additionally, this function has **no EventBridge trigger** — it is not scheduled and appears to be an orphaned legacy function superseded by `production-clockify-import`.

---

### ⚠️ `production-clockify-import` — DEGRADED (35.6% error rate)

**Last invocation:** 2026-05-13  
**Two distinct error types found in logs:**

**Error Type 1 — PostgreSQL view schema conflict (majority of errors, ~May 12):**
```
pg8000.dbapi.ProgrammingError: cannot drop columns from view (PostgreSQL error code 42P16)
```
The Lambda attempts to recreate views with `DROP VIEW IF EXISTS ... CASCADE` followed by `CREATE VIEW`. PostgreSQL raises `42P16` when a `CREATE OR REPLACE VIEW` (or equivalent) tries to remove columns from an existing view — the view must be dropped first. The `CASCADE` drop is being issued but the subsequent `CREATE VIEW` is adding fewer columns than the existing view definition, causing the conflict. This error affected multiple invocations on 2026-05-12.

**Error Type 2 — Missing function reference (most recent error, 2026-05-13):**
```
NameError: name 'get_quicksight_dataset_ids' is not defined
  File "/var/task/src/lambda_handler.py", line 1435
    qs_dataset_ids = dataset_ids if dataset_ids else get_quicksight_dataset_ids()
```
The function `get_quicksight_dataset_ids` is called but not defined (or not imported) in `lambda_handler.py`. This error occurs when `refresh_quicksight=true` and no `quicksight_dataset_ids` are passed in the event payload — specifically triggered by the `production-jira-daily-refresh` rule which passes `{"mode": "jira_import", "refresh_quicksight": true}` with no dataset IDs.

**Important:** Despite the errors, the core data import work completes successfully before the failure. Jira project sync, PS Project Status import, MC customer board ticket sync (23 customers, 846 tickets), and Clockify data ingestion all succeed. The error occurs at the QuickSight refresh step at the end of execution.

---

### ⚪ `production-archera-proxy` — IDLE (no invocations in 7 days)

**Last invocation:** 2026-03-30 (44 days ago)  
**Trigger:** None configured  
**Status:** No errors — simply not being called. Last execution in March 2026 completed without errors. This function proxies requests to the Archera API and appears to be invoked on-demand rather than on a schedule.

---

## EventBridge Schedule Map

| Rule | Schedule | Target Lambda | Lambda Status |
|---|---|---|---|
| `production-weekly-import-9am-ct` | Every Monday 9 AM CT (15:00 UTC) | `production-clockify-import` | ⚠️ DEGRADED |
| `production-weekly-import-noon-ct` | Every Monday 12 PM CT (18:00 UTC) | `production-clockify-import` | ⚠️ DEGRADED |
| `production-jira-daily-refresh` | Daily 10 AM UTC (5 AM CT) | `production-clockify-import` | ⚠️ DEGRADED — triggers the `get_quicksight_dataset_ids` NameError |
| `jira-data-pull` | Daily 9 AM UTC | `jira-data-pull-lambda` | 🔴 BROKEN — 100% init failure |

**Key observations:**
- `clockify-data-processor` has **no EventBridge trigger** — it is never scheduled to run automatically.
- All three production schedule rules target `production-clockify-import`, not `clockify-data-processor`. The `clockify-data-processor` appears to be a legacy function that was replaced.
- The `production-jira-daily-refresh` rule is the specific trigger that causes the `NameError` in `production-clockify-import` because it passes `refresh_quicksight: true` without dataset IDs.

---

## Root Cause Analysis

### RCA-1: `jira-data-pull-lambda` and `clockify-data-processor` — Missing DB env vars

Both functions share the same codebase (`src/database/config.py`) which validates database configuration at **module import time** (not inside the handler). This means the Lambda fails during the `INIT` phase before any handler code executes.

The code requires either:
- `DATABASE_URL` (full connection string), or
- Both `DB_HOST` and `DB_PASSWORD`

Neither function has these variables set. Both functions use `SECRET_NAME` pointing to Secrets Manager, but the code does not retrieve the secret at init time — it expects the env vars to be set directly.

**Root cause:** A code deployment updated `src/database/config.py` to require DB env vars at module load time, but the Lambda environment variables were never updated to include them. The `production-clockify-import` function avoids this because it retrieves secrets inside the handler body (`Retrieving secrets from Secrets Manager...` appears in its logs).

---

### RCA-2: `production-clockify-import` — PostgreSQL view schema conflict (Error 42P16)

The Lambda attempts to recreate database views by dropping and recreating them. The error `cannot drop columns from view` (PostgreSQL `42P16`) occurs when:
1. An existing view has columns A, B, C
2. The new `CREATE VIEW` definition has fewer columns (e.g., only A, B)
3. PostgreSQL rejects this because dependent objects may rely on column C

The `DROP VIEW ... CASCADE` statements are being issued as separate invocations (`mode: run_query`) before the view recreation, but the cascade drop and the create are not happening atomically — concurrent invocations or a failed drop may leave the old view in place.

**Root cause:** A schema migration on 2026-05-12 changed the column set of one or more views. The migration was run as individual `run_query` invocations rather than a single transaction, creating a race condition or partial-failure scenario.

---

### RCA-3: `production-clockify-import` — `get_quicksight_dataset_ids` NameError

The function at line 1435 of `lambda_handler.py` calls `get_quicksight_dataset_ids()` as a fallback when no dataset IDs are provided in the event. This function is not defined or imported in the current deployed code.

**Root cause:** A refactor removed or renamed `get_quicksight_dataset_ids` but did not update the call site at line 1435. The `production-jira-daily-refresh` rule always triggers this path because it passes `{"mode": "jira_import", "refresh_quicksight": true}` with no `quicksight_dataset_ids` key.

---

## Recommendations

### Priority 1 — Fix `production-clockify-import` NameError (blocks daily Jira refresh)

The `production-jira-daily-refresh` rule fires every day at 5 AM CT and always hits this error. The fix is one of:
- Define `get_quicksight_dataset_ids()` in `lambda_handler.py` (returning the known dataset ID list), or
- Update the EventBridge rule input to pass `quicksight_dataset_ids` explicitly (matching the pattern used by the Monday noon rule), or
- Guard the call: `qs_dataset_ids = dataset_ids or []` and skip the refresh if the list is empty

**Effort:** Low — single-line fix or EventBridge rule update.

---

### Priority 2 — Fix `jira-data-pull-lambda` missing DB env vars

Add the required environment variables to the Lambda configuration. The function uses `SECRET_NAME: production/weekly-reporting/jira` — confirm whether the DB credentials are stored in that secret and update the code to retrieve them at handler invocation time (not at module import), consistent with how `production-clockify-import` handles secrets.

Alternatively, if this function does not actually need a database connection (it pulls from Jira and writes to S3), remove the database import from `src/lambda_function.py` line 7.

**Effort:** Low — env var update or code fix.

---

### Priority 3 — Retire or fix `clockify-data-processor`

This function has no trigger, 100% error rate, and is superseded by `production-clockify-import`. Options:
- **Delete it** if it is confirmed to be legacy (recommended — reduces confusion and cost)
- **Fix it** only if there is a specific use case not covered by `production-clockify-import`

**Effort:** Low — confirm with team, then delete via console or IaC.

---

### Priority 4 — Fix `production-clockify-import` view schema conflict

The `42P16` errors on 2026-05-12 appear to have been triggered by a schema migration. Verify whether the views are now in a consistent state. If the migration is complete and views are stable, no further action is needed. If the migration is ongoing, wrap view recreation in a single transaction with explicit `DROP VIEW ... CASCADE` before `CREATE VIEW`.

**Effort:** Medium — requires schema review and migration strategy change.

---

### Priority 5 — Add timeout guard to `jira-data-pull-lambda`

The function has a 30-second timeout with 128 MB memory. Once the DB env var issue is fixed, verify the function completes within the timeout — Jira API calls can be slow under load.

---

### Operational Improvement — Add CloudWatch Alarms

None of the weekly-reporting Lambdas have CloudWatch alarms on the `Errors` metric. The 35.6% error rate on `production-clockify-import` went undetected until manual investigation. Recommend adding:
- Alarm: `Errors > 0` for `jira-data-pull-lambda` (any error is a problem)
- Alarm: `Errors / Invocations > 10%` for `production-clockify-import`
- SNS notification to the existing `production-weekly-reporting-notifications` topic (already configured on the Lambda)
