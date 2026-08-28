# Runbook: Monday Import Failure Recovery

## Detection

A Monday import failure can be detected by any of:

- **CloudWatch alarm** — `ClockifyImportErrors` or `ClockifyImportDuration` alarm fires
- **SNS notification** — email from `weekly-reporting-alerts` SNS topic
- **No SPICE refresh by 10:00 AM CT Monday** — QuickSight dashboards show stale data (prior week's numbers)

## First Diagnostics

Run these three checks before attempting any fix:

```bash
# 1. Confirm Lambda was recently deployed / last modified
aws lambda get-function-configuration \
  --function-name production-clockify-import \
  --query 'LastModified' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

# 2. Full Monday readiness check (EventBridge rule, DB connectivity, Clockify auth)
python3 scripts/verify_monday_readiness.py

# 3. SPICE dataset health — shows which datasets are stale or failed
python3 scripts/check_spice_health.py
```

Review the output of all three before proceeding to the failure-specific fixes below.

---

## Failure Modes and Fixes

### 1. Lambda Timeout (900-second limit)

**Symptoms:** CloudWatch shows `Task timed out after 900.00 seconds`. Lambda execution record shows `Status: timeout`.

**Fix:**

```bash
# Check CloudWatch logs for where it timed out
aws logs tail /aws/lambda/production-clockify-import \
  --since 3h \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

# Re-invoke with a smaller lookback window to catch up incrementally
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"incremental","weeks_back":1,"notify":true}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/retry.json && cat /tmp/retry.json
```

Repeat with `weeks_back` increasing (1 → 2 → 4) until fully caught up.

---

### 2. Clockify API Rate Limit

**Symptoms:** Lambda logs contain `429 Too Many Requests` or `Rate limit exceeded`. Import completes partially.

**Fix:** Wait 1 hour, then re-invoke incremental:

```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"incremental","notify":true}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/retry.json && cat /tmp/retry.json
```

---

### 3. RDS Connection Failure

**Symptoms:** Lambda logs contain `could not connect to server`, `Connection refused`, or `SSL connection has been closed unexpectedly`.

**Checks:**

1. Verify RDS instance is running in the AWS Console → RDS → `weekly-reporting-production`
2. Verify Lambda's security group allows outbound to RDS security group on port 5432
3. Verify RDS security group allows inbound from Lambda security group on port 5432

```bash
# Check RDS instance status
aws rds describe-db-instances \
  --db-instance-identifier weekly-reporting-production \
  --query 'DBInstances[0].DBInstanceStatus' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

Once connectivity is confirmed, re-invoke incremental import (see §2 above).

---

### 4. SPICE Ingestion Failed

**Symptoms:** `check_spice_health.py` shows one or more datasets in `FAILED` state. QuickSight dashboards show stale data.

**Fix — identify then re-trigger:**

```bash
# See which datasets failed and why
python3 scripts/check_spice_health.py

# Re-trigger all import-critical datasets via Lambda
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"refresh_quicksight","quicksight_dataset_ids":["kpi-weekly-snapshots-prod","ps-project-status-view","productive-utilization","clockify-missing-time-submissions-prod","clockify-missing-time-submissions","escalations-detail","ps-stage-trend","project-hours-summary-prod","project-hours-current-week-prod","mc-ticket-activity","mc-projects-at-risk","ps-projects-at-risk","time-compliance-current-week","missing-time-history"]}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/refresh.json && cat /tmp/refresh.json
```

See `docs/runbooks/spice-refresh-failure.md` for per-dataset details and known non-critical failures.

---

### 5. KPI Snapshot Stale

**Symptoms:** `check_spice_health.py` shows `kpi-weekly-snapshots-prod` is current, but KPI values in the dashboard are from a prior week. `kpi_weekly_snapshots` table has no row for the current `week_start`.

**Fix:**

```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"snapshot_kpis"}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/kpi.json && cat /tmp/kpi.json
```

---

### 6. EventBridge Rule Disabled

**Symptoms:** `verify_monday_readiness.py` reports the EventBridge rule is disabled or `check_spice_health.py` shows no ingestion was ever triggered.

**Fix:**

```bash
aws events enable-rule \
  --name clockify-weekly-import-monday \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

Also check the noon rule (KPI snapshot):

```bash
aws events enable-rule \
  --name clockify-weekly-import-monday-noon \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

---

## Manually Triggering the Full Monday Sequence

Use this when the automated run did not complete and you need to run the full Monday sequence by hand.

```bash
# Step 1: Full weekly import (Clockify data + SPICE refresh)
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"weekly","weeks_back":2,"notify":true,"refresh_quicksight":true,"quicksight_dataset_ids":["kpi-weekly-snapshots-prod","ps-project-status-view","productive-utilization","clockify-missing-time-submissions-prod","clockify-missing-time-submissions","escalations-detail","ps-stage-trend","project-hours-summary-prod","project-hours-current-week-prod","mc-ticket-activity","mc-projects-at-risk","ps-projects-at-risk","time-compliance-current-week","missing-time-history"]}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/weekly.json && cat /tmp/weekly.json

# Step 2: KPI snapshot (runs at noon — do this after Step 1 completes)
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"snapshot_kpis"}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/kpi.json && cat /tmp/kpi.json

# Step 3: Verify SPICE datasets are healthy
python3 scripts/check_spice_health.py
```

Wait for each step to return before proceeding. Lambda invoke is synchronous for payloads under 6 MB — the response file will contain the function result including any errors.

---

## Post-Recovery Verification Checklist

- [ ] `check_spice_health.py` shows all 14 import-critical datasets as `COMPLETED` with today's timestamp
- [ ] `verify_monday_readiness.py` passes all checks
- [ ] QuickSight COO Operational Dashboard — "Data as of" shows today's date
- [ ] KPI Scorecard sheet shows current week values (not prior week)
- [ ] Missing Time Submissions tab shows current week's data
- [ ] CloudWatch log group `/aws/lambda/production-clockify-import` shows successful completion (no ERROR lines in the last invocation)
