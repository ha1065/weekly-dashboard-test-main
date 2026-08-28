# Weekly Reporting Dashboard Redesign — Technical Assessment

**Date:** 2026-06-05  
**Migration baseline:** 065 (highest current is `065_backfill_week_start_cst.sql` and `065_rebuild_vw_kpi_ytd_with_prev_cols.sql`)  
**Next migration number:** 066

---

## Summary

This document assesses every change required for the Weekly Reporting dashboard redesign across five areas: new database objects, view changes, Lambda changes, new QuickSight datasets, and existing dataset updates. For each item the current state is confirmed from the codebase, gaps and risks are flagged, and a migration number is assigned.

---

## 1. New Database Objects

### 1.1 `practice_area` column on `clockify_users`

| | |
|---|---|
| **Status** | ❌ Does not exist |
| **Evidence** | `models.py` `ClockifyUser` class has no `practice_area` column. The table has `practice_alignment` (free-text Clockify field) but no structured `practice_area` enum column. |
| **What is needed** | `ALTER TABLE clockify_users ADD COLUMN IF NOT EXISTS practice_area VARCHAR(50)` with a CHECK constraint for `('PS', 'MC', 'Both', 'Internal', 'Exempt', NULL)`. Needs a backfill strategy (see Data Gap below). |
| **Migration** | **066** |
| **Data Gap ⚠️** | No existing data maps `clockify_users.practice_alignment` to the new enum. A manual or script-driven backfill is required before any Lambda or view can rely on this column. The `forecast_resources.py` currently uses `practice_alignment ILIKE '%Professional%'` etc. to identify PS resources — migration 066 should include a best-effort backfill SQL that maps known `practice_alignment` values to enum values, but **a human must review/correct the output before any downstream logic switches over**. |
| **Dependency** | Must be completed before Lambda change 3d (`forecast_resources.py` practice_area filter) and before `vw_time_compliance_history`/`vw_utilization_history` if they filter on `practice_area`. |

---

### 1.2 `ps_profitability_rates` table

| | |
|---|---|
| **Status** | ❌ Does not exist |
| **Evidence** | No table or migration with this name found anywhere in `src/database/`. The existing `vw_ps_profitability_2026` view and `vw_ps_profitability_chart` view compute hours-only profitability without a rates table. |
| **What is needed** | Single-row rates lookup: `onshore_rate`, `offshore_rate`, `contractor_rate`, `billable_rate` (all `NUMERIC(10,2)`), plus a metadata timestamp. Because this is a single-row config table, upsert semantics via `ON CONFLICT (id) DO UPDATE` on a fixed `id=1` is the correct pattern. |
| **Migration** | **067** |
| **Data Gap ⚠️** | The actual rate values are not in any existing document or code. Someone must provide the four rate figures before the QuickSight profitability dataset can compute dollar-value outputs. Placeholder NULLs should be inserted and the dashboard must handle NULL rates gracefully. |
| **Data Gap ⚠️** | The `clockify_users` table has `location` (`Onshore`/`Offshore`) and `employment_designation` (contains `FTE`/`Contractor` substrings). Both columns exist and are already used in `vw_ps_profitability_2026`. The staffing mix calculation is feasible with current data once rates are provided. |

---

### 1.3 `vw_time_compliance_history`

| | |
|---|---|
| **Status** | ❌ Does not exist |
| **Evidence** | No view with this name in `create_views.sql`. The existing `vw_weekly_compliance_report` (confirmed present, line 2519) covers only the **last complete week**. The `vw_weekly_compliance_report` uses `is_compliant = hours_submitted > 0` which matches the requirement. A historical multi-week version does not exist. |
| **What is needed** | New view drawing from `clockify_detailed_time_entries` with a cross-join spine of all past weeks, joining `missing_time_reasons` (table confirmed at migration 043) for the reason field. Monthly and quarterly labels can be derived via `TO_CHAR`. |
| **Migration** | **068** (view-only, no DDL) — added to `create_views.sql` |
| **Dependency** | Requires `practice_area` column (item 1.1) if the view filters by practice area. Can be built without it first and the filter added after migration 066. |
| **Risk** | The `missing_time_reasons` table (confirmed at `043_missing_time_reasons.sql`) has columns `clockify_user_id`, `week_start`, and reason fields. The LEFT JOIN will produce NULL reason for weeks where no reason was logged — this is expected behaviour and must be handled in QuickSight. |

---

### 1.4 `vw_utilization_history`

| | |
|---|---|
| **Status** | ❌ Does not exist |
| **Evidence** | `vw_productive_utilization` (confirmed present at line 2349) computes billable %, NB productive %, NB non-productive %, and non-logged % per user per week across all historical weeks. It already has the correct category breakdowns. A separate `vw_utilization_history` is essentially a rename/alias or a derived view adding month/quarter labels on top. |
| **What is needed** | New view (or rename) that wraps `vw_productive_utilization` and adds `TO_CHAR(week_start, 'Mon YYYY')` as `month_label` and a quarter label column. Alternatively, the labels can be added directly to `vw_productive_utilization` — however, renaming the existing view risks breaking the existing QuickSight `productive-utilization` dataset. Creating a new view `vw_utilization_history` is safer. |
| **Migration** | **069** (view-only) |
| **Dependency** | None — `vw_productive_utilization` already exists with all required breakdowns. |

---

### 1.5 `artifact_verification` (MC V2 audit)

| | |
|---|---|
| **Status** | ❌ Does not exist |
| **Evidence** | `mc_v2_audit_by_phase` (confirmed in `models.py`) has no artifact columns. `mc_v2_audit_by_customer` similarly has none. Neither `create_views.sql` nor any migration references `artifact_present`, `artifact_url`, or `artifact_verified_at`. |
| **What is needed** | New table `artifact_verification` with `(id SERIAL PK, jira_issue_id VARCHAR(50) UNIQUE, artifact_present BOOLEAN, artifact_url TEXT, artifact_verified_at TIMESTAMP, verified_by VARCHAR(50), synced_at TIMESTAMP DEFAULT NOW())`. A unique constraint on `jira_issue_id` supports upsert on re-verification. Alternative: add columns directly to `mc_v2_audit_by_phase` — **not recommended** because the audit table is per-phase snapshot and artifact verification is per-issue, making a separate table the cleaner model. |
| **Migration** | **070** |
| **Dependency** | Lambda change 2 (`mc_v2_audit.py` Confluence verification) must be implemented before this table is populated. The table can be created before the Lambda is deployed so the schema is ready. |

---

## 2. View Changes

### 2.1 `vw_project_time_detail` — add `user_name`

| | |
|---|---|
| **Status** | ❌ `user_name` is missing from the view's SELECT list |
| **Evidence** | View definition at line 2680 of `create_views.sql` selects `te.clockify_entry_id, te.entry_date, week_start_date, te.client_name, te.project_name, cp.project_type, pod_assignment, te.task_name, te.description, te.user_name` — **wait**: `te.user_name` is NOT in the confirmed SELECT list (confirmed at offset 2680, the view selects through `te.description` and then `te.billable, te.duration_hours`). |
| **Correction** | Re-reading the confirmed view text: columns are `clockify_entry_id, entry_date, week_start_date, client_name, project_name, project_type, pod_assignment, task_name, description, user_name, billable, duration_hours`. The `te.user_name` **is present** in the SELECT. This change may already be in place. |
| **Risk ⚠️** | The `create_views.sql` at offset 2680 does include `te.user_name` — **confirm whether the LIVE database view matches the file**, as the file may have been updated locally without being re-applied. The QuickSight dataset `project-time-detail` must be refreshed/SPICE-refreshed after confirming the live view has the column. |
| **Migration** | **None required** if the live view already matches the file. If not: re-apply the view section from `create_views.sql`. |

---

### 2.2 `vw_weekly_compliance_report` — is_compliant = hours > 0

| | |
|---|---|
| **Status** | ✅ Already correct |
| **Evidence** | Line 2569 in `create_views.sql`: `CASE WHEN COALESCE(h.hours_submitted, 0) > 0 THEN 1 ELSE 0 END AS is_compliant`. The requirement says "hours_submitted > 0" — this matches exactly. |
| **Action** | Verify the live view definition matches. No code change required. |

---

### 2.3 `vw_ps_project_status` — confirm `actual_kickoff`, `actual_completion` exposure

| | |
|---|---|
| **Status** | ✅ Both columns are exposed |
| **Evidence** | Lines 1240–1242 of `create_views.sql`: `p.actual_kickoff, p.actual_completion` are in the SELECT list. The underlying `ps_project_status` table (confirmed in `models.py`) has both columns as `Date` fields. |
| **Action** | No change required. Confirm in QuickSight that the dataset includes these fields and the "this-week/last-week activity tiles" filter on `week_start`. |

---

### 2.4 `vw_productive_utilization` — confirm category breakdowns

| | |
|---|---|
| **Status** | ✅ All required categories are present |
| **Evidence** | View at line 2349 produces: `billable_hours`, `nb_productive_hours`, `nb_non_productive_hours`, `total_logged_hours`, and (implied from the structure) `non_logged_hours = weekly_available_hours - total_logged_hours`. The four-category breakdown (Billable, NB Productive, NB Non-Productive, Non-Logged) is fully implemented. |
| **Action** | No change required. Confirm QuickSight `productive-utilization` dataset exposes all four columns. |

---

## 3. Lambda Changes

### 3.1 Jira import (`import_jira_data.py`) — duplicate prevention

| | |
|---|---|
| **Status** | ⚠️ Partially addressed — only for `mc_customer_tickets`, not for `ps_project_status` |
| **Evidence** | The `mc_customer_tickets` INSERT at line ~807 has `ON CONFLICT (jira_issue_id) DO UPDATE`. However, `ps_project_status` uses ORM-level `db.query(...).filter_by(jira_issue_id=..., week_start=...).first()` with a manual update branch — this is a compound key (issue_id + week_start). The requirement says to fix the INSERT to use `ON CONFLICT`. |
| **Current behaviour** | The ORM approach already prevents true duplicates on (jira_issue_id, week_start). The issue is likely **performance** (two round trips: SELECT then INSERT/UPDATE) and potential race conditions during concurrent Lambda invocations. |
| **What is needed** | Refactor the `ps_project_status` upsert in `import_ps_project_status()` to use a raw SQL `INSERT ... ON CONFLICT (jira_issue_id, week_start) DO UPDATE SET ...`. This requires a unique constraint on `(jira_issue_id, week_start)`. |
| **Migration** | **071** — `ALTER TABLE ps_project_status ADD CONSTRAINT IF NOT EXISTS uq_ps_status_issue_week UNIQUE (jira_issue_id, week_start)` |
| **Risk ⚠️** | If any duplicate (jira_issue_id, week_start) rows already exist in the live database, the migration will fail. Requires a dedup step first: `DELETE FROM ps_project_status WHERE id NOT IN (SELECT MAX(id) FROM ps_project_status GROUP BY jira_issue_id, week_start)`. Include this in migration 071. |

---

### 3.2 MC V2 Audit (`mc_v2_audit.py`) — Confluence artifact verification

| | |
|---|---|
| **Status** | ❌ Does not exist |
| **Evidence** | `mc_v2_audit.py` fetches Jira issues and organises them by phase. There is no Confluence API call anywhere in the file. No `artifact_present` or `artifact_url` logic exists. |
| **What is needed** | For each Done issue in the customer's Jira project, call `GET /rest/api/3/issue/{issueKey}/remotelink` to retrieve remote links, filter for Confluence URLs, then call the Confluence REST API (`GET /wiki/rest/api/content/{pageId}`) to verify the page exists. Write results to the new `artifact_verification` table (item 1.5). |
| **Dependencies** | Requires `artifact_verification` table (migration 070). Requires `CONFLUENCE_API_TOKEN` and `CONFLUENCE_BASE_URL` environment variables to be added to the Lambda and Secrets Manager. |
| **Risk ⚠️** | Rate limiting: Jira remote links API has stricter rate limits than the issue search API. For customers with many Done issues, add backoff/retry logic. The existing `backoff` package is already in `lambda_package_temp` — use it. |
| **Risk ⚠️** | Confluence API authentication: if the Confluence instance is a separate cloud org from Jira, a different token may be required. Validate environment before implementing. |
| **Lambda timeout risk ⚠️** | Each Confluence verification is a separate HTTP call. For large projects (50+ Done issues), this could add significant execution time. Consider batching or limiting verification to issues updated in the last 30 days on each run. |

---

### 3.3 Capacity model (`forecast_resources.py`) — 4 enhancements

#### 3.3a Seasonal correction factor

| | |
|---|---|
| **Status** | ❌ Does not exist |
| **Evidence** | `forecast_resources.py` uses a flat 4-week average with no week-of-year correction. |
| **What is needed** | Query `clockify_detailed_time_entries` for 18 months of actuals, compute `avg(hours)` per `EXTRACT(week FROM week_start)` per user, compare to the overall average, and produce a ratio per calendar week. Apply this ratio as a multiplier to the base forecast. |
| **Data availability** | `clockify_detailed_time_entries` stores `week_start` — 18 months of history is assumed to exist. The current lookback is 4 weeks; verify that the database actually has 18+ months of data before implementing. If not, fall back to whatever is available. |
| **Migration** | None (Lambda-only change). May want a config table row to store `seasonal_correction_enabled BOOLEAN` in the existing forecast config mechanism (check `_load_forecast_config` references). |

#### 3.3b Dynamic lookback window

| | |
|---|---|
| **Status** | ❌ Does not exist — fixed 4-week lookback |
| **Evidence** | `forecast_resources.py` line 32: `lookback_start = current_monday - timedelta(weeks=4)`. No conditional lookback. |
| **What is needed** | Count distinct weeks of actuals per (user, project) pair. If ≥6 weeks of history exist, use 8-week lookback; otherwise 4-week lookback. |
| **Risk** | The 8-week lookback expands the `lookback_start` date, which changes the query. Ensure the table has sufficient data for resources onboarded recently. |

#### 3.3c PM forecast accuracy scoring

| | |
|---|---|
| **Status** | ❌ Not implemented in `forecast_resources.py` |
| **Evidence** | The `ai_pm_forecast_accuracy` table exists (confirmed at line 2165 of `create_views.sql` with columns: `week_start, pm_name, project_resource_combos, resources_forecasted, total_forecasted, total_actual, overall_pct, accuracy_score, narrative`). However, `forecast_resources.py` does not write to this table — the existing writing is done by `analyze_forecast.py` (separate Lambda function). |
| **Clarification needed ⚠️** | The requirement says "write to `ai_pm_forecast_accuracy`". Currently `analyze_forecast.py` likely owns this table. Confirm whether this enhancement should be added to `forecast_resources.py` (a pure algorithmic scoring without Bedrock) or remains in `analyze_forecast.py`. The table schema supports both. |
| **If added to `forecast_resources.py`** | After generating the forecast, group by `pm_name` (from `ps_resource_forecast_v2`), compare to actuals from `clockify_detailed_time_entries`, compute accuracy score, and upsert into `ai_pm_forecast_accuracy`. The `narrative` column can be left NULL (no Bedrock call). |

#### 3.3d Replace `practice_alignment ILIKE` with `practice_area IN ('PS', 'Both')`

| | |
|---|---|
| **Status** | ❌ Not yet — blocked on migration 066 |
| **Evidence** | `forecast_resources.py` lines 341–345 use five `ILIKE` patterns on `practice_alignment`. The new `practice_area` column (migration 066) would replace all five patterns with `WHERE practice_area IN ('PS', 'Both')`. |
| **Dependency** | Migration 066 must be applied AND the `practice_area` backfill must be validated before this code change is deployed. Deploying this Lambda change before the backfill is complete will silently drop PS resources from forecasts. |
| **Risk ⚠️** | This is a breaking change if deployed before the data is ready. Use a feature flag or deploy in two steps: (1) add column + backfill, (2) validate, (3) update Lambda. |

---

## 4. New QuickSight Datasets

### 4.1 `time-compliance-history` → `vw_time_compliance_history`

| | |
|---|---|
| **Status** | Blocked on migration 068 (view creation) |
| **What is needed** | New SPICE dataset in QuickSight pointing to `vw_time_compliance_history` via the RDS Data Source. Scheduled refresh: weekly (Monday after Lambda run). |

### 4.2 `utilization-history` → `vw_utilization_history`

| | |
|---|---|
| **Status** | Blocked on migration 069 (view creation) |
| **What is needed** | New SPICE dataset pointing to `vw_utilization_history`. Scheduled refresh: weekly. |

### 4.3 `ps-profitability-rates` → `ps_profitability_rates` JOIN `ps_resource_forecast_v2`

| | |
|---|---|
| **Status** | Blocked on migration 067 (table creation + rate data entry) |
| **What is needed** | New dataset with a custom SQL join: `SELECT f.*, r.onshore_rate, r.offshore_rate, r.contractor_rate, r.billable_rate FROM ps_resource_forecast_v2 f CROSS JOIN ps_profitability_rates r`. |
| **Note** | A CROSS JOIN is safe because `ps_profitability_rates` is a single-row config table. |

### 4.4 `mc-v2-audit` datasets — add artifact verification

| | |
|---|---|
| **Status** | Blocked on migration 070 (table creation) and Lambda change 3.2 (data population) |
| **What is needed** | Update the existing `mc-v2-audit` QuickSight dataset to JOIN `artifact_verification` on `jira_issue_id`. Add `artifact_present`, `artifact_url`, `artifact_verified_at` columns to the dataset. |

---

## 5. Existing Datasets Needing Updates

### 5.1 `project-time-detail` — add `user_name` field

| | |
|---|---|
| **Status** | ⚠️ Likely already in view; QuickSight dataset may not expose it |
| **Action** | (1) Confirm live view has `user_name`. (2) In QuickSight, edit the `project-time-detail` dataset, click "Add data", and include `user_name`. Trigger SPICE refresh. |

### 5.2 `time-compliance-current-week` — verify data source

| | |
|---|---|
| **Status** | ⚠️ Verify required |
| **Evidence** | The requirement warns this might point to `vw_missing_time_submissions` rather than `vw_weekly_compliance_report`. Both views exist. `vw_missing_time_submissions` returns only non-compliant users; `vw_weekly_compliance_report` returns ALL users (compliant + non-compliant) which is needed for rate calculations. Check the QuickSight dataset configuration. If it points to `vw_missing_time_submissions`, update it to `vw_weekly_compliance_report`. |

### 5.3 `productive-utilization` — verify category breakdown columns

| | |
|---|---|
| **Status** | ✅ View has all required columns |
| **Evidence** | `vw_productive_utilization` exports `billable_hours`, `nb_productive_hours`, `nb_non_productive_hours`, `non_logged_hours`. Verify the QuickSight dataset includes all four. If the dataset was created before these columns were added, a dataset schema refresh is needed. |

---

## 6. Prioritised Implementation Order

Dependencies flow top-to-bottom. Items at the same level can be parallelised.

```
Level 1 (Foundation — no dependencies)
├── Migration 066: ADD practice_area to clockify_users + backfill SQL
├── Migration 067: CREATE ps_profitability_rates + populate rates
└── Migration 070: CREATE artifact_verification table

Level 2 (Depends on Level 1)
├── Migration 068: CREATE vw_time_compliance_history  (can use practice_area filter)
├── Migration 069: CREATE vw_utilization_history       (wraps vw_productive_utilization)
├── Migration 071: UNIQUE constraint + dedup on ps_project_status (jira_issue_id, week_start)
└── Lambda 3.2: mc_v2_audit.py Confluence verification  (depends on migration 070)

Level 3 (Lambda changes — depends on Level 1 + Level 2 data validation)
├── Lambda 3.1: import_jira_data.py ON CONFLICT refactor  (depends on migration 071)
├── Lambda 3.3a: forecast_resources.py seasonal correction
├── Lambda 3.3b: forecast_resources.py dynamic lookback
├── Lambda 3.3c: forecast_resources.py PM accuracy scoring
└── Lambda 3.3d: forecast_resources.py practice_area filter  ← BLOCKED until 066 backfill validated

Level 4 (QuickSight — depends on all migrations + Lambdas deployed)
├── New dataset: time-compliance-history
├── New dataset: utilization-history
├── New dataset: ps-profitability-rates
├── Updated dataset: mc-v2-audit (add artifact columns)
├── Updated dataset: project-time-detail (add user_name)
├── Verify/update: time-compliance-current-week data source
└── Verify: productive-utilization column exposure
```

---

## 7. Migration Assignments Summary

| Migration # | Description | Type | Risk |
|---|---|---|---|
| 066 | ADD `practice_area` column to `clockify_users` + backfill | DDL + DML | Medium — requires human backfill validation |
| 067 | CREATE `ps_profitability_rates` single-row table | DDL | Low — net new table |
| 068 | CREATE `vw_time_compliance_history` | View | Low |
| 069 | CREATE `vw_utilization_history` | View | Low |
| 070 | CREATE `artifact_verification` table | DDL | Low — net new table |
| 071 | UNIQUE constraint on `ps_project_status(jira_issue_id, week_start)` + dedup | DDL | High — must dedup first |

---

## 8. Open Data Gaps

| # | Gap | Blocking | Resolution |
|---|---|---|---|
| DG-1 | `practice_area` values for existing users not in any document | Lambda 3.3d, compliance/utilisation history filters | Human review of backfill output from migration 066 |
| DG-2 | Actual rate values for `ps_profitability_rates` (onshore/offshore/contractor/billable) | QuickSight profitability dollar calculations | Business stakeholder to provide four rate figures |
| DG-3 | Confluence API token + base URL for artifact verification | Lambda 3.2 | DevOps to add `CONFLUENCE_API_TOKEN` and `CONFLUENCE_BASE_URL` to Secrets Manager and Lambda env |
| DG-4 | 18 months of Clockify history assumed for seasonal correction | Lambda 3.3a | Query `SELECT MIN(week_start) FROM clockify_detailed_time_entries` to confirm; if < 18 months, reduce lookback or skip seasonal correction |
| DG-5 | Ownership of `ai_pm_forecast_accuracy` writes | Lambda 3.3c | Clarify whether `forecast_resources.py` or `analyze_forecast.py` should own PM accuracy scoring to avoid duplicate writes |

---

## 9. Risk Register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R-1 | Lambda 3.3d deployed before practice_area backfill validated — PS resources silently dropped from forecasts | High | Feature-flag the new WHERE clause; validate backfill in staging first |
| R-2 | Migration 071 fails if duplicate (jira_issue_id, week_start) rows exist | High | Include dedup DELETE in the migration before adding the constraint |
| R-3 | Confluence verification Lambda timeout for large MC customers (50+ Done issues) | Medium | Limit verification to issues updated in last 30 days per run; use backoff |
| R-4 | `vw_project_time_detail` live view out of sync with `create_views.sql` | Medium | Re-apply view from `create_views.sql` via `apply_views.py` script before updating the QuickSight dataset |
| R-5 | `ps_profitability_rates` rate values populated as NULLs break QuickSight calculations | Low | Dashboard visuals must handle NULL rates with IFNULL/0 defaults |
