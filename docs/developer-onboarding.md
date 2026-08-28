# Developer Onboarding — Weekly Reporting

> Last updated: 2026-07-17
> For the deployed system in AWS account `961341524729`, region `us-east-1`.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Original Requirements](#2-original-requirements)
3. [System Architecture](#3-system-architecture)
4. [Data Pipeline](#4-data-pipeline)
5. [The Three Dashboards](#5-the-three-dashboards)
6. [Current State](#6-current-state)
7. [Developer Setup](#7-developer-setup)
8. [Making Changes](#8-making-changes)
9. [Key Files Reference](#9-key-files-reference)
10. [Monitoring & Alerts](#10-monitoring--alerts)

---

## 1. Project Overview

### What this system does

The Weekly Reporting system is Cloudelligent's internal operations intelligence platform. It automatically pulls time tracking data from **Clockify** and project status data from **Jira** every Monday morning, stores everything in a **PostgreSQL database** on AWS RDS, and surfaces the data through two **QuickSight dashboards** and a **Streamlit web app**.

The result is a single source of truth for weekly operational decision-making. Before this system existed, the COO had to manually compile reports from multiple sources to answer basic questions like "how is on-time delivery trending?" or "who hasn't logged time this week?"

### Who uses it

| User | What they use | Why |
|------|--------------|-----|
| **COO** | All three dashboards | Weekly operational review meeting, OKR tracking, governance |
| **Practice Leads** (PS, MC, MIT) | KPI Tracking Dashboard (Sheet 2), Streamlit | Monitor their practice's health and compliance |
| **Staff** | KPI Tracking Dashboard (Sheet 3) | Visibility into how their practice/POD is performing |
| **Operations team** | Streamlit app | Data entry, compliance tracking, project configuration |
| **Delivery managers** | Streamlit app + COO dashboard | Project health, resource capacity, escalations |

### Business context

Cloudelligent is a cloud consulting firm with approximately 71 staff across five lines of business:

| Line of Business | Abbreviation | What they do |
|-----------------|-------------|--------------|
| Professional Services | PS | AWS project delivery (migrations, builds, optimizations) |
| Managed Cloud Services | MC | Ongoing managed cloud operations for clients |
| Managed IT | MIT | Managed IT services |
| FinOps | FINOPs | Cloud cost optimization practice |
| Product | Product | Internal product development |

Staff are also organized into **PODs** (Alpha, Bravo, Charlie, A2Z, Free Agent) — cross-functional delivery teams that are parallel to practice lines, not a hierarchy within them.

### 2026 COO OKRs this system supports

The system directly measures and tracks these key results:

| KR | Description | Q2 Target | Q4 Target | How Measured |
|----|-------------|-----------|-----------|--------------|
| **KR2.1** | PS on-time delivery rate | 60% | 90% | `ps_on_time_pct` in `kpi_weekly_snapshots` |
| **KR2.2** | Avg PS engagement duration | 10 weeks | 5 weeks | `ps_avg_duration_weeks` in `kpi_weekly_snapshots` |
| **KR2.4** | Projects in Red < 10% | < 20% | < 10% | `total_projects_red` in `kpi_weekly_snapshots` |
| **KR5.1** | 95%+ data hygiene + real-time COO visibility | 80% hygiene | 95%+ | Time compliance %, data freshness |

**One-week-in-arrears rule:** All dashboards report on the most recently *completed* week. The current in-progress week is always excluded. "This week" in the UI means "last completed week."

---

## 2. Original Requirements

### The problem this system was built to solve

Before this system, weekly operational reporting at Cloudelligent was:

- **Manual** — the COO or ops team had to pull data from multiple sources and compile it by hand
- **No historical compliance view** — you could see who missed time this week but not whether there was a pattern
- **No utilization breakdown by practice** — total company utilization was visible but not PS vs MC vs MIT
- **No profitability tracking** — no unified view of onshore/offshore mix, contractor vs FTE cost, or SOW burn
- **No automated project health trending** — project health (Green/Amber/Red from Jira) wasn't correlated with time data

### Three-tier reporting model

The system is designed as a hierarchy of detail:

```
Tier 1: Executive Summary (QuickSight)
         → 1-2 page weekly pulse for CEO/COO
         → Delivery health at a glance

Tier 2: COO Operational Analysis (QuickSight)
         → Full weekly meeting walkthrough
         → State of service delivery across PS + MC
         → Used during the Monday leadership meeting

Tier 3: Weekly Reporting Streamlit App
         → Granular operational control layer
         → Individual tracking, compliance, PM/project analysis
         → Data entry and configuration
         → Everything QuickSight can't do interactively
```

### The 17-tab Streamlit spec

The Streamlit app was designed as a 17-tab operational dashboard. Each tab serves a specific operational purpose:

| Tab | Name | Purpose |
|-----|------|---------|
| 1 | Weekly Operations Summary | Hours by practice, POD, location — the weekly pulse |
| 2 | PS Project Status | Jira project health, stage, schedule |
| 3 | PS Profitability | Billable hours vs. rates vs. SOW burn |
| 4 | MC Service Delivery | MC customer health and ticket activity |
| 5 | Missing Time Report | Who hasn't logged time — current week + historical |
| 6 | Resource Forecast | PM forecast vs. capacity model (12-week forward view) |
| 7 | Resource Capacity | PS staff availability heatmap (8-week forward) |
| 8 | PS Delivery Analysis | AI-generated project health narratives (Bedrock) |
| 9 | Non-Billable Analysis | NB hour breakdown by category and trend |
| 10 | MC V2 Audit | Confluence artifact verification for MC methodology compliance |
| 11 | Project Hours Trend | 12-week project hours trend |
| 12 | Escalations | Open escalation tracker |
| 13 | Productive Utilization | Billable + productive NB breakdown |
| 14 | Project Time Detail | Last 4 weeks of time entries, filterable |
| 15 | Customer Status Assignments | Active Jira queue by engineer |
| 16 | Project Runway | SOW burn rate and estimated completion |
| 17 | Organizational KPI Scorecard | QTD KPI summary (superseded by KPI Tracking Dashboard) |

Full acceptance criteria for each tab are in `docs/weekly-reporting-dashboard-spec.md`.

### KPI Tracking Dashboard requirements

The KPI Tracking Dashboard was built to give the COO and staff OKR visibility across three audiences:

- **Sheet 1 (OKR Scorecard):** Company-level KPI tiles with trend charts and OKR quarterly targets
- **Sheet 2 (Practice Scorecard):** Practice/LoB breakdown with cross-practice comparison
- **Sheet 3 (Staff Detail):** Individual-level compliance and utilization visibility

Full requirements and redesign spec are in `docs/kpi-dashboard-proposal.md` and `docs/kpi-dashboard-redesign-brief.md`.

---

## 3. System Architecture

### Data flow

```
Clockify API ────────────────────────────────────────┐
                                                      ▼
                                          Lambda: production-clockify-import
Jira API ───────────────────────────────────────────▶│ (Python 3.11, 900s timeout)
                                                      │
                                                      ▼
                                          RDS PostgreSQL
                                          (weekly_reporting DB)
                                                      │
                              ┌───────────────────────┤
                              │                       │
                              ▼                       ▼
                   QuickSight SPICE           ECS Fargate (Streamlit)
                   (53 datasets)              production-dashboard-service
                              │                       │
                    ┌─────────┴──────────┐            │
                    ▼                    ▼             ▼
           COO Operational       KPI Tracking    Streamlit Web App
           Dashboard             Dashboard       (ALB endpoint)
```

### AWS infrastructure

**Account:** `961341524729` | **Region:** `us-east-1`

| Resource | Name / Identifier | Notes |
|----------|------------------|-------|
| **Lambda** | `production-clockify-import` | Python 3.11, 900s timeout, 512MB. Handles ALL import modes AND serves as the DB query execution endpoint. |
| **RDS** | `production-weekly-reporting.cn0g6iw42ap2.us-east-1.rds.amazonaws.com` | PostgreSQL, private subnet. Database name: `weekly_reporting` |
| **ECS Cluster** | `production-weekly-reporting` | Runs the Streamlit app |
| **ECS Service** | `production-dashboard-service` | Fargate, public-facing via ALB |
| **ECR** | `961341524729.dkr.ecr.us-east-1.amazonaws.com/production-weekly-reporting-dashboard` | Docker image for Streamlit |
| **ALB** | `http://production-dashboard-alb-607632442.us-east-1.elb.amazonaws.com` | Streamlit app URL |
| **EventBridge** | `production-weekly-import-9am-ct` | Mon 9am CT `cron(0 14 ? * MON *)` |
| **EventBridge** | `production-weekly-import-noon-ct` | Mon noon CT `cron(0 17 ? * MON *)` |
| **SNS Topic** | `production-weekly-reporting-notifications` | Alerts: SPICE failures, Lambda errors |
| **Secrets Manager** | `production/weekly-reporting/secrets` | Clockify API key, Jira credentials, DB password, `master_database_url` |
| **CloudFormation** | `weekly-reporting-production` | Main infrastructure stack |
| **CloudFormation** | `production-weekly-reporting-dashboard` | Streamlit ECS stack |

### Database

**DB Users — this matters:**

| User | Permissions | When to Use |
|------|------------|-------------|
| `postgres` | Superuser — can CREATE/DROP/ALTER | DDL operations only (view changes, migrations) |
| `report_user` | SELECT, INSERT, UPDATE on application tables | All application queries |

**Critical:** DDL operations (creating views, running migrations that ALTER tables) **must use the master credentials** (`master_database_url` from Secrets Manager). The `report_user` cannot ALTER or CREATE objects owned by postgres. The Lambda runs DDL by fetching `master_database_url` from Secrets Manager when the mode is `apply_views` or `run_query`.

**Key tables:**

| Table | What it stores |
|-------|---------------|
| `clockify_users` | User roster — capacity hours, POD, practice alignment, LoB |
| `clockify_detailed_time_entries` | Raw time entries from Clockify |
| `clockify_projects` | Project metadata with `project_type`, `pod_assignment` |
| `ps_project_status` | Jira PS/MC project health synced daily (stage, health, PM, SA, budget) |
| `ps_project_mapping` | Maps Clockify project/client names to Jira projects (used for LoB classification) |
| `kpi_weekly_snapshots` | Weekly point-in-time KPI snapshots — the source for all KPI dashboards |
| `lob_practice_mapping` | Maps `practice_alignment` string → LoB (PS/MC/MIT/FINOPs/Product/Internal) |
| `import_logs` | Audit trail of all Lambda import runs |
| `ps_resource_forecast_v2` | Capacity model forecast (authoritative for forward capacity) |
| `ps_resource_forecasts` | PM-uploaded Excel forecasts (comparison only, not authoritative) |
| `escalations` | Open escalation tickets from Jira |

**Migrations:** Sequential SQL files in `src/database/migrations/`. Currently 001 through 102. Apply via Lambda `apply_views` mode or directly via `scripts/apply_views_direct.py`.

**Views:** All production views are defined in `src/database/create_views.sql`. Apply with Lambda `{"mode": "apply_views"}`. Views are recreated (DROP + CREATE) each time — this is idempotent.

### Key data concepts

**Line of Business (LoB):** Derived from the `lob_practice_mapping` table, which maps a user's `practice_alignment` string (free-text Clockify custom field, e.g., "Managed Cloud Services") to one of: `PS`, `MC`, `MIT`, `FINOPs`, `Product`, `Internal`.

> **Do not confuse with `practice_area`** — `practice_area` is an enum column (`PS`, `MC`, `Both`, `MIT`, `Internal`, `Exempt`) added to `clockify_users` during the dashboard redesign. It was backfilled for all 69 active users. `practice_alignment` is the raw Clockify free-text field. Both exist. `practice_area` is cleaner for filtering but `practice_alignment` drives LoB classification.

**Practice Alignment:** The raw Clockify custom field value. Single values only — compound values like "AI/ML,WAFR" cause double-counting in aggregations and should be avoided.

**POD:** Team assignment (Alpha, Bravo, Charlie, A2Z, Free Agent). This is a parallel dimension to practice — a PS engineer can be in any POD. It is NOT a hierarchy within practice.

**Reporting cycle:** One week in arrears. All dashboards default to the most recently completed ISO week (Monday–Sunday). The current in-progress week is always excluded.

**Project-based classification:** Hours are classified as PS/MC/Other based on `ps_project_mapping.category` (with `ps_project_status.category` as fallback), NOT based on employee attributes like `practice_area`. This is the COO alignment rule — the dashboard and Streamlit app should agree because they use the same classification source.

---

## 4. Data Pipeline

### Lambda modes

The Lambda function (`production-clockify-import`) is the workhorse of the entire system. It accepts a `mode` parameter and handles everything from data imports to view deployment to diagnostics.

| Mode | What it does | When to use |
|------|-------------|-------------|
| `incremental` | Pulls new Clockify time entries since the last import | Monday automation (default) |
| `weekly` | Pulls last 1 week of Clockify data | Ad-hoc refresh |
| `full` | Pulls last 52 weeks of Clockify data | Initial load only — slow |
| `apply_views` | Drops and recreates all PostgreSQL views from `create_views.sql` | After any view change |
| `jira_import` | Syncs PS/MC project status from Jira | Daily automation + ad-hoc |
| `snapshot_kpis` | Computes a weekly KPI snapshot row in `kpi_weekly_snapshots` | Monday automation after import |
| `run_query` | Executes arbitrary SQL (uses master credentials) | Diagnostics, DDL that can't run as report_user |
| `apply_views` | Re-applies all views from `create_views.sql` using postgres superuser | After view changes |
| `ai_analysis` | Runs Bedrock-powered project health analysis | Monday automation |
| `refresh_spice` | Triggers QuickSight SPICE refresh for all 53 datasets | Monday automation |
| `send_compliance_email` | Sends compliance status email to recipients | Mon 9:30am, 12:30pm, 2:30pm CT |

### Monday automated run sequence

Every Monday the system runs two passes:

**9am CT (EventBridge triggers Lambda):**
1. `apply_views` — ensures all views are current
2. Clockify incremental import
3. Jira import
4. `snapshot_kpis` — computes the week's KPI row
5. AI analysis (Bedrock)
6. SPICE refresh (all 53 datasets)
7. Compliance emails sent at 9:30am, 12:30pm, 2:30pm CT

**Noon CT (second EventBridge trigger):**
- `incremental` import + KPI snapshot + targeted SPICE refresh
- Catches any updates missed by the morning run

### SPICE datasets (53 active)

All QuickSight visuals use SPICE (in-memory cache), not live DB queries. The Lambda refreshes all 53 datasets on each Monday run. Key datasets:

| Dataset ID | Source | Used by |
|-----------|--------|---------|
| `kpi-weekly-snapshots-prod` | `vw_kpi_ytd` | COO dashboard KPI tiles, KPI Tracking Sheet 1 |
| `kpi-staff-weekly-prod` | `vw_kpi_staff_weekly` | KPI Tracking Dashboard all 3 sheets |
| `kpi-practice-weekly-prod` | `vw_practice_kpi_weekly` | KPI Tracking Dashboard Sheet 2 |
| `ps-project-status-view` | `vw_ps_project_status` | COO PS Delivery sheet |
| `productive-utilization` | `vw_productive_utilization` | COO Time & Utilization sheet |
| `clockify-missing-time-submissions-prod` | `vw_missing_time_submissions` | COO compliance visuals |
| `project-hours-summary-prod` | `vw_project_hours_summary` | COO dashboard, project trend charts |
| `escalations-detail` | `vw_escalations` | COO Escalations sheet |
| `mc-ticket-activity` | `vw_mc_ticket_activity` | COO MC Delivery sheet |

**SPICE failure pattern:** If a view is dropped or a column is renamed, the SPICE dataset that depends on it will fail on the next refresh. The CloudWatch alarm `weekly-reporting-spice-failure` fires when this happens. Fix: apply the corrected view, then re-run `{"mode": "apply_views"}` + trigger a SPICE refresh.

---

## 5. The Three Dashboards

### Dashboard 1: COO Operational Dashboard

| Property | Value |
|----------|-------|
| **Dashboard ID** | `coo-operational-dashboard-prod` |
| **Analysis ID** | `coo-operational-analysis-prod` |
| **Audience** | COO, leadership team |
| **IaC** | `cloudformation/coo-dashboards.yaml` |
| **Date filter** | `pWeekStart` DateTimePicker — pick a specific reporting week |

**Sheets:**

| Sheet | Purpose |
|-------|---------|
| Weekly Pulse | Top-line KPIs: utilization, compliance, escalations. Utilization trend line. |
| PS Delivery | PS project health donut, stage pipeline, project health table with RAG colors |
| MC Service Delivery | MC customer health, ticket activity, hours by customer |
| Time & Utilization | Compliance KPIs, non-compliant staff table, utilization breakdown |
| Compliance History | Historical compliance trend by week |
| Utilization History | Historical utilization trend by week |
| Resource Capacity | 12-week forward capacity heatmap |
| Org KPI Scorecard | 4 QTD KPI tiles + monthly trend charts (added 2026-06-10) |

**Theme:** `cloudelligent-brand-theme` (CE MIDNIGHT base). The theme must be preserved on every dashboard update — scripts that call `update_dashboard` must include `ThemeArn`. See `docs/theme-issue-analysis-2026-06-29.md` for the history of how the theme gets accidentally stripped.

---

### Dashboard 2: KPI Tracking Dashboard

| Property | Value |
|----------|-------|
| **Dashboard ID** | `kpi-tracking-dashboard-prod` |
| **URL** | `https://us-east-1.quicksight.aws.amazon.com/sn/dashboards/kpi-tracking-dashboard-prod` |
| **Audience** | COO (Sheet 1), Practice Leads (Sheet 2), Staff (Sheet 3) |
| **Primary dataset** | `kpi-staff-weekly-prod` (kpi_staff) for all 3 sheets |
| **Build script** | `scripts/build_kpi_dashboard.py` (idempotent — deletes and recreates analysis + dashboard) |

**Sheets:**

**Sheet 1 — OKR Scorecard**
- 8 company-level KPI tiles: Billable Util %, Productive Util %, Timesheet Compliance %, PS On-Time Delivery %, Avg Engagement Duration, Projects in Red %, Open Escalations, Active Resources
- Trend charts for utilization, on-time delivery, compliance
- Project health stacked bar (PS + MC combined)
- Date filter: `Reporting Period` — RelativeDateTime control (Last Week / Last Month / Last Quarter / Last Year)

**Sheet 2 — Practice Scorecard**
- All metrics from `kpi_practice` dataset grouped by `practice_alignment` / LoB
- Cross-practice comparison bar charts (utilization % and compliance % side-by-side)
- Correct headcount via `DISTINCT_COUNT(user_name)`
- Filter hierarchy: Line of Business → Practice Alignment

**Sheet 3 — Staff Detail**
- Individual staff rows with all KPIs
- Compliance status with RAG colors
- Productive utilization %
- POD compliance bar chart
- Filter hierarchy: Line of Business → Practice Alignment → POD → Individual Staff Member

**Patch scripts:** `scripts/patch_kpi_*.py` — use these for targeted fixes without a full rebuild. A full rebuild via `build_kpi_dashboard.py` deletes and recreates the entire analysis and dashboard, which takes several minutes.

**Known design issues (from redesign brief):**
- Filter controls on Sheets 2 and 3 were non-functional in early versions (fixed in v19)
- Compliance % tile on Sheet 3 may display as decimal (0.72) instead of percentage — check if you see this
- Default date should be last completed week, not the current in-progress week
- `projects_red_pct` calculated field should power the "Projects in Red %" tile (not the raw count)

Full redesign specification is in `docs/kpi-dashboard-redesign-brief.md`.

---

### Dashboard 3: Streamlit App

| Property | Value |
|----------|-------|
| **URL** | `http://production-dashboard-alb-607632442.us-east-1.elb.amazonaws.com` |
| **Code** | `src/app.py` (~3,500 lines) |
| **Audience** | COO governance, operations team, practice leads |
| **Deploy** | `./scripts/deploy_dashboard.sh` |

The Streamlit app is the operational control layer — it does things QuickSight cannot:
- Inline data entry (compliance reasons, practice area assignments, profitability rates)
- Import controls (trigger imports manually, view import logs)
- Configuration management (LoB mapping editor, practice area editor, forecast config)
- Granular drill-downs beyond what static dashboard sheets can provide

**Multi-page structure:**

| Page | Path in app | Purpose |
|------|------------|---------|
| Main app | `src/app.py` | All 17 tabs |
| AI Analysis | Extracted to own page | Bedrock-powered project health narratives |
| Data Management | Settings section | Import controls, SPICE refresh trigger |
| Settings | Settings section | Practice area editor, LoB mapping editor, profitability rates, forecast config |

**17 tabs** (see Section 2 for full list). All are implemented as of Sprint 6 (2026-06-10).

**Deployment:** The Streamlit app runs as a Docker container on ECS Fargate. Changes to `src/app.py` or any dependency require a new Docker image push to ECR and an ECS service update. Use `./scripts/deploy_dashboard.sh` — it handles the build, push, and service update.

---

## 6. Current State

### What's working

As of 2026-07-17, the following are fully operational:

- **Monday automated pipeline** — Clockify + Jira + KPI snapshot + SPICE refresh runs every Monday at 9am and noon CT
- **COO Operational Dashboard** — all 8 sheets live, CE brand theme applied, IaC synced to `coo-dashboards.yaml`
- **KPI Tracking Dashboard v19** — all 3 sheets, correct headcount via DISTINCT_COUNT, period filters, RAG colors
- **Streamlit app** — all 17 tabs implemented, LoB mapping editor in Settings, practice area editor, profitability rates editor
- **LoB classification** — driven by `lob_practice_mapping` table (managed in Streamlit Settings → LoB Mapping Editor)
- **practice_area backfill** — all 69 active timekeeping users have a value (PS/MC/MIT/Internal/Exempt). Zero NULLs.
- **CloudWatch monitoring** — 6 alarms covering SPICE failures, Lambda errors, missed runs, concurrent executions
- **Productive utilization** — computed from `project_type` field, consistent with `kpi_snapshot.py` logic
- **On-time delivery** — aligned with Jira snapshot logic via `ps_project_status`
- **Runbooks** — `docs/runbooks/` covers Monday import failure, SPICE refresh failure, view deploy procedure

### Known gaps and open items

These are documented issues that a developer taking over this system should be aware of:

**1. PS-Jira ↔ Clockify mapping gaps**
`ps_project_mapping` has many entries at the client level only (not project level). Individual on-time delivery on KPI Dashboard Sheet 3 will show incomplete data for staff whose projects aren't mapped at the project level.
- Fix: Improve `ps_project_mapping` coverage — add project-level entries for all active PS projects.

**2. On-time delivery mismatch between Sheet 1 and Sheet 3**
Sheet 1 uses Jira-based `ps_on_time_pct` (from `kpi_weekly_snapshots`). Sheet 3 uses Clockify-based `ontime_pct_in_week` (from `kpi_staff`). These will not match until `ps_project_mapping` is fully populated. Sheet 1 is the more reliable source.

**3. `actual_completion` not populated by PMs**
Only ~26% of Done PS projects have `actual_completion` set in Jira. The `vw_project_closure_status` view works around this using deadline-based logic (matching `kpi_snapshot.py`), but confirmed close dates would improve accuracy.
- Fix: Enforce `actual_completion` on the Jira project close transition.

**4. `mc_on_time_pct` is 0% in snapshots**
The `_compute_project_metrics` function in `kpi_snapshot.py` runs for MC but may not be capturing the right project scope. Needs investigation before the MC On-Time Delivery tile can be added to the KPI dashboard.

**5. Budget delivery KPI not yet built**
`% of projects delivered on or under budget` was identified as a needed KPI. Data exists (`budget_percent_used` in `vw_ps_project_status`) but ~28% of projects have `budget_hours = 10` (placeholder, not real SOW hours).
- Fix: Enforce real `budget_hours` entry at project kickoff in Jira, then build the KPI tile and add `ps_on_budget_pct` to `kpi_weekly_snapshots`.

**6. 6 users with NULL `practice_area`**
Haider Ahmed, huzaifa.khalid, jeremy.ballard, Muhammad Burhan, umair.naeem, and Ateeq Ur Rehman Baig have `practice_area = NULL`. They default to `Internal` in views. Their `practice_alignment` field needs to be set in Clockify, then their `practice_area` updated via the Settings editor.

**7. Streamlit Tab 1 queries raw ORM**
The Dashboard tab (Tab 1) queries the `ClockifyTimeEntry` ORM directly instead of using the pre-built views. This can surface uncleaned data.
- Fix: Refactor to use `vw_project_hours_by_assignment` or equivalent views.

**8. COO dashboard sheets not fully in IaC**
Some COO dashboard sheets were patched via scripts and may not exactly match `coo-dashboards.yaml`. Use `scripts/sync_coo_dashboard_iac.py` to export the live analysis back to IaC before making changes.

**9. KPI Dashboard filter and tile defects (from redesign brief)**
The full list of known defects is in `docs/kpi-dashboard-redesign-brief.md` §1. Key items:
- Sheet 2 and 3 filter controls were non-functional in early versions (fixed in v19, but verify)
- "Projects in Red %" tile shows a raw count instead of a percentage on some versions
- On-time delivery trend shows only the Q4 final target (90%), not quarterly step milestones
- Default date may show the current in-progress week instead of last completed week

---

## 7. Developer Setup

### Prerequisites

- **AWS CLI** configured with SSO profile `AWSAdministratorAccess-961341524729`
- **Python 3.11+**
- **Docker** (for Streamlit deployment)
- **psql** (optional but useful for direct DB queries)

### AWS SSO login

```bash
aws sso login --profile AWSAdministratorAccess-961341524729
```

Your session lasts 8 hours. Re-run this if you get `ExpiredTokenException` errors.

### Local development (Streamlit app)

```bash
cd /Users/cdx/weekly-reporting/weekly-reporting

pip install -r requirements.txt

# Copy env template and fill in credentials from Secrets Manager
cp .env.example .env

# Get the DB password from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id production/weekly-reporting/secrets \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --query SecretString --output text

# Run the Streamlit app
streamlit run src/app.py
```

**Note:** Local development connects to the production RDS instance. There is no local database. Be careful with any data-modifying operations.

### Common operational commands

**Run incremental import manually:**
```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode": "incremental"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  /tmp/result.json && cat /tmp/result.json
```

**Apply DB views after `create_views.sql` changes:**
```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode": "apply_views"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  /tmp/result.json && cat /tmp/result.json
```

**Run a Jira import:**
```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode": "jira_import"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  /tmp/result.json
```

**Compute KPI snapshot for latest week:**
```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode": "snapshot_kpis"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  /tmp/result.json
```

**Run arbitrary SQL (diagnostic — uses master credentials):**
```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode": "run_query", "sql": "SELECT COUNT(*) FROM clockify_users WHERE is_active = true"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  /tmp/result.json && cat /tmp/result.json
```

**Check SPICE health:**
```bash
python scripts/check_spice_health.py
```

**Verify Monday readiness (pre-flight check):**
```bash
python scripts/verify_monday_readiness.py
```

**Deploy the Streamlit app:**
```bash
./scripts/deploy_dashboard.sh
```

**Rebuild the KPI Tracking Dashboard from scratch:**
```bash
python scripts/build_kpi_dashboard.py
```
> ⚠️ This deletes and recreates the entire analysis + dashboard. Takes several minutes. Use patch scripts for targeted changes.

**Check dashboard accuracy:**
```bash
python scripts/dashboard_accuracy_audit.py
```

---

## 8. Making Changes

### Changing a PostgreSQL view

1. Edit `src/database/create_views.sql` — all views live in this single file
2. Test your SQL locally (connect via psql or Secrets Manager credentials)
3. Apply via Lambda:
   ```bash
   aws lambda invoke --function-name production-clockify-import \
     --payload '{"mode": "apply_views"}' \
     --profile AWSAdministratorAccess-961341524729 \
     --region us-east-1 \
     --cli-binary-format raw-in-base64-out /tmp/result.json
   ```
4. Check SPICE datasets that depend on the changed view: `python scripts/check_spice_health.py`
5. Trigger SPICE refresh if needed (the Lambda `refresh_spice` mode, or via the QuickSight console)

**Watch out for:** Views that other views depend on. Drop order matters — the `apply_views` mode drops views in an order that handles most dependencies, but if you add a new view that others depend on, you may need to adjust the drop/create order in `create_views.sql`.

### Adding a DB migration

1. Create a new file: `src/database/migrations/{NNN}_{description}.sql`
   - Use the next sequential number (currently up to 102, so start at 103)
2. For DDL changes (ALTER TABLE, CREATE TABLE), run via Lambda `run_query` mode — it uses master credentials
3. For view changes, use `apply_views` mode (not `run_query`)
4. Update `create_views.sql` if the migration affects any views
5. Run `apply_views` to redeploy view changes

**DDL via run_query example:**
```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode": "run_query", "sql": "ALTER TABLE clockify_users ADD COLUMN new_field VARCHAR(50)"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  /tmp/result.json
```

### Changing the Lambda (import logic, KPI computation, etc.)

The Lambda package is large (~59MB) and must be deployed via S3. The standard workflow:

1. Make your changes to the source files in `src/`
2. Download the current Lambda package (pre-signed URL via Lambda console or AWS CLI)
3. Unzip, patch the changed files, re-zip
4. Upload to S3 and update the Lambda function code

The `scripts/deploy_dashboard.sh` script shows the S3 upload + Lambda update pattern. The same approach applies to `production-clockify-import`.

**Alternatively**, for small changes to files that the Lambda loads at runtime (like `create_views.sql`), you can deploy the file change directly without repackaging the Lambda — `create_views.sql` is read from disk by the Lambda at runtime via the `apply_views` mode.

### Changing the Streamlit app

1. Edit `src/app.py` (or files in `src/pages/`, `src/utils/`, etc.)
2. Test locally: `streamlit run src/app.py`
3. Deploy: `./scripts/deploy_dashboard.sh`
   - This builds a new Docker image, pushes to ECR, and updates the ECS service
   - ECS performs a rolling update — the old container stays up until the new one is healthy

### Changing a QuickSight dashboard

**For targeted changes** (fix a single visual, update a calculated field):
- Use the appropriate `scripts/patch_kpi_*.py` script or write a new patch script following the same pattern
- Patch scripts use the QuickSight boto3 API to update specific visuals or calculated fields

**For full rebuilds:**
- COO dashboard: `python scripts/sync_coo_dashboard_iac.py` to export live → edit `coo-dashboards.yaml` → `aws cloudformation deploy`
- KPI dashboard: `python scripts/build_kpi_dashboard.py` (deletes and recreates)

**Theme preservation rule:** Any script that calls `update_dashboard` or `update_analysis` must include `ThemeArn: arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme`. Without it, the theme is silently stripped to the AWS default on the next publish. This has happened before — see `docs/theme-issue-analysis-2026-06-29.md`.

### Infrastructure changes

The main CloudFormation stack is `weekly-reporting-production` (`cloudformation/template.yaml`). Deploy changes with:

```bash
aws cloudformation deploy \
  --template-file cloudformation/template.yaml \
  --stack-name weekly-reporting-production \
  --capabilities CAPABILITY_IAM \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1
```

The Streamlit ECS stack is separate: `production-weekly-reporting-dashboard` (`cloudformation/streamlit-ecs.yaml`).

---

## 9. Key Files Reference

### Source code

| File | Purpose |
|------|---------|
| `src/lambda_handler.py` | Lambda entry point — routes all `mode` values to the appropriate handler function |
| `src/app.py` | Streamlit app (~3,500 lines) — all 17 tabs plus Settings, Data Management, AI Analysis pages |
| `src/shared.py` | Shared auth and DB connection module for the Streamlit app |
| `src/integrations/import_clockify_data.py` | Clockify time entry import — incremental/weekly/full modes |
| `src/integrations/import_jira_data.py` | Jira PS/MC project status import — upserts `ps_project_status` |
| `src/integrations/kpi_snapshot.py` | Weekly KPI computation — populates `kpi_weekly_snapshots` |
| `src/integrations/forecast_resources.py` | Resource capacity forecast model (`ps_resource_forecast_v2`) |
| `src/integrations/mc_v2_audit.py` | MC V2 methodology compliance audit via Confluence API |
| `src/integrations/clockify_client.py` | Clockify API client wrapper |
| `src/integrations/jira_client.py` | Jira API client wrapper |
| `src/database/create_views.sql` | **All production PostgreSQL views** — single source of truth for all views |
| `src/database/migrations/` | Sequential SQL migration files (001–102) |

### Infrastructure as Code

| File | Purpose |
|------|---------|
| `cloudformation/template.yaml` | Main infrastructure stack (VPC, RDS, Lambda, EventBridge, SNS, CloudWatch alarms) |
| `cloudformation/coo-dashboards.yaml` | COO QuickSight dashboard IaC — synced from live analysis |
| `cloudformation/streamlit-ecs.yaml` | Streamlit ECS Fargate infrastructure (cluster, service, ALB, ECR) |
| `cloudformation/quicksight-dashboards.yaml` | Base reporting QuickSight dashboards |
| `cloudformation/cloudelligent-quicksight-theme.yaml` | CE brand theme for QuickSight |

### Scripts

| File | Purpose |
|------|---------|
| `scripts/build_kpi_dashboard.py` | KPI Tracking Dashboard full rebuild — idempotent, deletes and recreates |
| `scripts/patch_kpi_*.py` | Targeted KPI dashboard patches — use for individual visual/field fixes |
| `scripts/check_spice_health.py` | Check ingestion status of all 53 SPICE datasets |
| `scripts/check_all_spice.py` | Alternate SPICE status check |
| `scripts/deploy_dashboard.sh` | Deploy Streamlit app to ECS (build Docker image → push ECR → update service) |
| `scripts/apply_views_direct.py` | Apply `create_views.sql` directly (bypasses Lambda — useful if Lambda is broken) |
| `scripts/dashboard_accuracy_audit.py` | Full accuracy audit: import schedule, data freshness, SPICE status |
| `scripts/sync_coo_dashboard_iac.py` | Export live COO analysis → write to `coo-dashboards.yaml` |
| `scripts/export_live_analysis.py` | Export live analysis to `coo-analysis-live.json` |
| `scripts/publish_coo_dashboard.py` | Republish COO dashboard from current analysis definition |
| `scripts/verify_monday_readiness.py` | Pre-flight check: EventBridge rules, SPICE status, last import timestamps |
| `scripts/backfill_kpi_snapshots_2026.py` | Recompute KPI snapshots for all 2026 weeks (use after kpi_snapshot.py logic changes) |
| `scripts/seed_profitability_rates.py` | Seeds `ps_profitability_rates` table with initial rate values |

### Documentation

| File | Purpose |
|------|---------|
| `docs/developer-onboarding.md` | This document |
| `docs/project-context.md` | Authoritative context reference — data sources, tables, design standards |
| `docs/weekly-reporting-dashboard-spec.md` | Full SRS for all 17 Streamlit tabs (v1.1) |
| `docs/kpi-dashboard-proposal.md` | KPI Tracking Dashboard solution proposal |
| `docs/kpi-dashboard-redesign-brief.md` | KPI dashboard strategic redesign spec — known defects + fix roadmap |
| `docs/AWS_DEPLOYMENT.md` | AWS infrastructure deployment guide |
| `docs/2026-coo-okrs.md` | Full OKR definitions with quarterly targets |
| `docs/COO_DASHBOARD_VIEWS.md` | View derivation reference for COO dashboard |
| `docs/implementation-plan.md` | 6-sprint plan for 17-tab Streamlit dashboard redesign |
| `docs/master-plan.md` | Master implementation plan |
| `docs/project-progress.md` | Sprint and task progress tracker |
| `docs/theme-issue-analysis-2026-06-29.md` | Root cause analysis for CE theme being stripped on dashboard updates |
| `docs/runbooks/monday-import-failure.md` | Runbook: what to do when the Monday import fails |
| `docs/runbooks/spice-refresh-failure.md` | Runbook: what to do when SPICE datasets fail |
| `docs/runbooks/view-deploy-procedure.md` | Runbook: how to safely deploy view changes |

---

## 10. Monitoring & Alerts

All alerts route to the SNS topic `production-weekly-reporting-notifications` → email.

### CloudWatch alarms

| Alarm Name | Trigger Condition | What it means |
|-----------|------------------|---------------|
| `weekly-reporting-spice-failure` | Error pattern `"SPICE"` or `"ingestion"` in Lambda logs | A SPICE dataset failed to refresh. Usually caused by a missing view, dropped column, or schema mismatch. |
| `production-import-lambda-errors` | Lambda function throws an exception | Import failed. Could be DB connection issue, Clockify/Jira API error, or timeout. |
| `weekly-reporting-lambda-duration-warning` | Lambda duration > 800 seconds | Usually the Bedrock AI analysis step timing out — non-fatal, AI narratives just won't update that run. |
| `weekly-reporting-lambda-not-invoked` | Zero Lambda invocations in 7 days | EventBridge rule was disabled or deleted. |
| `weekly-reporting-lambda-concurrent-executions` | 2+ concurrent Lambda executions | Duplicate EventBridge target — two triggers fired for the same event. |
| `weekly-reporting-import-errors` | 3+ error log patterns in Lambda logs | General import errors — check CloudWatch logs for details. |

### Diagnosing a Monday failure

1. **Check CloudWatch logs** for `production-clockify-import` — filter to the Monday morning window
2. **Check SPICE status**: `python scripts/check_spice_health.py`
3. **Check the import log table**: `{"mode": "run_query", "sql": "SELECT * FROM import_logs ORDER BY created_at DESC LIMIT 10"}`
4. **Follow the runbook** in `docs/runbooks/monday-import-failure.md`

### Common failure modes and fixes

**SPICE dataset fails after view change:**
```bash
# Re-apply views
aws lambda invoke --function-name production-clockify-import \
  --payload '{"mode": "apply_views"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 --cli-binary-format raw-in-base64-out /tmp/r.json

# Then trigger SPICE refresh via QuickSight console or:
aws lambda invoke --function-name production-clockify-import \
  --payload '{"mode": "refresh_spice"}' \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 --cli-binary-format raw-in-base64-out /tmp/r.json
```

**Lambda timeout (900s exceeded):**
- Most likely the Bedrock AI analysis step. This is non-fatal — the import data is already committed.
- Re-run without AI analysis: `{"mode": "incremental", "skip_ai": true}` (check `lambda_handler.py` for exact parameter)

**DB connection error:**
- Check that the Lambda's VPC security group allows outbound to the RDS security group on port 5432
- Verify Secrets Manager secret is not expired: check `production/weekly-reporting/secrets` in the console

**EventBridge rule not firing:**
```bash
python scripts/check_eventbridge_targets.py
```

**CE theme stripped from COO dashboard:**
```bash
python scripts/restore_dashboard_theme.py
```
Then patch `scripts/sync_coo_dashboard_iac.py` and any scripts that update the COO dashboard to include `ThemeArn`. See `docs/theme-issue-analysis-2026-06-29.md`.

---

*Questions or corrections? Update this document and commit — it's the onboarding source of truth.*
