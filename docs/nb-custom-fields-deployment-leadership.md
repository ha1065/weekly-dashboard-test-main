# NB Custom Fields Deployment — Leadership Account (961341524729)

**Date:** 2026-08-18
**Account:** 961341524729
**Profile:** leadership

---

## Summary

Same deployment as dev account — added `Non Bill Productive` and `Non Bill Non Productive` Clockify custom fields to the database, import pipeline, and reporting views. Also fixed the week filter scope on the COO Operational Dashboard so NB tiles respond to the date picker.

---

## Steps Executed

### 1. Lambda Deployment

```bash
aws s3 cp /tmp/lambda-deploy-clean.zip s3://weekly-reporting-production-deployments-961341524729/lambda/lambda-deployment.zip --profile leadership
aws lambda update-function-code \
  --function-name production-clockify-import \
  --s3-bucket weekly-reporting-production-deployments-961341524729 \
  --s3-key lambda/lambda-deployment.zip \
  --profile leadership --region us-east-1
```

**Note:** Code size went from 56MB → 21MB (was previously packaged with unnecessary dependencies).

---

### 2. Database Migration

```bash
aws lambda invoke --function-name production-clockify-import \
  --cli-binary-format raw-in-base64-out \
  --profile leadership --region us-east-1 \
  --payload '{"mode": "run_query_master", "sql": "ALTER TABLE clockify_detailed_time_entries ADD COLUMN IF NOT EXISTS is_nb_productive BOOLEAN DEFAULT FALSE, ADD COLUMN IF NOT EXISTS is_nb_non_productive BOOLEAN DEFAULT FALSE"}'
```

---

### 3. Full Clockify Import

```bash
aws lambda invoke --function-name production-clockify-import \
  --cli-binary-format raw-in-base64-out \
  --invocation-type Event \
  --profile leadership --region us-east-1 \
  --payload '{"mode": "full", "weeks_back": 52, "notify": false}'
```

**Result:** 43,102 total entries. 2,509 with `is_nb_productive=TRUE`, 1,399 with `is_nb_non_productive=TRUE`.

**Note:** Lambda timed out (900s) during the Jira/AI analysis phase, but Clockify time entry import had already committed.

---

### 4. Rewrote Views

**Critical:** `CREATE OR REPLACE VIEW` silently fails if the internal query structure changes (different JOINs). Must use `DROP VIEW ... CASCADE` + `CREATE VIEW`.

Views rewritten:
1. `vw_productive_utilization` — `DROP CASCADE` + `CREATE`
2. `vw_practice_kpi_weekly` — `DROP CASCADE` + `CREATE`
3. `vw_kpi_staff_weekly` — `DROP CASCADE` + `CREATE`

**Cascading dependency fixed:** `vw_utilization_history` was dropped by CASCADE (it depends on `vw_productive_utilization`). Had to recreate it:

```sql
CREATE VIEW vw_utilization_history AS
SELECT pu.*,
    TO_CHAR(pu.week_start, 'Mon YYYY') AS month_label,
    EXTRACT(YEAR FROM pu.week_start)::INTEGER AS year_num,
    EXTRACT(MONTH FROM pu.week_start)::INTEGER AS month_num,
    EXTRACT(QUARTER FROM pu.week_start)::INTEGER AS quarter_num,
    CONCAT('Q', EXTRACT(QUARTER FROM pu.week_start)::INTEGER, ' ', EXTRACT(YEAR FROM pu.week_start)::INTEGER) AS quarter_label
FROM vw_productive_utilization pu;
```

**After each view creation:**
```bash
aws lambda invoke --payload '{"mode": "run_query_master", "sql": "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO report_user;"}'
```

---

### 5. Backfilled KPI Snapshots

```bash
for week in "2026-08-10" "2026-08-03" "2026-07-27" "2026-07-20" "2026-07-13" "2026-07-06" "2026-06-29" "2026-06-22"; do
  aws lambda invoke --function-name production-clockify-import \
    --cli-binary-format raw-in-base64-out \
    --profile leadership --region us-east-1 \
    --payload "{\"mode\": \"snapshot_kpis\", \"week_start\": \"$week\"}"
done
```

---

### 6. Refreshed SPICE Datasets

Datasets refreshed:
- `productive-utilization` (1,830 rows) ✅
- `utilization-history` (1,830 rows) ✅
- `kpi-weekly-snapshots-prod` (33 rows) ✅
- `kpi-practice-weekly-prod` (424 rows) ✅
- `kpi-staff-weekly-prod` (3,710 rows) ✅

---

### 7. Fixed COO Dashboard — Week Filter Scope

**Problem:** The NB KPI tiles on the "Time & Utilization" sheet (`kpi-tu-nb-productive`, `kpi-tu-nb-nonproductive`) were NOT included in the week date filter (`fg-kpi-s5`). They showed unfiltered MAX across all weeks — appearing as stale old values.

**Fix:** Added the NB visuals to the filter group's `VisualIds` scope:

```python
# Before: ['kpi-tu-billable', 'kpi-tu-compliance', 'kpi-tu-presales']
# After:  ['kpi-tu-billable', 'kpi-tu-compliance', 'kpi-tu-presales', 'kpi-tu-nb-productive', 'kpi-tu-nb-nonproductive', 'kpi-tu-missing']
```

---

### 8. Restored Dashboard Theme

**Problem:** The `update_dashboard` call without `ThemeArn` parameter dropped the purple Cloudelligent brand theme.

**Fix:** Re-published with theme:
```python
qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId='coo-operational-dashboard-prod',
    Name='COO Operational Dashboard',
    Definition=defn,
    ThemeArn='arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'
)
```

**Final published version:** 38

---

## Verification

```
Week 2026-08-10 (leadership account, new custom field logic):
  NB Productive:     557.46 hrs (view) / 606.96 hrs (snapshot)
  NB Non-Productive: 749.63 hrs (view) / 874.70 hrs (snapshot, includes capacity gap)
  Billable:          1,420.96 hrs
```

---

## Data Availability

| Period | NB Custom Fields Available? |
|--------|---------------------------|
| Jan 2025 – Mar 2026 | ❌ All FALSE (checkboxes didn't exist in Clockify) |
| Apr 2026 | First entries (76 productive, 64 non-productive) |
| May 2026+ | Fully adopted |

---

## COO Dashboard — NB Visual Locations

| Sheet | Visual ID | Title | Dataset |
|-------|-----------|-------|---------|
| Weekly Pulse | `kpi-wp-nb-productive` | NB Productive Hrs | kpi_snapshots |
| Weekly Pulse | `kpi-wp-nb-nonproductive` | NB Non-Productive Hrs | kpi_snapshots |
| Time & Utilization | `kpi-tu-nb-productive` | NB Productive Hrs | kpi_snapshots |
| Time & Utilization | `kpi-tu-nb-nonproductive` | NB Non-Productive Hrs | kpi_snapshots |
| Time & Utilization | `tbl-util` | Productive Utilization by Person | productive_util |
| Utilization History | `kpi-uh-nb-productive` | Latest Week Avg NB Productive Hours | util_history |
| Utilization History | `line-uh-trend` | Weekly Utilization Trend | util_history |

---

## Lessons Learned

1. **`CREATE OR REPLACE VIEW` silently fails** if the internal query changes (different JOINs/CTEs). Always `DROP CASCADE` + `CREATE` when rewriting view logic.
2. **Cascading drops** — check dependent views before DROP CASCADE. In this case `vw_utilization_history` depended on `vw_productive_utilization`.
3. **`kpi_weekly_snapshots` is a pre-computed table** — changing views doesn't update it. Must re-run `snapshot_kpis` mode for each week.
4. **Dashboard filter scopes** — new KPI tiles added to a sheet don't automatically inherit existing filter groups. Must manually add visual IDs to the filter scope.
5. **Always pass `ThemeArn`** when calling `update_dashboard` — omitting it resets to default QuickSight theme.
6. **Account data differences** — dev has 14K entries (shorter history), leadership has 43K (full year). Numbers won't match exactly.
