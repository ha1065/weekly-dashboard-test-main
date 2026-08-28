# Outstanding Items Report
**Generated:** 2026-05-13  
**Account:** 961341524729 | **Region:** us-east-1

---

## What Was Completed Today

| Item | Status |
|---|---|
| `jira-data-pull-lambda` deleted | ✅ Done |
| `clockify-data-processor` deleted | ✅ Done |
| `jira-data-pull` EventBridge rule deleted | ✅ Done |
| Both legacy IAM roles deleted | ✅ Done |
| Both legacy CloudWatch log groups deleted | ✅ Done |
| `production/weekly-reporting/jira` secret created in Secrets Manager | ✅ Done |
| IAM Secrets Manager policies attached to legacy roles | ✅ Moot — roles deleted before policies were needed |
| `NameError: get_quicksight_dataset_ids` fixed in `production-clockify-import` | ✅ Done |
| `production-clockify-import` redeployed and verified working | ✅ Done |
| `src/utils/secrets.py`, `src/lambda_function.py`, `src/index.py` written | ✅ Moot — see Section 3 |

---

## 1. Migration Plan — Pending Items

The migration plan targeted two Lambdas. Both are now deleted, which changes the scope significantly.

### `jira-data-pull-lambda` migration — MOOT (Lambda deleted)

All steps in the plan for this Lambda (Steps 2b, 2d, 2e, 3b, 5a–5e for Jira) are moot. The Lambda no longer exists. The `production/weekly-reporting/jira` secret was created but has no consumer.

**Pending decision:** The `production/weekly-reporting/jira` secret now exists with no Lambda reading it. Either:
- Delete it (if Jira data pull is fully replaced by `production-clockify-import` via `production-jira-daily-refresh`), or
- Keep it if a replacement Lambda will be built

### `clockify-data-processor` migration — MOOT (Lambda deleted)

All steps for this Lambda (Steps 2c, 2d, 2e, 3c, 5a–5e for Clockify) are moot.

### CloudFormation updates (Plan Section 4) — PARTIALLY PENDING

| CF Update | Status |
|---|---|
| Add `JiraSecrets` resource to `cloudformation/template.yaml` | ⏳ Pending — the secret exists manually but is not in IaC |
| Add `JiraAPIToken` parameter to template | ⏳ Pending |
| Remove `ClockifyAPIKey` from `ApplicationSecrets` (optional, long-term) | ⏳ Pending — low priority now that `clockify-data-processor` is deleted |

The `production/weekly-reporting/jira` secret was created manually (via CLI). It is not managed by CloudFormation. If it is kept, it should be imported into the `weekly-reporting-production` stack to prevent drift.

---

## 2. Security Findings — Open Items

Security findings from `docs/security-review-infrastructure.md`, cross-referenced against today's work.

### Critical

| # | Finding | Status | Notes |
|---|---|---|---|
| F1 | `jira-data-pull-lambda` — Jira API token in plaintext env vars | ✅ Resolved | Lambda deleted; token no longer exposed |
| F2 | `clockify-data-processor` — Clockify API key in plaintext env vars | ✅ Resolved | Lambda deleted; key no longer exposed |
| F3 | QuickSight → RDS connection has `DisableSsl: true` | 🔴 **OPEN** | Not addressed today; data in transit still unencrypted |

### High

| # | Finding | Status | Notes |
|---|---|---|---|
| F4 | ALB accepts HTTP with no confirmed HTTPS redirect | 🔴 **OPEN** | Not addressed |
| F5 | ECS Exec enabled on production ECS service | 🔴 **OPEN** | Not addressed |
| F6 | Lambda execution role permissions not validated | 🔴 **OPEN** | Not addressed |
| F7 | CloudTrail / GuardDuty / Security Hub unconfirmed | 🔴 **OPEN** | Not addressed |
| F8 | Unmanaged security group `sg-0d71ad1d75e0bc310` | 🔴 **OPEN** | Not addressed |
| F9 | CloudFormation drift detection not run on any stack | 🔴 **OPEN** | Not addressed |

### Medium

| # | Finding | Status | Notes |
|---|---|---|---|
| F10 | S3 Block Public Access not confirmed on project buckets | 🔴 **OPEN** | Not addressed |
| F11 | RDS IAM database authentication disabled | 🔴 **OPEN** | Not addressed |
| F12 | X-Ray tracing disabled on project Lambdas | 🔴 **OPEN** | Not addressed |
| F13 | VPC endpoints for Secrets Manager / SNS / ECR not confirmed | 🔴 **OPEN** | Not addressed |
| F14 | `lambda-service-role-stack` uses inline IAM policies | 🔴 **OPEN** | Not addressed |
| F15 | ECR scan-on-push disabled on `weekly-reporting` and `aws-funding-rag-lambda` repos | 🔴 **OPEN** | Not addressed |

### Low (for completeness)

| # | Finding | Status | Notes |
|---|---|---|---|
| F16 | Legacy `Clockify-Quicksight` stack increases attack surface | ✅ Resolved | `clockify-data-processor` deleted; stack decommission still pending (see below) |
| F17 | RDS Performance Insights disabled | 🔴 **OPEN** | Not addressed |
| F18 | No DLQ on `production-clockify-import` | 🔴 **OPEN** | Not addressed |
| F19 | QuickSight dataset IDs hardcoded in EventBridge rule | 🔴 **OPEN** | Not addressed |

**Score change:** 3 Critical → 1 Critical remaining. 2 of 3 Critical findings resolved by deleting the legacy Lambdas.

---

## 3. Moot Items

These items were completed today but are now irrelevant because the target Lambdas were deleted.

| Item | Why Moot |
|---|---|
| `src/utils/secrets.py` | Written for `jira-data-pull-lambda` and `clockify-data-processor`; both deleted |
| `src/lambda_function.py` | Entry point written for `jira-data-pull-lambda`; Lambda deleted |
| `src/index.py` | Entry point written for `clockify-data-processor`; Lambda deleted |
| IAM Secrets Manager policies attached to legacy roles | Roles deleted; policies went with them |
| Migration plan Steps 2b, 2c, 2d, 2e (env var updates) | Target Lambdas no longer exist |
| Migration plan Steps 3b, 3c (handler code changes) | Target Lambdas no longer exist |
| Migration plan Steps 5a–5e (verification steps) | Nothing to verify |

**Recommendation:** The three source files (`src/utils/secrets.py`, `src/lambda_function.py`, `src/index.py`) can be deleted from the repo unless they will be reused for a replacement Lambda. Keeping dead code that references deleted infrastructure creates confusion.

---

## 4. Recommended Next Actions (Priority Order)

### Immediate

1. **Fix `production-clockify-import` view schema conflict (F: RCA-2)**  
   The `42P16` PostgreSQL errors from 2026-05-12 may still affect Monday runs. Verify current view state in RDS. If views are inconsistent, run the corrective migration as a single transaction.  
   *Effort: 1–2 hours*

2. **Enable SSL on QuickSight → RDS data source (Security F3 — Critical)**  
   Update `Weekly-Reporting-PostgreSQL` data source: set `DisableSsl: false`. Test SPICE refresh after change. Update CloudFormation template to prevent drift re-introducing the issue.  
   *Effort: 1–2 hours*

3. **Decide fate of `production/weekly-reporting/jira` secret**  
   The secret was created today but its consumer (the Lambda) was deleted. Either delete the secret or document that it is reserved for a future replacement. Leaving an orphaned secret with a live API token is a low-grade security risk.  
   *Effort: 15 minutes*

4. **Decommission `Clockify-Quicksight` CloudFormation stack**  
   The `clockify-data-processor` Lambda was deleted manually today, but the `Clockify-Quicksight` stack still exists. Delete the stack to clean up remaining resources (S3 buckets `clockify-dashboard-961341524729-us-east-1` and `clockify-quicksight-lambda`, any remaining IAM resources). Confirm buckets are empty before deletion.  
   *Effort: 30 minutes*

5. **Delete or archive moot source files**  
   Remove `src/utils/secrets.py`, `src/lambda_function.py`, `src/index.py` from the repo if they will not be reused. If kept for reference, move to `docs/archive/` or add a prominent comment noting the target Lambdas are deleted.  
   *Effort: 15 minutes*

### This Week

6. **Disable ECS Exec on production service (Security F5 — High)**  
   Update CloudFormation template: `EnableExecuteCommand: false` on `production-dashboard-service`. Redeploy.  
   *Effort: 30 minutes*

7. **Confirm/add ALB HTTP → HTTPS redirect (Security F4 — High)**  
   Enumerate ALB listeners; confirm port 80 redirects to 443. Add redirect rule if missing.  
   *Effort: 1 hour*

8. **Run CloudFormation drift detection on all 4 project stacks (Security F9 — High)**  
   Run `aws cloudformation detect-stack-drift` on `weekly-reporting-production`, `production-weekly-reporting-dashboard`, `cloudelligent-qs-theme`, `coo-dashboards-prod`. Review and remediate any drift found.  
   *Effort: 1 hour*

9. **Investigate and resolve unmanaged SG `sg-0d71ad1d75e0bc310` (Security F8 — High)**  
   Check what resources are attached to it. Delete if unused; import into CloudFormation if needed.  
   *Effort: 1 hour*

10. **Confirm CloudTrail, GuardDuty, Security Hub are active (Security F7 — High)**  
    Verify account-level detection controls. If managed via Control Tower, confirm this account (961341524729) is covered.  
    *Effort: 1–2 hours*

### Next Sprint

11. **Audit `production-clockify-import` execution role (Security F6 — High)**  
    Retrieve and review IAM policy. Remove wildcard resource ARNs; scope to specific secret, SNS topic, and QuickSight dataset ARNs.  
    *Effort: 4–8 hours*

12. **Enable S3 Block Public Access on all project buckets (Security F10 — Medium)**  
    Covers: `weekly-reporting-production-deployments-*`, `jira-data-pull-cloudelligent`, `internal-dashboard-bucket`, `executivereporting`.  
    *Effort: 1 hour*

13. **Enable ECR scan-on-push on `weekly-reporting` and `aws-funding-rag-lambda` repos (Security F15 — Medium)**  
    *Effort: 30 minutes*

14. **Enable X-Ray tracing on `production-clockify-import` (Security F12 — Medium)**  
    *Effort: 1 hour*

15. **Add SQS DLQ to `production-clockify-import` (Security F18 — Low)**  
    Add CloudWatch alarm on DLQ depth > 0 to the existing SNS notification topic.  
    *Effort: 2 hours*

16. **Import `production/weekly-reporting/jira` secret into CloudFormation (Migration Plan §4a)**  
    Only relevant if the secret is kept. Prevents it from being an untracked manual resource.  
    *Effort: 1 hour*

---

## Open Questions Requiring Stakeholder Input

These items cannot be resolved without a business decision:

| Question | Blocks |
|---|---|
| Is Jira data pull now fully handled by `production-clockify-import` via `production-jira-daily-refresh`? | Whether to delete `production/weekly-reporting/jira` secret and the `jira-data-pull-cloudelligent` S3 bucket |
| What is the RTO/RPO target for the reporting platform? | Whether single-AZ RDS is acceptable or Multi-AZ upgrade is required |
| Are CloudTrail and GuardDuty managed at the Control Tower management account level? | Scope of F7 remediation |
| Is there a WAF requirement in front of the ALB? | Whether to add AWS WAF v2 (~$5/month base) |
