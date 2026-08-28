# Monitoring & Alerting Setup — 2026-07-07

## Summary

Implemented CloudWatch alarms and log metric filters for the `weekly-reporting-production` system. All alerts route to the existing SNS topic which is subscribed by `chris.xenos@cloudelligent.com`.

**Critical finding:** The pre-existing `production-import-lambda-errors` alarm had **no SNS action** — it was in `ALARM` state at 12:15 PM ET today (Lambda errored at 16:10 UTC) and nobody was notified. This has been fixed.

---

## SNS Topic

| Field | Value |
|-------|-------|
| Topic name | `production-weekly-reporting-notifications` |
| Topic ARN | `arn:aws:sns:us-east-1:961341524729:production-weekly-reporting-notifications` |

### Current Email Subscriptions

| Endpoint | Protocol | Status |
|----------|----------|--------|
| `chris.xenos@cloudelligent.com` | email | Confirmed |

### How to Add a New Email Subscriber

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:961341524729:production-weekly-reporting-notifications \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

The recipient will receive a confirmation email they must click to activate. Subscription is pending until confirmed.

---

## CloudWatch Log Metric Filters

Two metric filters were created on `/aws/lambda/production-clockify-import`:

| Filter Name | Pattern | Metric | Namespace |
|-------------|---------|--------|-----------|
| `weekly-reporting-spice-errors` | `?SPICE ?ingestion ?QuickSight ?"refresh failed" ?"dataset refresh"` | `SPICEErrors` | `WeeklyReporting` |
| `weekly-reporting-import-errors` | `?ERROR ?Exception ?"import failed" ?Traceback ?"raise " ?CRITICAL` | `ImportErrors` | `WeeklyReporting` |

These emit custom metrics to the `WeeklyReporting` namespace whenever matching log lines appear. The alarms below fire on those metrics.

---

## CloudWatch Alarms

### 1. `production-import-lambda-errors` *(pre-existing — fixed)*

| Field | Value |
|-------|-------|
| Status | `ALARM` (Lambda errored today at 16:10 UTC) |
| Trigger | `AWS/Lambda Errors >= 1` in any 5-min window |
| Lambda | `production-clockify-import` |
| Fix applied | Added SNS action + OK action (was empty — alarm fired silently) |
| Covers failure mode | Lambda throws an unhandled exception |

### 2. `weekly-reporting-lambda-duration-warning` *(new)*

| Field | Value |
|-------|-------|
| Status | `INSUFFICIENT_DATA` (normalizes after first invocation) |
| Trigger | `AWS/Lambda Duration (Maximum) >= 800,000 ms` (800 seconds) in any 60-sec window |
| Lambda | `production-clockify-import` |
| Threshold rationale | 15-min timeout = 900,000 ms; 800s gives ~100s of warning buffer |
| Covers failure mode | Lambda approaching timeout during Bedrock AI analysis |

### 3. `weekly-reporting-lambda-not-invoked` *(new)*

| Field | Value |
|-------|-------|
| Status | `INSUFFICIENT_DATA` |
| Trigger | `AWS/Lambda Invocations (Sum) < 1` over a 7-day rolling window (604,800s — CloudWatch maximum) |
| `treat-missing-data` | `breaching` — if no data reported, alarm fires |
| Lambda | `production-clockify-import` |
| Covers failure mode | Monday import missed entirely due to disabled/misconfigured EventBridge rule |
| Note | CloudWatch enforces a 7-day max window. Alarm fires at latest by Tuesday if Monday import was missed. |

### 4. `weekly-reporting-lambda-concurrent-executions` *(new)*

| Field | Value |
|-------|-------|
| Status | `INSUFFICIENT_DATA` |
| Trigger | `AWS/Lambda ConcurrentExecutions (Maximum) >= 2` in any 60-sec window |
| Lambda | `production-clockify-import` |
| Covers failure mode | Duplicate EventBridge target causes two simultaneous import runs |

### 5. `weekly-reporting-spice-failure` *(new)*

| Field | Value |
|-------|-------|
| Status | `INSUFFICIENT_DATA` |
| Trigger | `WeeklyReporting/SPICEErrors >= 1` in any 5-min window (feeds from log metric filter) |
| Covers failure mode | SPICE dataset ingestion fails silently — QuickSight dashboards show stale data |

### 6. `weekly-reporting-import-errors` *(new)*

| Field | Value |
|-------|-------|
| Status | `INSUFFICIENT_DATA` |
| Trigger | `WeeklyReporting/ImportErrors >= 3` in any 5-min window (feeds from log metric filter) |
| Threshold rationale | 3 to reduce noise from transient warnings; 1 would be too sensitive |
| Covers failure mode | General error patterns in Lambda logs (exceptions, tracebacks, CRITICAL logs) |

---

## Coverage Matrix

| Failure Mode | Alarm(s) |
|---|---|
| Lambda throws unhandled exception | `production-import-lambda-errors` |
| Lambda times out (Bedrock AI) | `weekly-reporting-lambda-duration-warning` → then `production-import-lambda-errors` on timeout |
| SPICE dataset fails silently | `weekly-reporting-spice-failure` + `weekly-reporting-import-errors` |
| Import runs but 0 records (duplicate target) | `weekly-reporting-lambda-concurrent-executions` + `production-import-lambda-errors` |
| KPI snapshot not written | `weekly-reporting-import-errors` (if script logs an error) |
| Monday import missed entirely | `weekly-reporting-lambda-not-invoked` (fires by Tuesday at latest) |

---

## IaC Drift — Items to Add to `cloudformation/template.yaml`

The template has been updated in this session to reflect the live state. The following changes were made to `cloudformation/template.yaml`:

### Changes made to template.yaml

1. **`ImportLambdaErrorAlarm`** — added `AlarmActions` and `OKActions` pointing to `!Ref NotificationTopic` (was missing — alarm fired silently)

2. **Added `SPICEErrorMetricFilter`** — `AWS::Logs::MetricFilter` for SPICE/QuickSight error patterns

3. **Added `ImportErrorMetricFilter`** — `AWS::Logs::MetricFilter` for general error patterns (ERROR, Exception, Traceback, CRITICAL)

4. **Added `LambdaDurationWarningAlarm`** — Duration >= 800s warning

5. **Added `LambdaNotInvokedAlarm`** — 0 invocations over 7-day window

6. **Added `LambdaConcurrentExecutionsAlarm`** — ConcurrentExecutions >= 2

7. **Added `SPICEFailureAlarm`** — fires on `WeeklyReporting/SPICEErrors` custom metric

8. **Added `ImportErrorsAlarm`** — fires on `WeeklyReporting/ImportErrors` custom metric (threshold: 3)

> **Note:** These resources were created live via CLI and then back-ported to the template. Running `cdk deploy` or a CloudFormation stack update will attempt to create them again and may conflict with existing resource names. Review the template before deploying — the new alarms use hardcoded names (not `!Sub ${Environment}-*`) for the `weekly-reporting-*` prefix. You may want to rename them to use `!Sub` if multi-environment support is needed.

---

## Recommended Next Steps

### Immediate

1. **Investigate today's Lambda error** — `production-import-lambda-errors` is in ALARM right now (error at 16:10 UTC today). Check the Lambda logs:
   ```bash
   aws logs tail /aws/lambda/production-clockify-import \
     --since 4h \
     --profile AWSAdministratorAccess-961341524729 \
     --region us-east-1
   ```

2. **Run post-import health check** — after every Monday import, run:
   ```bash
   python verify_monday_readiness.py
   ```
   This validates record counts, KPI snapshot, and SPICE refresh status.

3. **Add additional email subscribers** — if other team members should receive alerts, use the `aws sns subscribe` command above.

### Future Sprints

4. **0-record import alarm** — there's no alarm for "Lambda ran but imported 0 records". This requires a custom metric emitted by the Lambda itself (e.g., `metrics.put_metric_data(MetricName='RecordsImported', Value=count)`). Add this to the Lambda code and create a corresponding `RecordsImported < 1` alarm.

5. **KPI snapshot alarm** — similarly, the Lambda should emit a `KPISnapshotWritten` metric (1 on success, 0 on failure) so an alarm can detect the "snapshot not written" failure mode directly.

6. **CloudFormation stack update** — reconcile the template changes with a `deploy.sh` run to bring IaC fully in sync. Verify no naming conflicts before deploying.

---

## Quick Reference — All Active Alarms

```bash
# View all weekly-reporting alarms and their current state
aws cloudwatch describe-alarms \
  --alarm-name-prefix weekly-reporting \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue}'

# Also check the pre-existing alarm
aws cloudwatch describe-alarms \
  --alarm-names production-import-lambda-errors \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue}'
```
