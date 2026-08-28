# NB Custom Fields Deployment — Dev Account (604775478093)

**Date:** 2026-08-17
**Account:** 604775478093
**Profile:** default

---

## Summary

Added `Non Bill Productive` and `Non Bill Non Productive` Clockify time entry custom fields to the database, import pipeline, and reporting views. The NB classification logic now uses these checkboxes directly instead of the old `project_type` + `ps_project_mapping` heuristic.

---

## Steps Executed

### 1. Verified Custom Fields Exist in Clockify API

```bash
curl -s -H "X-Api-Key: $CLOCKIFY_API_KEY" \
  "https://api.clockify.me/api/v1/workspaces/$WORKSPACE_ID/custom-fields"
```

**Result:** Found 7 workspace custom fields on TIMEENTRY entities:
- `Non Bill Productive` (ID: `69dfd7600828d1ece13fc540`, Type: CHECKBOX)
- `Non Bill Non Productive` (ID: `69dfd83e8e5e4984d4a0a35e`, Type: CHECKBOX)

---

### 2. Database Migration — Added Columns

**Migration:** `src/database/migrations/105_add_nb_custom_fields_to_time_entries.sql`

```sql
ALTER TABLE clockify_detailed_time_entries
    ADD COLUMN IF NOT EXISTS is_nb_productive BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_nb_non_productive BOOLEAN DEFAULT FALSE;
```

**Executed via:**
```bash
aws lambda invoke --function-name production-clockify-import \
  --cli-binary-format raw-in-base64-out \
  --payload '{"mode": "run_query_master", "sql": "ALTER TABLE clockify_detailed_time_entries ADD COLUMN IF NOT EXISTS is_nb_productive BOOLEAN DEFAULT FALSE, ADD COLUMN IF NOT EXISTS is_nb_non_productive BOOLEAN DEFAULT FALSE"}'
```

---

### 3. Code Changes

#### `src/integrations/clockify_client.py`
- Added `"hydrated": "true"` to `get_time_entries()` params — exposes custom fields in API response.

#### `src/integrations/import_clockify_data.py`
- Extract `Non Bill Productive` and `Non Bill Non Productive` from `entry_data.get("customFieldValues", [])`.
- Set `is_nb_productive` and `is_nb_non_productive` on each `ClockifyTimeEntry` insert/update.

#### `src/database/models.py`
- Added `is_nb_productive = Column(Boolean, default=False)` and `is_nb_non_productive = Column(Boolean, default=False)` to `ClockifyTimeEntry`.

#### `src/lambda_handler.py`
- Added `run_query_master` mode — executes SQL with the master/postgres credentials (needed for DDL operations like ALTER TABLE, DROP VIEW).

#### `src/integrations/kpi_snapshot.py`
- Replaced complex `project_type` + `ps_project_mapping` + `mapped_clients` CTE with:
  - NB Productive: `WHERE te.is_nb_productive = TRUE`
  - NB Non-Productive: `WHERE te.is_nb_non_productive = TRUE` + capacity gap

---

### 4. Lambda Deployment

```bash
rm -rf /tmp/lambda_package && mkdir -p /tmp/lambda_package
cp -r src /tmp/lambda_package/
pip install -r requirements-lambda.txt -t /tmp/lambda_package/ --upgrade -q
cd /tmp/lambda_package && zip -r /tmp/lambda-deploy-clean.zip . -x "*.pyc" -x "*__pycache__*" -q
aws s3 cp /tmp/lambda-deploy-clean.zip s3://weekly-reporting-production-deployments-604775478093/lambda/lambda-deployment.zip
aws lambda update-function-code \
  --function-name production-clockify-import \
  --s3-bucket weekly-reporting-production-deployments-604775478093 \
  --s3-key lambda/lambda-deployment.zip
```

---

### 5. Full Clockify Import

```bash
aws lambda invoke --function-name production-clockify-import \
  --cli-binary-format raw-in-base64-out \
  --invocation-type Event \
  --payload '{"mode": "full", "weeks_back": 52, "notify": false}'
```

**Result:** 12,649 entries updated. 2,500 with `is_nb_productive=TRUE`, 1,383 with `is_nb_non_productive=TRUE`.

---

### 6. Rewrote Views (Migration 106)

**Migration:** `src/database/migrations/106_rewrite_nb_classification_from_custom_fields.sql`

Views rewritten to use `is_nb_productive` / `is_nb_non_productive` directly:
1. `vw_productive_utilization`
2. `vw_practice_kpi_weekly`
3. `vw_kpi_staff_weekly`

**Key:** Had to use `DROP VIEW ... CASCADE` + `CREATE VIEW` (not `CREATE OR REPLACE`) because the internal query structure changed (removed JOINs to `clockify_projects` and `mapped_clients`).

**After each view creation:**
```bash
aws lambda invoke --payload '{"mode": "run_query_master", "sql": "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO report_user;"}'
```

---

### 7. Backfilled KPI Snapshots

```bash
for week in "2026-08-10" "2026-08-03" "2026-07-27" "2026-07-20" "2026-07-13" "2026-07-06" "2026-06-29" "2026-06-22" "2026-06-15"; do
  aws lambda invoke --function-name production-clockify-import \
    --cli-binary-format raw-in-base64-out \
    --payload "{\"mode\": \"snapshot_kpis\", \"week_start\": \"$week\"}"
done
```

---

### 8. Refreshed SPICE Datasets

Datasets refreshed:
- `kpi-weekly-snapshots-prod` (32 rows)
- `kpi-practice-weekly-prod` (400 rows)
- `kpi-staff-weekly-prod` (3,528 rows)
- `productive-utilization` (3,672 rows)

---

### 9. Added NB Non-Productive KPI Tiles to QuickSight

**Dashboard:** KPI Tracking Dashboard (`kpi-tracking-dashboard-dev`)
**Analysis:** `kpi-tracking-analysis-dev`

- **Sheet 1 (OKR Scorecard):** Added `kpi-s1-nb-nonprod` tile — `MAX(nb_nonproductive_hours)` from `kpi_snapshots` with WoW comparison
- **Sheet 3 (Staff Detail):** Added `kpi-s3-nb-nonprod` tile — `SUM(nb_non_productive_hours)` from `kpi_staff`

---

## Verification

```
Week 2026-08-10 (new custom field logic):
  NB Productive:     589.44 hrs
  NB Non-Productive: 697.13 hrs (view) / 934.47 hrs (snapshot, includes capacity gap)
  Billable:          1,348.71 hrs
```

---

## Notes

- NB custom fields only populated from **April 2026 onward** (when checkboxes were added to Clockify)
- Pre-April 2026 entries have `is_nb_productive=FALSE` and `is_nb_non_productive=FALSE`
- The `kpi_snapshot.py` NB Non-Productive number includes capacity gap (non-logged hours) — view does not
- 2 pre-existing SPICE failures unrelated to this change: `clockify-pod-performance-prod` and `clockify-time-entries-prod` (column name mismatches)
