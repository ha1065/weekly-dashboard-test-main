# CloudWatch Log Retention Drift Fix — 2026-07-07

**Date:** 2026-07-07  
**Performed by:** AWS Solutions Architect  
**Account:** 961341524729  
**Region:** us-east-1  
**Stack affected:** weekly-reporting-production

---

## Summary

A rogue EventBridge rule (`cloudwatch-retention-enforcement-schedule`) was running daily and enforcing 3-day retention on **every log group in the account**. This was overriding CloudFormation-specified retention values and permanently deleting logs before they could be used for debugging. The rule was deployed via a StackSet (`StackSet-cloudwatch-retention-enforcement-*`) — it is not part of the `weekly-reporting-production` stack and has no business ownership.

The rule has been disabled and all four `weekly-reporting-production` project log groups have been restored to 30-day retention.

---

## 1. Findings

| # | Severity | Resource | Finding | Root Cause |
|---|----------|----------|---------|------------|
| 1 | **Critical** | `/aws/lambda/production-clockify-import` | Live retention = 3 days; CloudFormation `ImportLambdaLogGroup` specifies `RetentionInDays: 30` | `cloudwatch-retention-enforcement-schedule` EventBridge rule fires `rate(1 day)` and invokes `cloudwatch-retention-enforcement` Lambda with `RETENTION_DAYS=3`, overwriting all log groups account-wide |
| 2 | **Critical** | `/aws/rds/instance/production-weekly-reporting/postgresql` | Live retention = 3 days | Same enforcement Lambda — no CloudFormation resource governs this log group, but 3 days is too short for DB query debugging |
| 3 | **High** | `/aws/ecs/containerinsights/production-weekly-reporting/performance` | Live retention = 3 days | Same enforcement Lambda |
| 4 | **High** | `/ecs/production-weekly-reporting-dashboard` | Live retention = 3 days | Same enforcement Lambda |
| 5 | **High** | All other log groups in account (50+) | Live retention = 3 days on every log group | Enforcement Lambda has `RETENTION_DAYS=3` hardcoded as an environment variable and iterates all log groups; no include/exclude list |
| 6 | **Medium** | IaC drift | `ImportLambdaLogGroup` in CloudFormation specifies 30 days but live value was 3 days until this fix | Daily override by StackSet-deployed enforcement Lambda |

### Rogue Rule Details

| Property | Value |
|----------|-------|
| Rule name | `cloudwatch-retention-enforcement-schedule` |
| Schedule | `rate(1 day)` |
| State (before fix) | `ENABLED` |
| Target Lambda | `arn:aws:lambda:us-east-1:961341524729:function:cloudwatch-retention-enforcement` |
| Target ID | `RetentionEnforcementTarget` |
| Lambda env var | `RETENTION_DAYS=3` |
| Lambda runtime | Python 3.12 |
| Lambda deployed by | StackSet `StackSet-cloudwatch-retention-enforcement-6f388350-82f6-4d62-980c-2a4b13079a63` |
| StackSet tag | `aws-apn-id: pc:7dc4j6pmzicdew9fctd2db8fi` |

The enforcement Lambda was deployed by a CloudFormation StackSet — likely an AWS Partner Network (APN) or AWS-managed compliance tool (`aws-apn-id` tag), **not** a manual action. It has no awareness of per-log-group retention requirements and applies a single 3-day value universally.

---

## 2. Fix Applied

### Step 1 — Disabled the EventBridge rule

```bash
aws events disable-rule \
  --name cloudwatch-retention-enforcement-schedule \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

**Result:** Rule state changed from `ENABLED` → `DISABLED`. The Lambda will no longer fire daily.

### Step 2 — Restored 30-day retention on all project log groups

```bash
# Primary Lambda (CloudFormation-managed — must match ImportLambdaLogGroup RetentionInDays: 30)
aws logs put-retention-policy \
  --log-group-name /aws/lambda/production-clockify-import \
  --retention-in-days 30 \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

# RDS PostgreSQL logs
aws logs put-retention-policy \
  --log-group-name /aws/rds/instance/production-weekly-reporting/postgresql \
  --retention-in-days 30 \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

# ECS Container Insights
aws logs put-retention-policy \
  --log-group-name /aws/ecs/containerinsights/production-weekly-reporting/performance \
  --retention-in-days 30 \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1

# ECS Dashboard
aws logs put-retention-policy \
  --log-group-name /ecs/production-weekly-reporting-dashboard \
  --retention-in-days 30 \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

---

## 3. Verification — Before and After

| Log Group | Before (live) | After (live) | CloudFormation spec |
|-----------|--------------|-------------|---------------------|
| `/aws/lambda/production-clockify-import` | 3 days | **30 days** ✅ | 30 days (`ImportLambdaLogGroup`) |
| `/aws/rds/instance/production-weekly-reporting/postgresql` | 3 days | **30 days** ✅ | Not explicitly set in CFN |
| `/aws/ecs/containerinsights/production-weekly-reporting/performance` | 3 days | **30 days** ✅ | Not explicitly set in CFN |
| `/ecs/production-weekly-reporting-dashboard` | 3 days | **30 days** ✅ | Not explicitly set in CFN |

### EventBridge rule state verification

```
Name:  cloudwatch-retention-enforcement-schedule
State: DISABLED  ✅
```

---

## 4. IaC Drift Notes

| Item | Status |
|------|--------|
| `ImportLambdaLogGroup.RetentionInDays` in `template.yaml` | Correctly set to `30`. No change needed. |
| RDS, ECS log groups | Not declared in `template.yaml`. Retention was fixed directly. Consider adding explicit `AWS::Logs::LogGroup` resources for these in the stack to prevent future drift. |
| `cloudwatch-retention-enforcement-schedule` EventBridge rule | **Not in `template.yaml`** — deployed by external StackSet. Do not add to the weekly-reporting stack. |
| `cloudwatch-retention-enforcement` Lambda | **Not in `template.yaml`** — deployed by external StackSet. Do not manage it here. |

**`template.yaml` requires no changes.** The CloudFormation spec was already correct at 30 days.

---

## 5. Recommendations

### Immediate (done)
- ✅ Disabled `cloudwatch-retention-enforcement-schedule` rule
- ✅ Restored 30-day retention on all 4 project log groups

### Short-term
1. **Investigate the StackSet owner.** The `aws-apn-id: pc:7dc4j6pmzicdew9fctd2db8fi` tag suggests this was deployed by an AWS Partner tool (possibly a cost optimization or compliance scanner). Identify who owns it and whether `RETENTION_DAYS=3` is intentional for the rest of the account. If a different retention value is desired globally, the enforcement Lambda's `RETENTION_DAYS` environment variable should be updated.

2. **Add explicit log group resources for RDS and ECS to `template.yaml`.** This makes CloudFormation the authoritative source for retention on all project log groups, so `cfn-drift-detection` will catch future overrides:
   ```yaml
   RDSLogGroup:
     Type: AWS::Logs::LogGroup
     Properties:
       LogGroupName: /aws/rds/instance/production-weekly-reporting/postgresql
       RetentionInDays: 30

   ECSContainerInsightsLogGroup:
     Type: AWS::Logs::LogGroup
     Properties:
       LogGroupName: /aws/ecs/containerinsights/production-weekly-reporting/performance
       RetentionInDays: 30

   ECSDashboardLogGroup:
     Type: AWS::Logs::LogGroup
     Properties:
       LogGroupName: /ecs/production-weekly-reporting-dashboard
       RetentionInDays: 30
   ```

3. **Add a CloudFormation drift detection check to the pre-deploy script** (`scripts/check_eventbridge_targets.py` or a new script) that also verifies log group retention matches the template values before any deploy.

### Long-term
- If the account-wide enforcement Lambda is re-enabled in the future with a corrected value (e.g., 30 or 90 days), ensure the `RETENTION_DAYS` environment variable is updated before re-enabling, or add an exclude-list mechanism so it skips log groups already managed by CloudFormation.
