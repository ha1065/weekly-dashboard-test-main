# Cloudelligent Weekly Reporting — Current State Assessment

**Date:** 2026-06-23
**Account:** 961341524729 | **Region:** us-east-1
**Prepared for:** COO / Decision-maker
**Scope:** Full infrastructure, data pipeline, Lambda modes, IaC gaps, stability and simplification

---

## Section 1: Infrastructure Inventory

### 1.1 CloudFormation Stacks — Confirmed Deployed

| Stack | Status | Last Updated | Description |
|---|---|---|---|
| `weekly-reporting-production` | UPDATE_COMPLETE | 2026-01-20 | Core infra: VPC, RDS PostgreSQL, Lambda, Secrets Manager, SNS, EventBridge (partial) |
| `production-weekly-reporting-dashboard` | UPDATE_COMPLETE | 2026-01-29 | ECS Fargate Streamlit dashboard + ALB (confirmed 1 task running) |
| `cloudelligent-qs-theme` | CREATE_COMPLETE | 2026-04-27 | CE MIDNIGHT brand theme for QuickSight |
| `coo-dashboards-prod` | UPDATE_COMPLETE | 2026-05-04 | COO Operational Analysis + Executive Summary dashboards |

**Drift status:** `NOT_CHECKED` on all four stacks. Live state may diverge from IaC definitions.

### 1.2 Exists as IaC Only — Not Confirmed Deployed

| Template | Status | Notes |
|---|---|---|
| `cloudformation/streamlit-ecs.yaml` | **IaC only — superseded** | The `production-weekly-reporting-dashboard` stack is the live ECS deployment. This template appears to be the source for that stack but is now out of date with the live stack (task definition revision 4, last deployed 2026-05-08). Do not use this template for redeployment without reconciling with live state. |
| `cloudformation/quicksight-dashboards.yaml` | **Supplementary / partial** | Defines older QuickSight datasets not in `coo-dashboards.yaml`. Relationship to live datasets is unclear — 47 SPICE datasets exist in the account, only a subset are CloudFormation-managed. |

### 1.3 Live Resources Outside CloudFormation

These resources exist in the account and are actively used but have no CloudFormation management:

| Resource | Type | How Created | Risk |
|---|---|---|---|
| `production-weekly-import-9am-ct` EventBridge rule | EventBridge Rule | Script/console | No drift detection; payload diverges from CF template |
| `production-weekly-import-noon-ct` EventBridge rule | EventBridge Rule | Script/console | Hardcodes 50+ dataset IDs in payload |
| `production-jira-daily-refresh` EventBridge rule | EventBridge Rule | Script/console | No IaC; delete/change leaves no audit trail |
| `production-compliance-email-*` rules (3) | EventBridge Rules | `add_compliance_email_rules.py` | Entirely script-managed |
| `production/weekly-reporting/jira` secret | Secrets Manager | CLI (2026-05-13) | Exists but consumer Lambda was deleted; orphaned |
| Bedrock IAM permissions | IAM Policy | Unknown — not in CF template | No `bedrock:InvokeModel` policy visible in `template.yaml` |
| SES identity / sending permissions | SES + IAM | Unknown | `send_compliance_report` mode calls `sesv2:send_email`; no SES resource in CF |
| `quicksight-vpc-sg` (`sg-0d71ad1d75e0bc310`) | Security Group | Manual/console | No CF tags; no inbound rules; possibly orphaned |
| 47 QuickSight SPICE datasets | QuickSight | Mix of CF + scripts | Only ~12 are CF-managed; rest are manual |
| 81+ database migrations | RDS schema | Lambda `run_query` + scripts | No migration table; no idempotency guarantee |

**Note:** The CF template's EventBridge rules (`ImportScheduleRule9AM`, `ImportScheduleRuleNoon`) use simplified static payloads (`{"mode":"incremental","notify":true}`), while the live rules use richer payloads including `weeks_back`, `snapshot_kpis`, and explicit dataset ID lists. The live rules are the operational ones; the CF rules would **overwrite** live behavior if a stack update were applied.

### 1.4 Lambda Function Summary

| Function | Runtime | Handler | Package Size | VPC | Modes Handled |
|---|---|---|---|---|---|
| `production-clockify-import` | python3.11 | `src.lambda_handler.lambda_handler` | ~95 KB source (19 MB deployed ZIP) | Yes | 30 distinct modes (see §1.5) |

The Lambda code is deployed via `scripts/update_lambda_and_apply_views.sh` — a shell script that zips source, uploads to S3, and calls `update-function-code`. This is outside CloudFormation.

### 1.5 Lambda Modes Inventory

The single `lambda_handler.py` (2,034 lines) dispatches 30 distinct `mode` values:

| Category | Modes | Triggered By |
|---|---|---|
| **Data import** | `weekly`, `incremental`, `full` | EventBridge Mon 9am CT |
| **Jira** | `jira_import`, `jira_fields` | EventBridge daily 10am UTC |
| **KPI** | `snapshot_kpis` (inline in noon import) | EventBridge Mon noon CT |
| **Views** | `apply_views` | Manual / script — **BROKEN** |
| **Compliance email** | `send_compliance_report` | EventBridge Mon 9:30am, 12:30pm, 2:30pm CT |
| **AI analysis** | `analyze_project_health`, `analyze_forecast`, `mc_v2_audit` | Manual |
| **Resource forecast** | `forecast_resources` | Manual |
| **QuickSight** | `refresh_quicksight`, `refresh_quicksight_only`, `create_quicksight_datasets` | Chained from imports |
| **SQL tools** | `run_query`, `run_migration` (appears twice, lines 590 and 1460) | Scripts / manual |
| **Diagnostics** (11 modes) | `diagnose`, `diagnose_users`, `diagnose_contractors`, `diagnose_dates`, `debug_secrets`, `diagnose_ps`, `diagnose_forecasts`, `diagnose_free_agents`, `diagnose_pod`, `diagnose_report_mapping`, `debug_clockify` | Manual ad-hoc |
| **Other** | `run_escalations_import`, `restore_forecasts`, `mc_v2_customers` | Manual |

**Critical observation:** `run_migration` is defined twice (lines 590 and 1460). The second definition silently overrides the first.

### 1.6 Database Schema State

| Item | Count | Notes |
|---|---|---|
| Migration files in `src/database/migrations/` | **91 files** | Sorted by filename prefix at Streamlit startup |
| Duplicate migration number prefixes | **9 collisions** | See §2.1 — execution order is undefined for duplicates |
| `create_views.sql` | 139 KB | ~50+ views; applied via `apply_views` Lambda mode (broken) or `apply_views_direct.py` script |
| Migration tracking table | **None** | No `schema_migrations` table; every migration re-executes on every Streamlit restart |

**Duplicate migration numbers confirmed:**
`002` (×2), `004` (×2), `053` (×2), `059` (×3), `060` (×3), `061` (×2), `062` (×2), `065` (×2)

### 1.7 QuickSight

| Item | Count |
|---|---|
| Dashboards | 7 total (3 active: COO Operational, Executive Summary, Weekly Reporting) |
| SPICE datasets | 47 total (all import mode) |
| Data sources | 1 PostgreSQL (VPC connection) + 1 file upload |
| CF-managed datasets | ~12 (in `coo-dashboards.yaml` + `quicksight-dashboards.yaml`) |
| Manually-managed datasets | ~35 |

---

## Section 2: Stability & Accuracy Risk Assessment

### 2.1 Critical Findings

| # | Severity | Area | Finding | Impact |
|---|---|---|---|---|
| C1 | **Critical** | Data Accuracy | `apply_views` Lambda mode is broken — `create_views.sql` was fixed locally but the Lambda has not been redeployed with the fix | All QuickSight views continue to run against the old view definitions. Any fix applied to `create_views.sql` since the last Lambda deployment is not live. KPI calculations may be wrong. |
| C2 | **Critical** | Data Accuracy | 9 duplicate migration number prefixes (002, 004, 053, 059×3, 060×3, 061, 062, 065) | `apply_pending_migrations()` in `shared.py` sorts files lexicographically and runs them all. For duplicate numbers, execution order is filesystem-dependent. Both files in each collision run every time Streamlit starts — idempotent SQL survives this; DDL changes may not. Specifically: `060_kpi_ytd_prev_columns.sql` and `060_resource_capacity_forecast.sql` both run; the latter could overwrite schema changes made by the former. |
| C3 | **Critical** | Data Accuracy | `pWeekEnd` parameter default is stale (`2026-04-26`) | The COO Operational Analysis dashboard opens to a stale week by default. Any reviewer who opens the dashboard without adjusting the parameter sees 8-week-old data. For executive decision-making this is a high-risk silent error. |
| C4 | **Critical** | Data Accuracy | PS Active Projects KPI shows 24 vs. live view shows 19 — 5-project gap | KPI snapshot (`kpi_weekly_snapshots`) and live view (`vw_ps_project_status`) use different filters. The COO is making decisions based on a count that differs from reality by 5 projects (~26% overstated). Root cause: snapshot computed with a different `issue_type` filter than the view. |

### 2.2 High Findings

| # | Severity | Area | Finding | Impact |
|---|---|---|---|---|
| H1 | **High** | Reliability | No migration tracking table — `apply_pending_migrations()` replays all 91 migrations on every Streamlit restart | Any non-idempotent migration that runs twice will either fail silently (caught by `except Exception`) or corrupt data. Silent failure is the default — migrations that error are printed and skipped, so broken schema changes go undetected. |
| H2 | **High** | Reliability | `run_migration` mode is defined twice in `lambda_handler.py` (lines 590 and 1460) | The second definition silently overrides the first. Any caller relying on the first implementation gets the second. This is an undetected logic bug that has been in production. |
| H3 | **High** | Reliability | Lambda deployment is script-based, outside CloudFormation — `update_lambda_and_apply_views.sh` | Code changes to the Lambda have no IaC audit trail. CloudFormation stack still contains a `ZipFile` placeholder. A stack update would replace the live function with the placeholder. |
| H4 | **High** | Reliability | No dead-letter queue (DLQ) on `production-clockify-import` | If the Monday import fails (Clockify API timeout, DB connection error, etc.), the failure is silent unless the CloudWatch `Errors` alarm fires. The Lambda has a 900-second timeout — a hung invocation will burn the full 15 minutes before the alarm triggers. There is no automatic retry or failure notification beyond the SNS alarm. |
| H5 | **High** | Reliability | Single-AZ RDS (`db.t3.micro`, `us-east-1b`) — no Multi-AZ standby | An AZ failure or instance failure causes a complete data pipeline outage. Recovery requires manual RDS restore (20–30 minutes minimum). The Monday import cycle would be missed entirely. |
| H6 | **High** | Observability | CloudFormation drift detection not run on any of the 4 project stacks | Live state has diverged from IaC in multiple known ways (EventBridge payloads, Lambda code). Unknown drift may exist elsewhere. A stack update is dangerous without first running drift detection. |
| H7 | **High** | Security | QuickSight → RDS data source has `DisableSsl: true` | All data in transit between QuickSight and RDS is unencrypted. This includes all time tracking, project health, escalation, and KPI data. |
| H8 | **High** | Security | Bedrock IAM permissions and SES sending permissions are not in `cloudformation/template.yaml` | The Lambda calls `bedrock-runtime:InvokeModel` (Claude Sonnet 4.5) and `sesv2:SendEmail`. Neither permission appears in the Lambda execution role in CF. These were added manually. A stack update would remove them, breaking `analyze_project_health`, `mc_v2_audit`, and `send_compliance_report` modes. |

### 2.3 Medium Findings

| # | Severity | Area | Finding | Impact |
|---|---|---|---|---|
| M1 | **Medium** | Observability | CloudWatch alarm fires on Lambda `Errors ≥ 1` but there is no alarm on Lambda `Duration` approaching timeout (900s) | A hung Lambda (e.g., Clockify API stall) will not alert until the invocation fails or completes. The import can consume the full 15 minutes silently. |
| M2 | **Medium** | Observability | No alarm on EventBridge rule invocation failures | If EventBridge cannot invoke the Lambda (throttle, permission error), it fails silently. The CloudWatch alarm only triggers after the Lambda itself errors. |
| M3 | **Medium** | Observability | No monitoring on QuickSight SPICE refresh failures | The noon import triggers ~50 dataset refreshes. If any fail, the only indicator is a stale dataset timestamp visible in the QuickSight console. No alarm, no SNS notification. |
| M4 | **Medium** | Configuration Drift | 5 EventBridge rules are script-managed and not in CloudFormation | Payloads diverge from what the CF template defines. A stack update silently restores simplified payloads, breaking the noon KPI snapshot chain and COO dataset refresh targeting. |
| M5 | **Medium** | Configuration Drift | `production/weekly-reporting/jira` Secrets Manager secret is orphaned — consumer Lambda was deleted 2026-05-13 | Live Jira credentials sitting in Secrets Manager with no defined consumer. Security risk if the Jira token is not rotated. |
| M6 | **Medium** | Data Accuracy | `create_views.sql` (139 KB) is the single source of truth for all views but is not applied atomically | Views are applied statement-by-statement via `apply_views_direct.py`. A mid-run failure leaves the database in a partially-updated view state with no rollback. |
| M7 | **Medium** | Reliability | ECS deployment circuit breaker disabled on `production-dashboard-service` | A bad container deployment will not auto-rollback. It stalls until manually intervened. Last deployment was 2026-05-08. |
| M8 | **Medium** | Reliability | Streamlit `apply_pending_migrations()` runs migrations at process startup, before the UI is ready | If a migration takes a long time or errors, Streamlit silently swallows it and continues loading. Users see stale data with no error indicator. |

### 2.4 Low / Info Findings

| # | Severity | Area | Finding |
|---|---|---|---|
| L1 | **Low** | Complexity | Lambda handler is 2,034 lines with 30 modes — a single timeout or unhandled exception in one mode can affect all modes sharing the same execution environment. |
| L2 | **Low** | Complexity | `create_views.sql` at 139 KB is a single monolithic file covering 50+ views. A syntax error anywhere in the file causes the entire apply to fail. |
| L3 | **Low** | Hygiene | 5 dead deployment artifacts in repo root: `lambda-deployment-package.zip`, `lambda-deployment-package-coo.zip`, `lambda-deployment-package-backup.zip`, `lambda-min.zip`, `lambda_function.zip` (total ~85 MB) |
| L4 | **Low** | Hygiene | 6 empty placeholder files in repo root: `--profile`, `--services`, `--output`, `--query`, `--region`, `--cluster` (shell script redirect artifacts) |
| L5 | **Low** | Hygiene | `lambda_package_temp/` and `lambda_package_min/` directories contain stale extracted deployment packages (contain source from March 2026) |
| L6 | **Low** | Security | ECS Exec is enabled on `production-dashboard-service` — allows shell access to the running Streamlit container from anyone with `ecs:ExecuteCommand` IAM permission |
| L7 | **Info** | Architecture | `streamlit-ecs.yaml` exists in the repo but the live ECS deployment is managed by `production-weekly-reporting-dashboard` stack — two templates for the same deployment creates confusion about which is authoritative |


---

## Section 3: Simplification Opportunities

### 3.1 Lambda Architecture — Monolith vs. Split

**Current state:** A single 2,034-line handler handles 30 modes ranging from the Monday import to AI analysis to ad-hoc SQL execution and 11 diagnostic modes. This means:
- A bug or exception in a diagnostic mode can mask or interfere with the production import path
- The 900-second timeout is sized for the longest operation (full import); short modes like `refresh_quicksight_only` inherit a 15-minute timeout unnecessarily
- The entire 19 MB deployment package must be redeployed to fix any single mode

**Recommendation:** Do not split aggressively — the overhead of managing multiple Lambdas for an internal tool is not justified. Instead, apply two targeted changes:

1. **Retire all 11 diagnostic modes from the Lambda.** `diagnose`, `diagnose_users`, `diagnose_contractors`, `diagnose_dates`, `debug_secrets`, `diagnose_ps`, `diagnose_forecasts`, `diagnose_free_agents`, `diagnose_pod`, `diagnose_report_mapping`, `debug_clockify`. These exist only to run queries from outside the VPC. Replace them with: connect to RDS directly via SSM port-forward (already available — SSM session manager bundle is in the repo). Diagnostic mode code adds ~400 lines to the handler and increases the attack surface.

2. **Extract `run_query` and `run_migration` as a protected utility.** These allow arbitrary SQL execution against production RDS via Lambda invocation. Any IAM principal with `lambda:InvokeFunction` on `production-clockify-import` can run arbitrary SQL. Gating these behind an explicit allowlist of known safe operations (or removing them) would eliminate this risk.

### 3.2 IaC Gaps — Bring Out-of-Band Resources into CloudFormation

These resources are active in production but unmanaged by IaC. Priority order for remediation:

| Priority | Resource | Recommended Action |
|---|---|---|
| **1 — High** | Bedrock IAM permissions (`bedrock-runtime:InvokeModel`) | Add to `LambdaExecutionRole` in `template.yaml`. Without this, a stack update deletes the permission and breaks 3 Lambda modes. |
| **2 — High** | SES sending permissions (`sesv2:SendEmail`, SES identity) | Add `SESAccess` policy to `LambdaExecutionRole`. Add SES identity ARN as a parameter. |
| **3 — High** | 5 EventBridge rules (all Monday + daily schedules) | Replace the simplified CF rules with the actual operational payloads, or import live rules into CF using `aws cloudformation import-resources`. Do not run a stack update until the live EventBridge rules match CF definitions. |
| **4 — Medium** | `production/weekly-reporting/jira` Secrets Manager secret | Either delete it (if Jira is handled by the existing secret) or import into CF. Currently an orphaned secret with a live API token. |
| **5 — Medium** | QuickSight data source SSL setting | Update `Weekly-Reporting-PostgreSQL` data source in `coo-dashboards.yaml`: `DisableSsl: false`. Then update live via CF stack update. |
| **6 — Low** | Unmanaged SG `sg-0d71ad1d75e0bc310` | Check if attached to any resource; delete if unused. |

### 3.3 Migration Management — 91 Files with No Tracking Table

**Current state:** `shared.py:apply_pending_migrations()` sorts all `*.sql` files by filename and re-executes every one on every Streamlit startup. There is no `schema_migrations` tracking table. Most DDL is written with `CREATE TABLE IF NOT EXISTS` or `CREATE OR REPLACE VIEW`, which makes them naturally idempotent. However:

- 9 duplicate number prefixes mean two files sort to adjacent positions with the same prefix — both execute every time
- Non-idempotent data operations (backfill migrations, seed data inserts) run repeatedly, potentially duplicating rows
- A migration that fails is silently swallowed and the next one runs anyway — there is no atomic transaction boundary between migrations

**Recommendation:**

1. **Add a `schema_migrations` tracking table** (one row per applied filename + applied-at timestamp). `apply_pending_migrations()` checks the table and skips already-applied files. This is a 20-line change to `shared.py` and a single `CREATE TABLE IF NOT EXISTS` migration. This is the highest-value reliability improvement available with minimal effort.

2. **Rename the 9 duplicate-numbered files** to remove the ambiguity. Assign them sequential numbers from 082 onward (after the current highest, 081). The content of the files is correct — only the filename prefix needs to change.

3. **Do not remove migrations** — they are the audit trail of schema evolution. Once a tracking table exists, old migrations become no-ops for deployments that have already run them.

### 3.4 Streamlit Deployment — Local vs. ECS

**Current state:** The ECS Fargate service (`production-dashboard-service`) is confirmed running (1 task, task definition revision 4, last deployed 2026-05-08). The Streamlit app runs in ECS on `app.py` (103 KB, accessed via ALB). Local mode is available as a fallback via `DATABASE_URL` in `.env`.

**What to standardize:**
- ECS is the production runtime. The `streamlit-ecs.yaml` template is a stale copy; the live stack is `production-weekly-reporting-dashboard`. **Delete `cloudformation/streamlit-ecs.yaml`** or clearly label it as archived.
- The Streamlit app auto-applies all 91 migrations on startup in ECS. This means every ECS task restart re-runs all migrations. With the tracking table fix (§3.3), this becomes safe. Without it, it is an ongoing risk.
- The known redundancy (Dashboard/Resource Directory tabs duplicate QuickSight) should be addressed: either remove the redundant Streamlit tabs or deprecate the Streamlit dashboard entirely for those views. The QuickSight COO dashboards are the primary governance tool; the Streamlit app's value is in write operations (forecast uploads, user management) and views not available in QuickSight.

### 3.5 Script Sprawl — 93 Scripts

The `scripts/` directory has accumulated 93 files, most of which are one-off fixes applied at a specific point in time. Classification:

**Permanently useful (keep and document):**

| Script | Why Keep |
|---|---|
| `apply_views_direct.py` | The only reliable way to apply `create_views.sql` while `apply_views` Lambda mode is broken |
| `update_lambda_and_apply_views.sh` | Standard Lambda deployment script |
| `sync_coo_dashboard_iac.py` | Exports live QuickSight analysis → `coo-dashboards.yaml` |
| `export_live_analysis.py` | Snapshot live analysis to JSON for backup |
| `republish_from_analysis.py` | Republish COO dashboard from current analysis |
| `publish_coo_dashboard.py` | Publish from analysis definition |
| `check_spice_health.py` / `check_all_spice.py` | SPICE ingestion status checks |
| `full_status_check.py` | System health overview |
| `dashboard_accuracy_audit.py` | Data freshness + SPICE audit |
| `add_compliance_email_rules.py` | Re-creates EventBridge compliance email rules (needed if rules are lost) |
| `deploy_dashboard.sh` / `deploy_dashboard_stack.sh` | Dashboard deployment automation |
| `refresh_quicksight_datasets.py` | Manual SPICE refresh trigger |

**One-off fixes — can be archived (move to `scripts/archive/`):**

All `fix_*.py`, `diag_*.py`, `check_*.py`, `patch_*.py`, and `add_*.py` scripts created before 2026-05-01 (approximately 55 scripts). These were applied at specific points in time to fix a specific visual, conditional formatting rule, or data issue. They are not repeatable operations and running them again could overwrite current state. They should be archived rather than deleted, as they document the fix history.

**Can be deleted:**
- `generate_password_hash.py` — utility replaced by the `app_users` DB table
- Scripts that operate on deleted resources (e.g., anything targeting `clockify-data-processor` or `jira-data-pull-lambda`)

### 3.6 View Management — `create_views.sql` at 139 KB

**Current state:** All 50+ views are defined in a single 139 KB SQL file. Every change requires editing this file and re-running the entire apply process.

**Risks with the current approach:**
- A syntax error anywhere in the file halts the apply mid-run, leaving a partially-updated view state
- There is no version history for individual views (only the overall file in git)
- View dependencies (view A references view B) must be maintained by the developer manually — the file must be ordered correctly

**Recommendation (pragmatic for a single-operator system):**
Split `create_views.sql` into one file per view, named `vw_{view_name}.sql`, in a `src/database/views/` directory. The apply process becomes: `DROP VIEW IF EXISTS ... CASCADE; CREATE VIEW ...` for each file, in dependency order. This makes each view independently version-controlled and testable. The `apply_views_direct.py` script already handles statement-level execution — it can be adapted to execute a directory of view files instead of one large file.

This is a medium-effort refactor with no runtime behavior change.

---

## Section 4: Immediate Action Items

### Fix Now — Before Next Monday Import Cycle (by 2026-06-30)

| Priority | Action | File / Resource | Effort | Risk If Skipped |
|---|---|---|---|---|
| **1** | Redeploy Lambda with fixed `apply_views` mode | `scripts/update_lambda_and_apply_views.sh` | 30 min | Views remain on stale definitions indefinitely; KPI accuracy at risk |
| **2** | Fix stale `pWeekEnd` parameter default (`2026-04-26` → current week) | `cloudformation/coo-dashboards.yaml` → re-sync from live via `sync_coo_dashboard_iac.py` | 15 min | COO opens dashboard to 8-week-old data by default on every session |
| **3** | Investigate and fix PS Active Projects KPI gap (24 vs. 19) | `src/integrations/kpi_snapshot.py` + `src/database/create_views.sql` | 2–4 hrs | COO making decisions based on project count overstated by ~26% |
| **4** | Add Bedrock and SES IAM permissions to `template.yaml` | `cloudformation/template.yaml` → `LambdaExecutionRole` | 30 min | Next CF stack update will silently delete these permissions, breaking compliance emails and AI analysis |
| **5** | Update EventBridge rules in CF to match live payloads | `cloudformation/template.yaml` | 1 hr | Any CF stack update will overwrite live EventBridge rules with simplified payloads, breaking the noon KPI snapshot chain |
| **6** | Add `schema_migrations` tracking table | New migration `082_schema_migrations_tracking.sql` + update `shared.py` | 2 hrs | 91 migrations replay on every Streamlit restart; duplicate numbers run conflicting DDL |

### Fix This Week — Before Next Monday

| Priority | Action | File / Resource | Effort |
|---|---|---|---|
| **7** | Rename the 9 duplicate-numbered migration files | `src/database/migrations/` | 1 hr |
| **8** | Enable SSL on QuickSight → RDS data source | `coo-dashboards.yaml` + live QuickSight console | 1 hr |
| **9** | Run CloudFormation drift detection on all 4 project stacks | AWS console or CLI | 30 min |
| **10** | Decide fate of orphaned `production/weekly-reporting/jira` secret | AWS Secrets Manager console | 15 min |
| **11** | Add SQS DLQ to `production-clockify-import` + CloudWatch alarm | `cloudformation/template.yaml` | 2 hrs |

### Schedule — Next Sprint

| Action | Effort | Notes |
|---|---|---|
| Remove/archive the 11 diagnostic Lambda modes | 3–4 hrs | Reduces handler by ~400 lines; eliminates arbitrary SQL risk |
| Add CloudWatch alarm on Lambda Duration > 600s | 30 min | Early warning before 900s timeout hit |
| Split `create_views.sql` into per-view files | 4–6 hrs | Improves maintainability significantly |
| Archive ~55 one-off fix scripts to `scripts/archive/` | 1 hr | Reduces scripts/ confusion without losing history |
| Delete dead deployment artifacts from repo root (5 ZIPs, ~85 MB) | 15 min | Reduces repo size and confusion |
| Enable ECS deployment circuit breaker | 30 min | `cloudformation/streamlit-ecs.yaml` or via console |
| Evaluate Multi-AZ upgrade for RDS | 2 hrs | Currently single-AZ `db.t3.micro`; ~$30/month incremental cost for Multi-AZ `db.t3.micro` |

---

## Summary

The system is functionally operational and successfully running the weekly reporting cycle. The most significant risks are accuracy risks, not availability risks: the COO is currently viewing data through stale views (`apply_views` broken), a stale default week parameter, and a KPI metric that overstates active projects by 26%. These three issues affect the primary purpose of the system — executive decision-making — and should be fixed before the next Monday cycle.

The infrastructure has accumulated meaningful IaC drift: Bedrock and SES permissions are not in CloudFormation, EventBridge payloads diverge from the CF template, and the Lambda code is deployed outside CF entirely. The immediate danger is that a well-intentioned `aws cloudformation update-stack` to fix something small would silently overwrite the live EventBridge rules and delete the Bedrock/SES IAM permissions. Do not run a stack update until items 4 and 5 in the immediate action list are completed.

The migration duplicate-numbering issue is the highest-latent reliability risk: migrations 059, 060, and 062 each have three files all running on every Streamlit restart. This has not caused a visible outage because most of the duplicate operations happen to be idempotent, but this is luck, not design.

**MCP Note:** If any MCP tools returned no results or behaved unexpectedly, your MCP server session may have expired. Run `kiro mcp login` to re-authenticate.
