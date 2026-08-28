# AWS Deployment Evaluation — Sprint 3–5 Recommendations
**Date:** 2026-06-26  
**Reviewer:** AWS Architect  
**Account:** 961341524729 | us-east-1  
**Sprint:** 3 started Jun 25 — evaluating before feature work proceeds

---

## 1. Critical Risks — Must Address Before Sprint 3 Feature Work

Three conditions in the current deployment create immediate risk of either a production outage or data loss if `aws cloudformation deploy` is run without preparation. These are not scheduling suggestions — they are blockers.

### 1.1 CloudFormation Drift Is the #1 Deployment Risk

All four stacks are `NOT_CHECKED`. The live EventBridge rules have **materially different payloads** from what the CloudFormation template defines. Specifically:

- The CF template's `ImportScheduleRule9AM` uses `{"mode":"weekly","weeks_back":2,...}` — the live rule contains a full `quicksight_dataset_ids` list with 14 dataset IDs that took weeks to compile.
- The CF template's `ImportScheduleRuleNoon` uses a simplified payload — the live rule has `snapshot_kpis:true` and the same 14 dataset IDs.
- Three compliance email rules exist only as script-managed resources, not in CF. A stack update would not delete them (CF only manages what it knows about), but any change to the Lambda function ARN would break the target and silently stop compliance emails.

**If you run `aws cloudformation deploy` on `weekly-reporting-production` today, the live EventBridge payloads will be overwritten by the simplified CF payloads. The 9am import will run but will not trigger a SPICE refresh. The Monday data pipeline will partially fail silently.**

The IaC story S3-08 (EventBridge import into CF) is correctly sequenced in Sprint 3, but it must be completed and verified before any other stack update is attempted.

### 1.2 Lambda Code Deployment Is Completely Decoupled from CloudFormation

The live Lambda (`production-clockify-import`) is deployed via `scripts/update_lambda_and_apply_views.sh` — direct S3 upload + `update-function-code`. The CloudFormation template references an S3 `LambdaCodeKey` but the actual code is whatever was last uploaded to that S3 key.

This means:
- A stack update that modifies the `ImportLambdaFunction` resource will deploy whatever is currently in `lambda/lambda-deployment-package.zip` on S3 — which may or may not match the local source code.
- There is no version lock between the template and the deployed code.

Sprint 3 S3-08 through S3-10 involve Lambda IAM changes, which will trigger a stack update on the Lambda resource. Before running that update, confirm the S3 deployment package is current.

### 1.3 The Orphaned Jira Secret Creates a Clean-Up Trap

The `production/weekly-reporting/jira` secret was created via CLI and has no CloudFormation management. The consumer Lambda that used it was deleted. This secret is harmless in isolation but dangerous in two ways:

1. If the Jira credentials in it are still valid, they represent an exposed credential with no rotation policy.
2. Sprint 3's S3-04 (Jira import upsert fix) touches the Jira import Lambda — the right time to also confirm this secret is rotated or deleted is during that same story, not later.

---

## 2. Findings Table

| # | Severity | Area | Finding | Recommendation | Effort |
|---|----------|------|---------|----------------|--------|
| 1 | Critical | IaC / EventBridge | CF EventBridge payloads will overwrite live rules on next stack update; live rules include 14-dataset SPICE refresh list that CF template lacks | Complete S3-08 (EventBridge import into CF) before ANY stack update; verify CF payloads match live exactly | 3h |
| 2 | Critical | IAM | Lambda execution role has `sesv2:SendEmail` with `Resource: "*"` — wildcard on email send allows sending to any address | Scope to SES-verified identity ARN: `arn:aws:ses:us-east-1:961341524729:identity/*` | 30m |
| 3 | High | Security | ECS Exec enabled on production service — interactive shell access to running container | Disable in `streamlit-ecs.yaml`: `EnableExecuteCommand: false`, redeploy dashboard stack | 30m |
| 4 | High | Security | ALB HTTP→HTTPS redirect not confirmed | Verify listener rules in console; if no redirect exists, add port 80 → 443 redirect rule and codify in `streamlit-ecs.yaml` | 1h |
| 5 | High | Security | CloudTrail/GuardDuty/Security Hub status unknown | Answer stakeholder question #3 (Control Tower); if not managed centrally, enable CloudTrail with log file validation, enable GuardDuty basic | 2h |
| 6 | High | IaC | Lambda code deployment is fully decoupled from CloudFormation — stack updates can deploy stale code | Document deployment order: always run `update_lambda_and_apply_views.sh` first, then `cloudformation deploy`; add this to the ops runbook | 1h |
| 7 | High | Security | `production/weekly-reporting/jira` secret is orphaned (consumer Lambda deleted) but credentials may still be valid | Delete the secret; if the Jira token is still live, rotate it in Atlassian first | 30m |
| 8 | Medium | Security | X-Ray tracing disabled on Lambda (`PassThrough`) | Enable active tracing in `template.yaml`: `TracingConfig: Mode: Active`; requires Lambda-level IAM for `xray:PutTraceSegments` | 30m |
| 9 | Medium | Security | ECR scan-on-push not confirmed | Verify `weekly-reporting` ECR repo has `imageScanningConfiguration: scanOnPush: true`; add to `streamlit-ecs.yaml` | 30m |
| 10 | Medium | IaC | `quicksight-vpc-sg` (`sg-0d71ad1d75e0bc310`) has no CF tags and unknown purpose | Run `aws ec2 describe-security-groups --group-ids sg-0d71ad1d75e0bc310` to check ENI attachments; delete if unused | 30m |
| 11 | Medium | IaC | SES identity and Bedrock IAM are now in `template.yaml` (confirmed via code review) but stack has not been updated since Jan 2026 | The template is current; the drift is that the stack hasn't been updated to reflect these additions. Include in the S3-08 stack update. | — |
| 12 | Medium | Resilience | Single NAT Gateway — all private subnet egress through one AZ | Accept for internal tool at this cost tier (~$32/mo); document explicitly; if RTO < 1 hour matters, add second NAT | Low (cost decision) |
| 13 | Medium | Resilience | Single-AZ RDS on `db.t3.micro` — no standby | Pending stakeholder RTO/RPO answer; for an internal weekly import tool, single-AZ is likely acceptable. Multi-AZ would add ~$25/mo. | Low (pending answer) |
| 14 | Low | Observability | No DLQ on Lambda — failed invocations from EventBridge are silently dropped | Add SQS DLQ to `ImportLambdaFunction` in `template.yaml`; add CloudWatch alarm on DLQ depth > 0 | 1h |
| 15 | Low | IaC | 35 QuickSight datasets are not IaC-managed | Accept for now — QuickSight IaC is brittle and high-maintenance; document the 35 manually-managed datasets in a registry comment in `coo-dashboards.yaml` | 2h |
| 16 | Low | Cost | Lambda has `MemorySize: 512` and `Timeout: 900` — no timeout/error alarm scoped to the 9am Monday run | Add specific CloudWatch alarm for Lambda duration > 600s (10 min) to catch runaway imports before they hit the 15-min timeout | 30m |

---

## 3. Sprint 3 Plan Assessment

**Overall verdict: Correctly prioritized, but sequencing within the sprint needs one adjustment.**

### What's Right

- S3-01 (forecast_config migration) → S3-02 (3-signal blend) → S3-03 (Streamlit editor) is the correct dependency order. The config table must exist before the Lambda can read from it, and the Lambda must be updated before the UI is useful.
- S3-04 (Jira upsert fix) is high-priority and correctly placed early in the sprint — the duplicate `ps_project_status` rows are causing noise in the QuickSight PS datasets.
- S3-08 through S3-10 (IaC cleanup) are in the right sprint. The question is sequencing within the sprint.

### Required Sequencing Change

**IaC cleanup (S3-08 through S3-10) must complete before any other Lambda deploy in Sprint 3.**

The current plan lists IaC cleanup at the end of Sprint 3. This is backwards. If S3-02 or S3-04 require a Lambda redeploy (which they do), and the CF EventBridge payloads haven't been reconciled yet, any subsequent stack update triggered by the IaC stories will overwrite the live rules with incorrect payloads.

**Recommended Sprint 3 order:**

1. **S3-08 first**: Import live EventBridge rules into CF; reconcile payloads; validate CF template matches live before any stack update.
2. **S3-09**: Scope Lambda IAM. Update `template.yaml`. Do not deploy yet.
3. **S3-10**: Add SES identity and Bedrock resources to CF. Do not deploy yet.
4. **Single stack update** after S3-08/09/10 are all ready. Deploy all three together — one safe update.
5. Then proceed to S3-01 → S3-02 → S3-03 → S3-04 as Lambda code changes only (no stack updates needed for Lambda code changes since code is deployed separately via script).

### Gap: S3-04 Orphaned Secret Cleanup Is Missing

S3-04 touches the Jira import path. Add a sub-task: confirm `production/weekly-reporting/jira` secret is either being actively used by `import_jira_data.py` or delete it. If the Jira import now runs through `production-clockify-import` using the main `production/weekly-reporting/secrets` secret, the standalone Jira secret is orphaned and should be deleted.

### Gap: Human Gate S3-04 Is Mislabeled in the Plan

Looking at the master plan, S3-04 is listed as "[HUMAN GATE] practice_area filter in forecast_resources.py" but the session log shows the practice_area backfill was completed on 2026-06-08. The gate has been passed. Confirm this is the case and unblock S3-04 in the sprint board — it should not be treated as blocked.

---

## 4. Sprint 4/5 Plan Assessment — Security Items Scheduled Too Late

### Security Items in Sprint 4

The current plan has security hardening (ECS Exec disable, ALB HTTPS, drift detection) in Sprint 4. This is a 3-week delay from now. Three of these items are High severity and take 30 minutes each. There is no business reason to defer them.

**ECS Exec disable** is a one-line CF change + stack update. It takes 30 minutes including testing. It belongs in Sprint 3, not Sprint 4.

**ALB HTTPS redirect** — if the redirect already exists (which may be the case and is simply unconfirmed), this is a 15-minute verification. If it doesn't exist, it's a 1-hour fix. Do it this week.

**Drift detection** — running `aws cloudformation detect-stack-drift` takes 5 minutes. After S3-08 reconciles the EventBridge rules, run drift on all four stacks and document the results. This is a pre-condition for all future stack updates.

### Sprint 4 Feature Build Assessment

The Sprint 4 feature work (Resource Capacity tab, Project Time Detail tab, Customer Status Assignments tab) is correctly sequenced after S3-04 (Jira upsert fix). The Customer Status Assignments tab depends on accurate `ps_project_status` data, which only becomes reliable after the upsert fix.

The QuickSight ML Insights work in Sprint 4 is a Should Have and can slip to Sprint 5 without blocking the resource capacity feature.

### Sprint 5 (Hardening) — Two Blockers Are Real

- **PS Profitability tab**: The session log shows rates were seeded on 2026-06-10 (`onshore=$150/hr, offshore=$35/hr, contractor=$120/hr, billable=$150/hr`). This blocker appears to be resolved. The story should be unblocked.
- **MC V2 Audit**: The session log shows this was also completed using Jira credentials (2026-06-10). Confirm whether this is still blocked or has been resolved.

If both of these are resolved, Sprint 5's actual unblocked scope is significantly larger than documented.

---

## 5. IaC Drift Risk — Safe CloudFormation Deploy Protocol

Given the live resources outside CloudFormation, this is the safest sequence for running `aws cloudformation deploy` on `weekly-reporting-production`:

### Pre-Conditions (complete before any deploy)

```bash
# 1. Check current live EventBridge rule targets
aws events list-targets-by-rule --rule production-weekly-import-9am-ct
aws events list-targets-by-rule --rule production-weekly-import-noon-ct
aws events list-targets-by-rule --rule production-jira-daily-refresh

# 2. Capture live rule payloads
aws events list-rules --name-prefix production --query 'Rules[*].{Name:Name,Schedule:ScheduleExpression}'

# 3. Run drift detection FIRST on current state (before any changes)
aws cloudformation detect-stack-drift --stack-name weekly-reporting-production
# Wait ~60 seconds, then:
aws cloudformation describe-stack-drift-detection-status --stack-drift-detection-id <id>
aws cloudformation describe-stack-resource-drifts --stack-name weekly-reporting-production
```

### What Will and Won't Break on Stack Update

| Resource | CF Template Action | Live Impact | Safe? |
|---|---|---|---|
| EventBridge rules (2 in CF) | Will UPDATE targets with CF payload | **Will overwrite live payloads** | ❌ NOT safe until S3-08 complete |
| Lambda function config | Will UPDATE env vars + memory + timeout | Safe — code is deployed separately | ✅ Safe |
| Lambda IAM role | Will UPDATE policies | Safe if additions only | ✅ Safe |
| RDS instance | No change if params unchanged | No impact | ✅ Safe |
| VPC/subnets/SGs | No change | No impact | ✅ Safe |
| CloudWatch alarms | Will UPDATE thresholds | Safe | ✅ Safe |

### The One Rule: Never Update the Stack Until S3-08 Is Done

After S3-08 imports the live EventBridge rules into CF with correct payloads:
1. Run `detect-stack-drift` on all four stacks.
2. Document any remaining intentional drift (the 3 compliance email rules will still be script-managed unless you choose to add them to CF — acceptable to leave them out if documented).
3. Only then run `aws cloudformation deploy`.

### For the ECS Dashboard Stack

The `production-weekly-reporting-dashboard` stack can be updated independently — it has no EventBridge resources and doesn't affect the import pipeline. ECS Exec disable and ALB listener changes can be deployed here without touching the core stack.

---

## 6. Prioritized Action List — Next 2 Weeks (Sprint 3)

### This Week (Jun 26 – Jul 3)

| Priority | Action | Time | Why Now |
|---|---|---|---|
| 🔴 P1 | Verify ALB HTTP→HTTPS redirect in AWS console (5 min); if missing, add rule (1h) | 1h | High security finding; takes 30 min |
| 🔴 P1 | Disable ECS Exec: update `streamlit-ecs.yaml`, deploy dashboard stack | 30m | High security; 1-line CF change |
| 🔴 P1 | Confirm `production/weekly-reporting/jira` orphaned secret → delete or confirm active use | 30m | Credential hygiene; blocks clean S3-04 |
| 🟠 P2 | S3-08: Import 5 live EventBridge rules into `template.yaml` with exact live payloads | 3h | Prerequisite for all future stack updates |
| 🟠 P2 | S3-09: Scope Lambda IAM — add `Resource` ARN to `sesv2:SendEmail` policy | 30m | Include in same stack update as S3-08 |
| 🟠 P2 | Confirm CloudTrail status (answer stakeholder Q3) | 30m | Scopes security remediation; unblocks other items |
| 🟡 P3 | Run `detect-stack-drift` on all 4 stacks after S3-08 template changes | 15m | Establishes baseline before Sprint 3 deploys |
| 🟡 P3 | Confirm practice_area human gate (S3-06) is resolved — unblock S3-07 in sprint board | 15m | Session log shows gate passed Jun 8; sprint board may be stale |

### Week 2 (Jul 4 – Jul 11)

| Priority | Action | Time | Why |
|---|---|---|---|
| 🟠 P2 | S3-01 → S3-02 → S3-03: forecast_config table + 3-signal blend + Streamlit editor | 8h | Sprint 3 primary deliverable |
| 🟠 P2 | S3-04: Jira upsert fix (`ON CONFLICT`) + orphaned secret cleanup | 4h | Prerequisite for Sprint 4 project status tabs |
| 🟡 P3 | S3-05 through S3-07: New views + QS datasets | 7h | Sprint 3 secondary deliverables |
| 🟡 P3 | Enable X-Ray tracing on Lambda (add to `template.yaml` in the S3-08 batch update) | 30m | Medium security; 1-line change |
| 🟡 P3 | Verify ECR scan-on-push enabled on `weekly-reporting` repo | 15m | Medium security; console verification |

---

## 7. Open Questions for the Team

| # | Question | Why It Matters | Blocks |
|---|---|---|---|
| Q1 | Is the Jira data pull now handled entirely by `production-clockify-import`? Or does the orphaned `jira-data-pull-cloudelligent` function still run? | If the consumer Lambda is gone, delete the secret. If anything still uses it, rotate the credential first. | S3-04 cleanup, security finding #7 |
| Q2 | What is the RTO/RPO target for this tool? | Determines whether single-AZ RDS ($0 extra) or Multi-AZ (~$25/mo extra) is appropriate. For a Monday-morning COO dashboard, tolerable recovery time is probably "before next Monday" — which single-AZ with 7-day backups handles. | Finding #13 |
| Q3 | Are CloudTrail and GuardDuty managed at Control Tower or Organization level? | If yes, no action needed at account level. If no, enabling GuardDuty costs ~$3/mo for this account's activity level. | Finding #5 |
| Q4 | Is WAF required in front of the ALB? | The Streamlit dashboard has no public user base — it's internal-only (COO + team). At ~$5/mo base + $0.60/1M requests, WAF adds cost with marginal security benefit for an internal tool that should have IP allowlisting instead. Recommendation: skip WAF; instead confirm ALB has an HTTPS listener and optionally add IP allowlist for Cloudelligent office/VPN range. | Budget; security posture |
| Q5 | Were the PS Profitability tab and MC V2 Audit tab completed in the earlier sprints? | The session log (2026-06-10) shows both were completed. If accurate, Sprint 5 has ~20 hours of freed capacity that should be redirected to the testing plan (T-01 through T-10), which is currently scheduled for Sprint 6. | Sprint 5/6 scope |
| Q6 | What is the `quicksight-vpc-sg` (`sg-0d71ad1d75e0bc310`) for? | Run `aws ec2 describe-network-interfaces --filters Name=group-id,Values=sg-0d71ad1d75e0bc310` — if no ENIs are attached, delete it. If attached to QuickSight VPC connection ENIs, import into CF. | Finding #10 |

---

## 8. Revised Sprint Sequencing Recommendation

Based on this evaluation, the recommended adjustment to the Sprint 3–5 plan is:

**Sprint 3 (current): Reorder internal sequence**

```
Week 1:
  - ALB HTTPS verify/fix (30m)
  - ECS Exec disable (30m)  ← pull forward from Sprint 4
  - S3-08: EventBridge IaC import + CF template update (3h)  ← move to start of sprint
  - S3-09: Lambda IAM scope (30m)  ← batch with S3-08 stack update
  - S3-10: SES/Bedrock into CF (30m)  ← batch with S3-08 stack update
  - Single stack update: weekly-reporting-production
  - Run detect-stack-drift on all 4 stacks

Week 2:
  - S3-01 → S3-02 → S3-03: Forecast model (8h)
  - S3-04: Jira upsert fix + orphaned secret cleanup (4h)
  - S3-05 → S3-07: Views + QS datasets (7h)
```

**Sprint 4 (Jul 14–25): Remove security items already done**

- ECS Exec disable moves to Sprint 3 Week 1 (above).
- ALB HTTPS moves to Sprint 3 Week 1 (above).
- Drift detection runs automatically after S3-08.
- Sprint 4 is now purely feature work: Resource Capacity tab, Project Time Detail tab, Customer Status Assignments tab, QS datasets.

**Sprint 5 (Jul 28–Aug 8): Validate true scope**

- If PS Profitability and MC V2 Audit are already done (per session log), Sprint 5 should move the testing plan (T-01 through T-10) forward from Sprint 6.
- Sprint 5 becomes: remaining blocked items (if any) + full testing cycle.
- This would make Sprint 6 (Sep 1–Sep 12) purely documentation/runbooks, potentially shrinking it or eliminating it.

**Implication:** If the session log is accurate about Sprints 1–6 being largely complete as of 2026-06-10, the master-plan.md sprint numbering is misaligned with actual progress. The first priority for Sprint 3 should be reconciling the session log with the sprint board to understand the actual remaining scope — the plan as written may be significantly overstating the remaining work.

---

*Generated: 2026-06-26 | Source: CloudFormation templates, security review docs, master plan, session log, current state assessment*
