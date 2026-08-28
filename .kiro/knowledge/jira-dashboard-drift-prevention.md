# Dashboard Drift Prevention — Improvement Plan

## Overview

This document identifies points where the JIRA → PostgreSQL → QuickSight pipeline can silently drift (stale, incomplete, or inconsistent dashboard data) and proposes fixes for each.

---

## Problem 1: Fire-and-Forget SPICE Refresh (No Completion Verification)

**Current behavior:** `refresh_quicksight_datasets()` calls `create_ingestion()` and logs "triggered" but never checks whether the ingestion actually completed or failed. If SPICE refresh fails (throttling, data source error, timeout), the dashboard shows stale data with no alert.

**Impact:** Dashboards can display data that is hours or days old with no indication to users.

**Fix — Poll for ingestion completion:**

```python
def refresh_quicksight_datasets(dataset_ids: list, wait=True, timeout_sec=300):
    quicksight = boto3.client('quicksight')
    account_id = boto3.client('sts').get_caller_identity()['Account']
    results = []

    for dataset_id in dataset_ids:
        ingestion_id = f"ingestion-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{dataset_id}"
        try:
            quicksight.create_ingestion(
                DataSetId=dataset_id, IngestionId=ingestion_id, AwsAccountId=account_id
            )

            if wait:
                deadline = datetime.now().timestamp() + timeout_sec
                while datetime.now().timestamp() < deadline:
                    resp = quicksight.describe_ingestion(
                        DataSetId=dataset_id, IngestionId=ingestion_id, AwsAccountId=account_id
                    )
                    status = resp['Ingestion']['IngestionStatus']
                    if status == 'COMPLETED':
                        break
                    elif status in ('FAILED', 'CANCELLED'):
                        raise RuntimeError(
                            f"SPICE ingestion {status}: {resp['Ingestion'].get('ErrorInfo')}"
                        )
                    time.sleep(5)
                else:
                    raise TimeoutError(f"SPICE refresh timed out after {timeout_sec}s")

            results.append({'dataset_id': dataset_id, 'status': 'completed'})
        except Exception as e:
            results.append({'dataset_id': dataset_id, 'status': 'failed', 'error': str(e)})
            publish_metric('SPICERefreshFailure', dataset_id)

    return results
```

**Priority:** High  
**Effort:** Medium

---

## Problem 2: No Data Freshness Alarm

**Current behavior:** If EventBridge is disabled, Lambda times out, or Jira API credentials expire, dashboards silently go stale. Nobody knows until someone manually checks.

**Impact:** Up to 24+ hours of stale data before anyone notices.

**Fix — Data freshness canary:**

### Step A: Create a monitoring view

```sql
CREATE VIEW vw_data_freshness AS
SELECT
    'ps_project_status' AS source,
    MAX(synced_at) AS last_sync,
    NOW() - MAX(synced_at) AS age,
    CASE WHEN NOW() - MAX(synced_at) > INTERVAL '26 hours' THEN 'STALE' ELSE 'FRESH' END AS status
FROM ps_project_status
UNION ALL
SELECT
    'clockify_time_entries',
    MAX(synced_at),
    NOW() - MAX(synced_at),
    CASE WHEN NOW() - MAX(synced_at) > INTERVAL '26 hours' THEN 'STALE' ELSE 'FRESH' END
FROM clockify_detailed_time_entries;
```

### Step B: Add a canary Lambda (separate from the import Lambda)

- Runs every 4 hours via EventBridge
- Queries `vw_data_freshness`
- If any source is STALE → publish CloudWatch metric → triggers SNS alarm
- Decoupled from import so it detects failures even if the import Lambda is broken

**Priority:** High  
**Effort:** Low

---

## Problem 3: Import Succeeds with Zero Records (Silent No-Op)

**Current behavior:** If Jira returns zero issues (API auth expired, wrong project keys, Jira outage returning empty results), the import logs `status=success` with `records_imported=0`. No alarm fires.

**Impact:** Dashboard looks current (synced_at is fresh) but no new data was actually imported.

**Fix — Zero-record guard:**

```python
if len(issues) == 0 and not full_sync:
    last_import = get_last_ps_import_date(db)
    if last_import and (datetime.now() - last_import).days < 7:
        # Jira should have activity within a week — this is suspicious
        print("WARNING: Zero issues returned from Jira. Possible auth/connectivity issue.")
        publish_metric('JiraImportZeroRecords', 1)
        complete_import_log(db, log, 0, 0, 0, status='warning',
                          error='Zero records returned - possible Jira connectivity issue')
        return {'imported': 0, 'updated': 0, 'warning': 'zero_records'}
```

**Priority:** High  
**Effort:** Low

---

## Problem 4: Upsert Preserves Stale `client_name` / `project_name`

**Current behavior:** The `ON CONFLICT DO UPDATE` intentionally excludes `client_name` and `project_name` to protect manual normalizations. But if a Jira issue summary is updated (client renamed, project renamed), the dashboard keeps showing the old name forever.

**Impact:** Permanent name drift between Jira (source of truth) and the dashboard.

**Fix — Track divergence for review:**

### Step A: Schema change

```sql
ALTER TABLE ps_project_status 
    ADD COLUMN IF NOT EXISTS jira_client_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS jira_project_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS name_overridden BOOLEAN DEFAULT FALSE;
```

### Step B: On every import, write raw Jira values

Always write `jira_client_name` and `jira_project_name` from the latest Jira data (even if `client_name` is preserved).

### Step C: Flag divergence

```sql
UPDATE ps_project_status
SET name_overridden = TRUE
WHERE client_name IS DISTINCT FROM jira_client_name
   OR project_name IS DISTINCT FROM jira_project_name;
```

### Step D: Surface in Streamlit admin panel

Show a "Name Drift Review" section listing rows where `name_overridden = TRUE` so an admin can periodically confirm or accept the Jira-side rename.

**Priority:** Medium  
**Effort:** Low

---

## Problem 5: No Retry / Single Point of Failure Schedule

**Current behavior:** One EventBridge rule at 10:00 AM UTC. If it fails, there's no retry until the next day (24-hour gap).

**Impact:** A single Lambda timeout or transient error causes a full day of stale data.

**Fix — Add a catch-up rule:**

### CloudFormation addition

```yaml
JiraCatchupRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub ${Environment}-jira-catchup
    Description: Catch-up Jira import if 10 AM run missed (checks freshness first)
    ScheduleExpression: 'cron(0 16 ? * * *)'  # 4 PM UTC
    State: ENABLED
    Targets:
      - Arn: !GetAtt ImportLambdaFunction.Arn
        Id: JiraCatchupTarget
        Input: '{"mode":"jira_import","conditional":true,"max_age_hours":8,"refresh_quicksight":true}'
```

### Lambda logic

```python
if event.get('conditional'):
    max_age = event.get('max_age_hours', 8)
    last_import = get_last_ps_import_date(db)
    if last_import and (datetime.now() - last_import).total_seconds() < max_age * 3600:
        return {'statusCode': 200, 'body': 'Skipped - data is fresh'}
    # Otherwise proceed with import
```

**Priority:** Medium  
**Effort:** Low

---

## Problem 6: Snapshot Coupled to Import Atomicity

**Current behavior:** `_capture_stage_snapshot()` and `_capture_mc_ticket_snapshot()` run inside the import loop. If the Lambda is retried (timeout → EventBridge retry), snapshots could be captured from partially-imported data.

**Impact:** Historical trending data could be inaccurate for retried runs.

**Fix — Conditional snapshot capture:**

```python
# Only capture snapshot if import actually modified data
if imported_count + updated_count > 0:
    _capture_stage_snapshot(db, week_start)
    _capture_mc_ticket_snapshot(db, week_start)
```

The `ON CONFLICT DO UPDATE` in the snapshot tables already handles idempotency for duplicate runs within the same week — the fix is ensuring the trigger condition is sound.

**Priority:** Low  
**Effort:** Low

---

## Problem 7: View Schema Drift

**Current behavior:** Reporting views (`vw_ps_project_status`, etc.) are applied separately from column additions to `ps_project_status`. If someone adds a column via migration but doesn't re-apply the view, QuickSight datasets may break or miss data.

**Impact:** Broken or incomplete QuickSight datasets after schema changes.

**Fix — Pre-refresh view existence check:**

```python
# Before triggering QuickSight refresh
with engine.connect() as conn:
    view_check = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.views "
        "WHERE table_name = 'vw_ps_project_status'"
    )).scalar()
    if view_check == 0:
        raise RuntimeError(
            "Reporting view vw_ps_project_status missing — skipping SPICE refresh"
        )
```

Additionally, include view re-application as part of the deployment script (`cloudformation/deploy.sh`) so views are always in sync after any schema migration.

**Priority:** Low  
**Effort:** Low

---

## Implementation Priority Summary

| # | Fix | Priority | Effort | Impact |
|---|-----|----------|--------|--------|
| 1 | Verify SPICE ingestion completion + alarm on failure | **High** | Medium | Prevents stale dashboards going unnoticed |
| 2 | Data freshness canary Lambda + CloudWatch alarm | **High** | Low | Alerts within hours, not days |
| 3 | Zero-record guard on incremental import | **High** | Low | Catches auth/connectivity failures |
| 4 | Track `jira_client_name` divergence from `client_name` | **Medium** | Low | Prevents permanent name drift |
| 5 | Catch-up EventBridge rule | **Medium** | Low | 24h gap → 6h max gap |
| 6 | Conditional snapshot capture | **Low** | Low | Prevents partial-data snapshots on retries |
| 7 | View existence check before SPICE trigger | **Low** | Low | Prevents broken dataset refreshes |

---

## Recommended Implementation Order

1. **Quick wins (can be done in one session):** #3 (zero-record guard), #6 (conditional snapshot)
2. **High-value monitoring (next session):** #2 (freshness canary), #1 (SPICE verification)
3. **Resilience (following session):** #5 (catch-up rule), #4 (name drift tracking)
4. **Hardening:** #7 (view check)
