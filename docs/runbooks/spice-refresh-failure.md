# Runbook: SPICE Refresh Failure Recovery

## Identification

```bash
python3 scripts/check_spice_health.py
```

This script queries the QuickSight API for all datasets and reports ingestion status, last refresh time, and row counts. Look for datasets in `FAILED` or `CANCELLED` state, or with a `last_ingestion` timestamp older than 7 days on a Monday.

---

## Import-Critical Datasets (14)

These 14 datasets are refreshed every Monday by the Lambda import. A failure in any of them means dashboard consumers are seeing stale data.

| Dataset ID | Feeds |
|---|---|
| `kpi-weekly-snapshots-prod` | KPI Scorecard sheet, COO tiles (compliance, utilization, on-time delivery, escalations) |
| `ps-project-status-view` | PS Projects tab, project status indicators |
| `productive-utilization` | Utilization tab, resource utilization metrics |
| `clockify-missing-time-submissions-prod` | Missing Time tab (primary dataset) |
| `clockify-missing-time-submissions` | Missing Time tab (secondary / legacy) |
| `escalations-detail` | Escalations tab, open escalation counts |
| `ps-stage-trend` | PS Delivery Analysis, stage trend charts |
| `project-hours-summary-prod` | Project Hours Trend tab, summary view |
| `project-hours-current-week-prod` | Weekly Ops tab, current-week project breakdown |
| `mc-ticket-activity` | MC Delivery tab, ticket activity view |
| `mc-projects-at-risk` | MC Delivery tab, at-risk project list |
| `ps-projects-at-risk` | PS Projects tab, at-risk project list |
| `time-compliance-current-week` | Compliance tab, current-week compliance |
| `missing-time-history` | Missing Time tab, historical trend |

---

## Re-Trigger a Single Dataset

```bash
aws quicksight create-ingestion \
  --aws-account-id 961341524729 \
  --data-set-id <dataset-id> \
  --ingestion-id manual-$(date +%s) \
  --region us-east-1 \
  --profile AWSAdministratorAccess-961341524729
```

Replace `<dataset-id>` with one of the IDs from the table above (e.g., `kpi-weekly-snapshots-prod`).

Check ingestion status after ~2 minutes:

```bash
aws quicksight describe-ingestion \
  --aws-account-id 961341524729 \
  --data-set-id <dataset-id> \
  --ingestion-id manual-<timestamp> \
  --region us-east-1 \
  --profile AWSAdministratorAccess-961341524729
```

---

## Re-Trigger All 14 Datasets at Once

```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"refresh_quicksight","quicksight_dataset_ids":["kpi-weekly-snapshots-prod","ps-project-status-view","productive-utilization","clockify-missing-time-submissions-prod","clockify-missing-time-submissions","escalations-detail","ps-stage-trend","project-hours-summary-prod","project-hours-current-week-prod","mc-ticket-activity","mc-projects-at-risk","ps-projects-at-risk","time-compliance-current-week","missing-time-history"]}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/refresh.json && cat /tmp/refresh.json
```

Ingestions are asynchronous — the Lambda triggers them and returns immediately. Run `check_spice_health.py` again after 3–5 minutes to confirm completion.

---

## Common Failure Causes

### View Does Not Exist

**Error in QuickSight:** `ERROR: relation "vw_something" does not exist`

The underlying PostgreSQL view was dropped or never created. Apply it via Lambda:

```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"apply_views"}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/av.json && cat /tmp/av.json
```

Then re-trigger the affected dataset refresh.

### Column Mismatch

**Error in QuickSight:** `column "xyz" does not exist` or `invalid input syntax`

A view was updated but the QuickSight dataset still expects the old column name. Options:

1. Fix the view to restore the expected column name (preferred if the QuickSight dataset has downstream analyses)
2. Edit the QuickSight dataset to point to the new column name

Apply view fix via `apply_views` mode (see above), then re-trigger SPICE.

### VPC Connection Issue

**Error in QuickSight:** `Unable to connect to data source` or `Connection timed out`

The QuickSight VPC connection to the RDS instance is broken. Check:

1. RDS instance is running
2. QuickSight VPC connection (`weekly-reporting-vpc-connection`) is in `AVAILABLE` state in QuickSight → Manage QuickSight → VPC connections
3. RDS security group allows inbound from the QuickSight ENI IP range

This issue affects all datasets simultaneously. Once connectivity is restored, re-trigger all 14.

---

## Known Non-Critical Failing Datasets

These three datasets consistently fail because the underlying views do not exist in the production database. They are **not import-critical** — no active dashboard sheets depend on them. Do not spend time fixing them unless a new dashboard requirement is created.

| Dataset ID | Missing View | Status |
|---|---|---|
| `vw_daily_activity_trend` | `vw_daily_activity_trend` | View never created in production |
| `vw_import_activity` | `vw_import_activity` | View never created in production |
| `vw_skill_area_summary` | `vw_skill_area_summary` | View never created in production |

`check_spice_health.py` will flag these as FAILED — this is expected and can be ignored.
