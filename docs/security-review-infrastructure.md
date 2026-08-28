# Security Review — AWS Infrastructure
**Reviewed:** 2026-05-13
**Reviewer:** AWS Security Reviewer
**Source:** docs/aws-infrastructure-discovery.md
**Account:** 961341524729 | **Region:** us-east-1

---

## Executive Summary

The weekly-reporting platform has a **mixed security posture**. The network architecture is well-structured — compute and database tiers are correctly isolated in private subnets, security groups follow least-privilege ingress, and RDS is encrypted at rest with KMS. However, two active Lambda functions store live API credentials in plaintext environment variables, and the QuickSight → RDS connection transmits data without TLS. These two issues alone represent a material data exposure risk and must be remediated before any other work.

Beyond the pre-flagged findings, this review identified additional gaps: no HTTPS enforcement on the ALB, ECS Exec enabled on the production task (interactive shell access), an unmanaged security group of unknown purpose, no CloudTrail or GuardDuty evidence, no S3 bucket policy audit, and no IAM least-privilege validation on Lambda execution roles.

**Overall posture: 🔴 Needs Immediate Remediation** — 3 Critical, 6 High, 6 Medium, 3 Low findings.

---

## Findings

| # | Severity | Category | Finding | Remediation | Effort |
|---|----------|----------|---------|-------------|--------|
| 1 | Critical | SEC05 — Data Protection | `jira-data-pull-lambda` stores live Jira API token and email in Lambda env vars | Rotate token immediately; move to Secrets Manager; update function to read from secret | Low |
| 2 | Critical | SEC05 — Data Protection | `clockify-data-processor` stores Clockify API key in Lambda env vars | Rotate key immediately; move to Secrets Manager or decommission legacy function | Low |
| 3 | Critical | SEC05 — Data Protection | QuickSight → RDS connection has `DisableSsl: true` — data in transit is unencrypted | Enable SSL on QuickSight data source; enforce `ssl=require` on RDS parameter group | Low |
| 4 | High | SEC04 — Infrastructure Protection | ALB accepts HTTP (port 80) with no confirmed redirect to HTTPS | Add ALB listener rule to redirect HTTP 80 → HTTPS 443; confirm ACM certificate is attached | Low |
| 5 | High | SEC07 — Application Security | ECS Exec is enabled on the production ECS service — allows interactive shell into running containers | Disable ECS Exec on production service unless actively needed for debugging | Low |
| 6 | High | SEC02 — IAM | Lambda execution role permissions not validated — `production-clockify-import` accesses RDS, Secrets Manager, Bedrock, SNS, QuickSight | Audit IAM role; remove any wildcard actions; scope resource ARNs to specific secrets/topics/datasets | Medium |
| 7 | High | SEC03 — Detection | No CloudTrail, GuardDuty, or Security Hub evidence in discovery — detection controls unconfirmed | Confirm CloudTrail is enabled with log file validation; enable GuardDuty; enable Security Hub | Low |
| 8 | High | SEC04 — Infrastructure Protection | `quicksight-vpc-sg` (`sg-0d71ad1d75e0bc310`) is not CloudFormation-managed — unknown origin, all-traffic egress | Investigate purpose; if unused, delete; if needed, import into CloudFormation | Low |
| 9 | High | SEC01 — Foundations | CloudFormation drift detection not run on any stack — live infrastructure may diverge from IaC | Run drift detection on all 4 project stacks; schedule weekly automated drift checks | Low |
| 10 | Medium | SEC05 — Data Protection | S3 bucket public access block settings not confirmed for any project bucket | Audit all project S3 buckets; enable Block Public Access on all; confirm no bucket policies grant public read | Low |
| 11 | Medium | SEC05 — Data Protection | RDS IAM database authentication is disabled — password auth only | Enable IAM DB authentication; update Lambda and ECS to use IAM tokens instead of password from Secrets Manager | High |
| 12 | Medium | SEC03 — Detection | X-Ray tracing disabled on all project Lambdas (`PassThrough`) | Enable X-Ray active tracing on `production-clockify-import` and `production-archera-proxy` | Low |
| 13 | Medium | SEC04 — Infrastructure Protection | No VPC endpoints confirmed for Secrets Manager, SNS, or SSM — traffic may traverse NAT/internet | Confirm or create VPC Interface Endpoints for `secretsmanager`, `sns`, `ssm`, `ecr.dkr`, `ecr.api` | Medium |
| 14 | Medium | SEC02 — IAM | `lambda-service-role-stack` uses inline policies — harder to audit and reuse | Convert inline policies to managed policies; audit scope of permissions granted | Medium |
| 15 | Medium | SEC07 — Application Security | `weekly-reporting` ECR repository has no scan-on-push; `aws-funding-rag-lambda` ECR also lacks scanning | Enable scan-on-push on all ECR repositories; review existing image scan results | Low |
| 16 | Low | SEC01 — Foundations | Legacy `Clockify-Quicksight` stack and `clockify-data-processor` Lambda increase attack surface unnecessarily | Confirm if in use; if not, decommission stack, Lambda, and associated S3 buckets | Low |
| 17 | Low | SEC05 — Data Protection | RDS Performance Insights disabled — limits forensic visibility into query-level activity | Enable Performance Insights (free tier for db.t3.micro); retain logs for 7 days | Low |
| 18 | Low | SEC06 — Incident Response | No DLQ configured on `production-clockify-import` — failed invocations are silently dropped | Add SQS DLQ to Lambda; configure CloudWatch alarm on DLQ depth | Low |
| 19 | Low | SEC01 — Foundations | Monday noon EventBridge rule hardcodes 14 QuickSight dataset IDs in static JSON input | Move dataset ID list to SSM Parameter Store; Lambda reads at runtime | Low |

---

## Critical Findings (Immediate Action Required)

### Finding 1 — Hardcoded Jira API Token in Lambda Environment Variables

**Severity:** Critical
**Pillar:** SEC05 — Data Protection
**Resource:** `jira-data-pull-lambda`

**Risk:** Lambda environment variables are stored in plaintext and are readable by any IAM principal with `lambda:GetFunctionConfiguration` or `lambda:GetFunction`. They appear in CloudTrail `UpdateFunctionConfiguration` events and are visible in the AWS console. A compromised IAM credential or overly permissive role grants immediate access to the Jira API token and the associated email address.

**Remediation (step-by-step):**
1. **Rotate the Jira API token immediately** via the Atlassian account settings. The existing token must be considered compromised.
2. Store the new token in Secrets Manager:
   ```
   Secret name: production/jira/api-credentials
   Keys: jira_api_token, jira_email
   ```
3. Update the Lambda execution role to allow `secretsmanager:GetSecretValue` on the new secret ARN only.
4. Update `jira-data-pull-lambda` code to call `GetSecretValue` at runtime instead of reading env vars.
5. Remove `JIRA_API_TOKEN` and `JIRA_EMAIL` (or equivalent) from the Lambda environment variables.
6. Verify no other Lambda or resource references the old token.

**Effort:** Low (2–4 hours)

---

### Finding 2 — Hardcoded Clockify API Key in Legacy Lambda

**Severity:** Critical
**Pillar:** SEC05 — Data Protection
**Resource:** `clockify-data-processor` (stack: `Clockify-Quicksight`)

**Risk:** Same exposure vector as Finding 1. The Clockify API key grants access to time-tracking data for all workspace members. If this legacy Lambda is still active, the key is in active use and exposed.

**Remediation (step-by-step):**
1. **Determine if `clockify-data-processor` is still in active use** (check CloudWatch Logs for recent invocations).
2. **If in use:** Rotate the Clockify API key; move to Secrets Manager (`production/clockify/api-key`); update Lambda to read from secret.
3. **If not in use (recommended):** Rotate the key to invalidate it, then decommission the `Clockify-Quicksight` stack entirely (Lambda, S3 buckets `clockify-dashboard-961341524729-us-east-1` and `clockify-quicksight-lambda`).
4. Confirm the production `production-clockify-import` Lambda uses Secrets Manager (env var `SECRET_NAME` is present — verify the secret contains the Clockify key and the Lambda reads it correctly).

**Effort:** Low (2–4 hours)

---

### Finding 3 — QuickSight → RDS Connection Has TLS Disabled

**Severity:** Critical
**Pillar:** SEC05 — Data Protection
**Resource:** QuickSight data source `Weekly-Reporting-PostgreSQL`

**Risk:** All data flowing from RDS PostgreSQL to QuickSight SPICE — including employee time data, project financials, utilization metrics, and COO-level KPIs — is transmitted in plaintext over the network. Any network-level observer between QuickSight's VPC connection ENIs and the RDS instance can read query results in full.

**Remediation (step-by-step):**
1. Update the QuickSight data source to remove `DisableSsl: true` (set `SslProperties.DisableSsl: false`).
2. Confirm the RDS parameter group `weekly-reporting-postgres15` has `ssl = 1` (PostgreSQL default is on; verify it has not been disabled).
3. Confirm the RDS CA certificate is trusted by QuickSight (CA valid until 2027-01-20 — within range).
4. Test the QuickSight data source connection after the change; re-run a SPICE refresh to confirm datasets load successfully.
5. If the CloudFormation stack manages the data source, update the template to reflect `DisableSsl: false` to prevent drift re-introducing the issue.

**Effort:** Low (1–2 hours)

---

## High Findings

### Finding 4 — ALB HTTP Listener Without Confirmed HTTPS Redirect

**Severity:** High
**Pillar:** SEC04 — Infrastructure Protection
**Resource:** ALB security group `production-dashboard-alb-sg` — port 80 open to `0.0.0.0/0`

**Risk:** The ALB accepts inbound HTTP on port 80 from the internet. If no redirect rule exists, users accessing the Streamlit dashboard over HTTP transmit session data, cookies, and report content in plaintext. The discovery did not enumerate ALB listeners directly, so HTTPS enforcement is unconfirmed.

**Remediation:**
- Confirm ALB has an HTTPS listener (port 443) with a valid ACM certificate.
- Add a listener rule on port 80: redirect all traffic to HTTPS (301).
- If no ACM certificate exists, request one via ACM for the dashboard domain.
- Update the CloudFormation stack to codify the redirect rule.

**Effort:** Low

---

### Finding 5 — ECS Exec Enabled on Production Service

**Severity:** High
**Pillar:** SEC07 — Application Security
**Resource:** ECS service `production-dashboard-service`

**Risk:** ECS Exec (`enableExecuteCommand: true`) allows any IAM principal with `ecs:ExecuteCommand` permission to open an interactive shell (`/bin/sh`) inside a running production container. This bypasses application-level access controls and provides direct access to the container filesystem, environment variables (including any injected at runtime), and the network interface. In a production environment, this capability should be disabled unless actively used for an incident.

**Remediation:**
- Disable ECS Exec on the service: update the CloudFormation template to set `EnableExecuteCommand: false`.
- If ECS Exec is needed for break-glass debugging, document the procedure and re-enable only during active incidents, then disable again.
- Audit CloudTrail for any `ExecuteCommand` events to determine if this has been used.

**Effort:** Low

---

### Finding 6 — Lambda Execution Role Permissions Not Validated

**Severity:** High
**Pillar:** SEC02 — IAM
**Resource:** `production-clockify-import` execution role

**Risk:** The Lambda accesses RDS (via VPC), Secrets Manager, Bedrock, SNS, and QuickSight SPICE. The discovery did not retrieve the IAM role policy. If the role uses broad managed policies (e.g., `AmazonQuickSightFullAccess`, `AmazonBedrockFullAccess`) rather than scoped resource-level permissions, a Lambda compromise grants an attacker broad access to these services across the account.

**Remediation:**
- Retrieve and audit the execution role policy for `production-clockify-import` and `production-archera-proxy`.
- Replace any `*` resource ARNs with specific ARNs (secret ARN, SNS topic ARN, specific QuickSight dataset ARNs).
- Remove any service actions not required by the function's actual code path.
- Apply the same audit to `jira-data-pull-lambda`.

**Effort:** Medium

---

### Finding 7 — Detection Controls (CloudTrail / GuardDuty / Security Hub) Unconfirmed

**Severity:** High
**Pillar:** SEC03 — Detection
**Resource:** Account-level

**Risk:** The discovery document does not confirm whether CloudTrail, GuardDuty, or Security Hub are active. Without CloudTrail, there is no audit log of API calls — credential misuse, unauthorized access, and configuration changes are undetectable. Without GuardDuty, there is no automated threat detection for anomalous behavior (e.g., credential exfiltration, unusual API call patterns).

**Remediation:**
- Confirm CloudTrail is enabled in us-east-1 with a multi-region trail, log file validation enabled, and logs delivered to an S3 bucket with restricted access.
- Enable GuardDuty in us-east-1 (and all active regions).
- Enable Security Hub with the AWS Foundational Security Best Practices standard.
- If these are managed at the Control Tower management account level (StackSet-* stacks suggest Control Tower is in use), confirm coverage extends to this account.

**Effort:** Low

---

### Finding 8 — Unmanaged Security Group of Unknown Purpose

**Severity:** High
**Pillar:** SEC04 — Infrastructure Protection
**Resource:** `sg-0d71ad1d75e0bc310` (`quicksight-vpc-sg`)

**Risk:** This security group exists in the production VPC but has no CloudFormation tags, indicating it was created manually outside IaC. It has no inbound rules but allows all-traffic egress. Its purpose is unknown. An unmanaged security group can be attached to resources without IaC visibility, creating untracked network paths.

**Remediation:**
- Identify all resources currently attached to this security group (`aws ec2 describe-network-interfaces --filters Name=group-id,Values=sg-0d71ad1d75e0bc310`).
- If unused: delete the security group.
- If in use: document its purpose and import it into the CloudFormation stack.
- Run CloudFormation drift detection to surface any other manually created resources.

**Effort:** Low

---

### Finding 9 — CloudFormation Drift Detection Not Run

**Severity:** High
**Pillar:** SEC01 — Security Foundations
**Resource:** All 4 project CloudFormation stacks

**Risk:** All stacks show `DriftStatus: NOT_CHECKED`. Manual changes to security groups, IAM policies, RDS parameter groups, or Lambda configurations made outside CloudFormation are invisible to the IaC state. This means the security posture documented in templates may not reflect reality.

**Remediation:**
- Run drift detection on all 4 project stacks immediately.
- Review and remediate any detected drift (either update the template to match reality, or revert the manual change).
- Schedule automated drift detection via EventBridge + Lambda or AWS Config rule `cloudformation-stack-drift-detection-check`.

**Effort:** Low

---

## Medium Findings

### Finding 10 — S3 Bucket Public Access Block Not Confirmed

**Severity:** Medium
**Pillar:** SEC05 — Data Protection
**Resource:** All project S3 buckets

The discovery lists 5 project-related buckets (`weekly-reporting-production-deployments-*`, `clockify-dashboard-*`, `jira-data-pull-cloudelligent`, `internal-dashboard-bucket`, `executivereporting`) but does not confirm Block Public Access settings or bucket policies. `executivereporting` and `internal-dashboard-bucket` names suggest they may contain sensitive business data.

**Remediation:** Enable S3 Block Public Access (all 4 settings) on every project bucket. Audit bucket policies for any `Principal: *` statements. Enable account-level Block Public Access as a backstop.

---

### Finding 11 — RDS IAM Database Authentication Disabled

**Severity:** Medium
**Pillar:** SEC05 — Data Protection
**Resource:** `production-weekly-reporting` RDS instance

Password-based authentication relies on the database password stored in Secrets Manager. IAM DB authentication eliminates the long-lived password entirely — the Lambda and ECS task would authenticate using short-lived IAM tokens, reducing the blast radius of a Secrets Manager compromise.

**Remediation:** Enable IAM DB authentication on the RDS instance; update Lambda and ECS task role to include `rds-db:connect`; update application connection code to generate IAM auth tokens. This is a medium-effort change requiring application code updates.

---

### Finding 12 — X-Ray Tracing Disabled

**Severity:** Medium
**Pillar:** SEC03 — Detection

Both project Lambdas run with `TracingConfig.Mode: PassThrough`. Without X-Ray, there is no visibility into which downstream calls (Secrets Manager, RDS, Bedrock, QuickSight, external APIs) are slow or failing, making incident investigation significantly harder.

**Remediation:** Set `TracingConfig.Mode: Active` on both Lambdas. Add X-Ray SDK instrumentation to the Python code for RDS and HTTP client calls. Cost: ~$0.000005 per trace — negligible at this scale.

---

### Finding 13 — VPC Endpoints for AWS Services Not Confirmed

**Severity:** Medium
**Pillar:** SEC04 — Infrastructure Protection

The Lambda and ECS tasks run in private subnets and call Secrets Manager, SNS, ECR, and potentially SSM. Without VPC Interface Endpoints, this traffic exits the VPC via NAT Gateway to the public AWS service endpoints, incurring data transfer costs and bypassing VPC-level network controls.

**Remediation:** Confirm or create VPC Interface Endpoints for: `com.amazonaws.us-east-1.secretsmanager`, `com.amazonaws.us-east-1.sns`, `com.amazonaws.us-east-1.ecr.dkr`, `com.amazonaws.us-east-1.ecr.api`, `com.amazonaws.us-east-1.logs`. Cost: ~$7.30/month per endpoint — evaluate against NAT Gateway data transfer costs.

---

### Finding 14 — Inline IAM Policies in `lambda-service-role-stack`

**Severity:** Medium
**Pillar:** SEC02 — IAM

The `lambda-service-role-stack` uses inline policies. Inline policies cannot be reused, are harder to audit in IAM Access Analyzer, and are not visible in the IAM managed policies list.

**Remediation:** Convert inline policies to customer-managed policies. Scope each policy to the minimum required actions and resource ARNs.

---

### Finding 15 — ECR Scan-on-Push Disabled for Two Repositories

**Severity:** Medium
**Pillar:** SEC07 — Application Security
**Resource:** `weekly-reporting` ECR repo, `aws-funding-rag-lambda` ECR repo

The `weekly-reporting` repo (9 images, 1 tagged `latest`) has no vulnerability scanning. If this image is deployed anywhere, known CVEs in its base image or dependencies are undetected.

**Remediation:** Enable `imageScanningConfiguration.scanOnPush: true` on both repositories. Review existing scan findings on `production-weekly-reporting-dashboard` (scan-on-push already enabled) and remediate any Critical/High CVEs.

---

## Low Findings

### Finding 16 — Legacy `Clockify-Quicksight` Stack Increases Attack Surface

**Severity:** Low
**Pillar:** SEC01 — Foundations

The `Clockify-Quicksight` stack and `clockify-data-processor` Lambda appear to be a pre-production predecessor. If unused, they represent unnecessary attack surface (exposed credentials, active Lambda execution role, S3 buckets with potentially sensitive data).

**Remediation:** Confirm last invocation date in CloudWatch Logs. If unused, decommission: delete the stack, rotate any credentials it held, and empty/delete associated S3 buckets.

---

### Finding 17 — RDS Performance Insights Disabled

**Severity:** Low
**Pillar:** SEC03 — Detection

Performance Insights provides query-level visibility into RDS activity. Without it, detecting anomalous query patterns (e.g., unexpected full-table scans, unusual query volumes) requires manual log analysis.

**Remediation:** Enable Performance Insights on the RDS instance (free for db.t3.micro with 7-day retention). No application changes required.

---

### Finding 18 — No Dead-Letter Queue on `production-clockify-import`

**Severity:** Low
**Pillar:** SEC06 — Incident Response

Failed Lambda invocations from EventBridge are retried twice by default, then silently discarded. There is no DLQ to capture failed events for investigation or replay.

**Remediation:** Create an SQS DLQ; attach it to the Lambda function's event source mapping; add a CloudWatch alarm on `ApproximateNumberOfMessagesVisible > 0` to alert on failures.

---

### Finding 19 — Hardcoded QuickSight Dataset IDs in EventBridge Rule

**Severity:** Low
**Pillar:** SEC01 — Foundations

The `production-weekly-import-noon-ct` rule embeds 14 QuickSight dataset IDs as static JSON. This is a configuration management risk — not a direct security issue — but hardcoded resource IDs in event payloads are difficult to audit and update.

**Remediation:** Move the dataset ID list to SSM Parameter Store (`/weekly-reporting/production/quicksight-dataset-ids`). Update the Lambda to read the list at runtime. This also removes the IDs from CloudTrail event history.

---

## Well-Architected Pillar Assessment

| Pillar | Status | Rationale |
|--------|--------|-----------|
| **SEC01 — Security Foundations** | 🔴 Red | No confirmed CloudTrail/GuardDuty/Security Hub; drift detection never run; legacy stack increases attack surface |
| **SEC02 — IAM** | 🟠 Amber | Secrets Manager used for primary Lambda (good); inline policies present; Lambda execution role permissions unvalidated; IAM DB auth disabled |
| **SEC03 — Detection** | 🔴 Red | CloudTrail unconfirmed; GuardDuty unconfirmed; X-Ray disabled; no DLQ for failed invocations |
| **SEC04 — Infrastructure Protection** | 🟠 Amber | Network topology is well-structured (private subnets, SG least-privilege ingress); ALB HTTP redirect unconfirmed; ECS Exec enabled; unmanaged SG present; VPC endpoints unconfirmed |
| **SEC05 — Data Protection** | 🔴 Red | Two active Lambdas with plaintext credentials in env vars; QuickSight → RDS TLS disabled; S3 public access block unconfirmed; RDS IAM auth disabled |
| **SEC06 — Incident Response** | 🟠 Amber | RDS deletion protection enabled (good); 7-day backup retention (good); no DLQ; no runbooks documented; RTO/RPO not defined |
| **SEC07 — Application Security** | 🟠 Amber | ECS Exec enabled on production; ECR scan-on-push missing on 2 repos; `production-weekly-reporting-dashboard` repo scans correctly |

**Reliability (bonus):** 🟠 Amber — Single-AZ RDS is the primary reliability risk; ECS deployment circuit breaker disabled; no ECS auto-scaling.

---

## Recommended Remediation Order

Prioritized by risk reduction per unit of effort:

### Immediate (this week) — Critical + High

| Priority | Action | Finding | Estimated Effort |
|----------|--------|---------|-----------------|
| 1 | Rotate Jira API token; move to Secrets Manager | F1 | 2–4 hours |
| 2 | Rotate Clockify API key; move to Secrets Manager or decommission legacy Lambda | F2 | 2–4 hours |
| 3 | Enable SSL on QuickSight → RDS data source | F3 | 1–2 hours |
| 4 | Disable ECS Exec on production service | F5 | 30 minutes |
| 5 | Confirm/add ALB HTTP → HTTPS redirect | F4 | 1 hour |
| 6 | Run CloudFormation drift detection on all 4 stacks | F9 | 1 hour |
| 7 | Investigate and remove/import unmanaged SG `sg-0d71ad1d75e0bc310` | F8 | 1 hour |
| 8 | Confirm CloudTrail, GuardDuty, Security Hub are active | F7 | 1–2 hours |

### Short-term (next 2 weeks) — High + Medium

| Priority | Action | Finding | Estimated Effort |
|----------|--------|---------|-----------------|
| 9 | Audit Lambda execution role policies; remove wildcards | F6 | 4–8 hours |
| 10 | Enable S3 Block Public Access on all project buckets | F10 | 1 hour |
| 11 | Enable ECR scan-on-push on `weekly-reporting` and `aws-funding-rag-lambda` repos | F15 | 30 minutes |
| 12 | Enable X-Ray tracing on both project Lambdas | F12 | 1 hour |
| 13 | Confirm or create VPC endpoints for Secrets Manager, SNS, ECR | F13 | 2–4 hours |
| 14 | Convert inline IAM policies to managed policies | F14 | 2–4 hours |

### Medium-term (next sprint) — Medium + Low

| Priority | Action | Finding | Estimated Effort |
|----------|--------|---------|-----------------|
| 15 | Enable RDS Performance Insights | F17 | 30 minutes |
| 16 | Add SQS DLQ to `production-clockify-import` | F18 | 2 hours |
| 17 | Decommission `Clockify-Quicksight` legacy stack (if unused) | F16 | 2–4 hours |
| 18 | Move QuickSight dataset IDs to SSM Parameter Store | F19 | 2–4 hours |
| 19 | Enable RDS IAM database authentication | F11 | 1–2 days (app code change) |

---

## Open Questions for Stakeholder Input

These items require business or operational decisions before remediation can be scoped:

1. **Is `clockify-data-processor` / `Clockify-Quicksight` stack still in active use?** Determines whether Finding 2 is a rotate-and-migrate or rotate-and-decommission.
2. **What is the RTO/RPO target for the reporting platform?** Determines whether single-AZ RDS (Finding: Reliability) is acceptable or requires Multi-AZ upgrade.
3. **Who has access to the COO QuickSight dashboards?** QuickSight user/group permissions were not enumerated — confirm access is restricted to intended principals.
4. **Is there a WAF in front of the ALB?** The Streamlit dashboard is internet-facing. WAF (AWS WAF v2) would add rate limiting and managed rule groups (~$5/month base + $1/million requests). Confirm whether this is in scope.
5. **Are CloudTrail and GuardDuty managed at the Control Tower management account level?** If so, confirm this account (961341524729) is covered by the organization-level trail and GuardDuty delegated admin.
