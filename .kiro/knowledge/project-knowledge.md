# Weekly Reporting — Project Knowledge Document

> **Single source of truth** for anyone (human or AI agent) working on this project.
> Last updated: 2026-04-30

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Sources & Integrations](#3-data-sources--integrations)
4. [Database Schema](#4-database-schema)
5. [Lambda Handler Modes](#5-lambda-handler-modes)
6. [QuickSight Datasets](#6-quicksight-datasets)
7. [CloudFormation Stacks](#7-cloudformation-stacks)
8. [Streamlit Application](#8-streamlit-application)
9. [Key Environment Variables & Secrets](#9-key-environment-variables--secrets)
10. [Deployment Notes](#10-deployment-notes)
11. [Known Resource IDs](#11-known-resource-ids)

---

## 1. Project Overview

### What the system does

A **weekly operations reporting platform** for Cloudelligent. It:

- Imports time-tracking data from **Clockify** (users, projects, time entries)
- Imports project status from **Jira** (PS and MC boards, escalations ES board)
- Imports resource forecasts from **Excel templates** uploaded via the Streamlit UI
- Runs **AI analysis** (Amazon Bedrock) comparing Jira estimates vs Clockify actuals
- Writes weekly **KPI snapshots** to a persistent table
- Exposes all data to **Amazon QuickSight** via PostgreSQL views and SPICE datasets
- Provides a **Streamlit web app** for operations staff to view dashboards, manage forecasts, configure project mappings, and update Clockify custom fields

### Business purpose

Gives the Cloudelligent COO and operations team visibility into:
- Billable/productive utilisation by practice (PS, MC), POD, and individual
- Time submission compliance
- PS and MC project delivery health (Green/Amber/Red)
- Resource forecasting vs actuals
- Escalation tracking
- MC V2 methodology progress (A2Z framework)

### Key stakeholders

- **COO** — primary consumer of QuickSight dashboards
- **Operations team** — uses Streamlit app for data management
- **Project Managers** — upload forecast Excel templates

### AWS Account & Region

| Item | Value |
|------|-------|
| AWS Account ID | `961341524729` |
| Primary region | `us-east-1` |

---

## 2. Architecture Overview

### AWS Services Used

| Service | Role |
|---------|------|
| **AWS Lambda** | Scheduled data import orchestrator (`production-clockify-import`) |
| **Amazon RDS PostgreSQL** | Primary data store (all tables and views) |
| **Amazon QuickSight** | BI dashboards (SPICE datasets, analyses, dashboards) |
| **AWS Secrets Manager** | Stores DB password, Clockify API key, Jira credentials |
| **AWS SSM Parameter Store** | Stores RDS endpoint |
| **Amazon SNS** | Import success/failure notifications |
| **Amazon Bedrock** | AI project health analysis (Claude 3.5 Sonnet) |
| **Amazon ECS** (implied) | Streamlit app hosting (env vars set in task definition) |
| **Amazon EventBridge** | Scheduled Lambda triggers (weekly import, KPI snapshot) |

### Data Flow

```
Clockify API ──────────────────────────────────────────────────────────┐
Jira REST API ─────────────────────────────────────────────────────────┤
Excel Upload (Streamlit) ──────────────────────────────────────────────┤
                                                                        ▼
                                                          Lambda / Streamlit
                                                                        │
                                                                        ▼
                                                          RDS PostgreSQL (pg8000)
                                                          ┌─────────────────────┐
                                                          │  Tables             │
                                                          │  SQL Views          │
                                                          └─────────────────────┘
                                                                        │
                                                                        ▼
                                                          QuickSight SPICE datasets
                                                                        │
                                                                        ▼
                                                          COO Dashboards / Analyses
```

### Lambda Deployment

- **Function name:** `production-clockify-import`
- **Package:** `lambda-deployment-package.zip`
- **Runtime:** Python 3.x
- **Handler:** `src/lambda_handler.lambda_handler`
- **Key dependencies:** `pg8000`, `SQLAlchemy`, `boto3`, `requests`, `openpyxl`
- The Lambda uses `pg8000` (pure-Python PostgreSQL driver) because `psycopg2` requires native libs not available in the standard Lambda environment.

### Streamlit App Deployment

- Runs as a container (ECS Fargate implied by env var pattern)
- Entry point: `src/app.py`
- Applies all pending SQL migrations on startup (`apply_pending_migrations()`)
- Invokes Lambda directly via `boto3` for data refresh operations

---

## 3. Data Sources & Integrations

### 3.1 Clockify (Time Tracking)

**File:** `src/integrations/import_clockify_data.py`  
**Client:** `src/integrations/clockify_client.py`

**What is imported:**
- **Users** — all workspace members (ACTIVE + INACTIVE), including all custom fields via the member-profile endpoint
- **Projects** — all projects with client names and custom fields (Project Type, Pod Assignment, Overtime, Presales toggles)
- **Time entries** — per-user, per-date range; denormalised with user custom fields at import time

**Custom fields on users (Clockify):**

| Field Name | DB Column | Purpose |
|-----------|-----------|---------|
| Practice Alignment | `practice_alignment` | PS / Managed Cloud / etc. |
| Skill Area | `skill_area` | Technical expertise |
| POD Assignment | `pod_assignment` | Alpha / Bravo / A2Z / SurePoint / Free Agent / Exempt |
| Cloudelligent Title | `cloudelligent_title` | Job title |
| Location | `location` | Onshore / Offshore |
| Employment Designation | `employment_designation` | FTE / Contractor |
| Time Submission | `time_submission` | Set to "No" to exclude from compliance reports |

**Custom fields on projects (Clockify):**

| Field Name | DB Column | Purpose |
|-----------|-----------|---------|
| Project Type | `project_type` | Professional Services / Managed Cloud / Non Bill Productive / Non Bill Non Productive / FinOps / Overhead / Training and Certs / etc. |
| Pod Assignment | `pod_assignment` | MC pod for the project |
| Overtime | `is_overtime` | Boolean toggle |
| Presales | `is_presales` | Boolean toggle |

**Import modes:**
- **Incremental** — fetches since last successful import date (from `import_logs`)
- **Full** — fetches last 52 weeks
- **Weekly** — fetches last 1 week

**API base URL:** `https://api.clockify.me/api/v1/workspaces/{workspace_id}/`

**Important note on pod_assignment formatting:** Clockify returns custom field values with JSON array notation (e.g. `{Bravo}` or `{"Free Agent"}`). All views strip these with `REPLACE(REPLACE(REPLACE(REPLACE(value, '{', ''), '}', ''), '"', ''), '\', '')`.

---

### 3.2 Jira (Project Status & Escalations)

**Files:**
- `src/integrations/import_jira_data.py` — PS/MC project status import
- `src/integrations/import_escalations.py` — ES board escalation import
- `src/integrations/jira_client.py` — REST API client

**What is imported:**

**PS/MC Project Status (`ps_project_status` table):**
- All issues from configured Jira project keys
- Parsed fields: client name + project name (from issue summary), status, health (Red/Yellow/Green), team members (PM, SA, Engineer, AE, CSM), budget hours, all phase completion dates, narrative fields, SOW link, Jira board link
- **Category classification:** `MC` if `issue_type` is in `settings.mc_issue_types`; otherwise `PS`
- Client name and project name are parsed from the Jira issue summary field and are **never overwritten on re-import** (to preserve manual normalisation via migrations)

**Escalations (`escalations` table):**
- From the ES Jira board
- Fields: customer name (from epic), summary, status, priority, assignee, dates, days open/to resolve, description, status change history

**Project mapping auto-population:**
- After each Jira import, `auto_populate_mappings()` attempts to match Jira client names to Clockify client names using exact match, then substring matching
- Manual mappings can be created/edited in the Streamlit "Project Mapping" page

**Stage snapshot:**
- After each full Jira sync, `_capture_stage_snapshot()` upserts the current PS/MC stage distribution into `ps_stage_weekly_snapshot` for week-over-week trend tracking

---

### 3.3 Amazon Bedrock (AI Analysis)

**Files:**
- `src/integrations/analyze_project_health.py` — PS/MC Jira vs Clockify analysis
- `src/integrations/mc_v2_audit.py` — MC V2 methodology audit
- `src/integrations/analyze_forecast.py` — Forecast vs actuals analysis

**Model:** `us.anthropic.claude-3-5-sonnet-20241022-v2:0` (configurable via `BEDROCK_MODEL_ID` env var)

**What each analysis does:**

| Analysis | Lambda mode | Output tables | Description |
|----------|-------------|---------------|-------------|
| Project Health | `analyze_project_health` | `ai_analysis_by_user`, `ai_analysis_by_project` | Compares Jira issue estimates vs Clockify actuals per user and project for PS and MC |
| MC V2 Audit | `mc_v2_audit` | `mc_v2_audit_by_customer`, `mc_v2_audit_by_phase` | Assesses MC customer progress through the A2Z 4-phase methodology |
| Forecast Analysis | `analyze_forecast` | `ai_forecast_analysis`, `ai_forecast_summary`, `ai_pm_forecast_accuracy` | Analyses forecast vs actual hours per resource and PM |

**Prompts:** Stored in `ai_analysis_prompts` table, editable via the Streamlit "Data Management" page. Categories: `PS`, `MC`, `MC_V2`, `FORECAST`.

**Bedrock API:** Uses the Converse API (`bedrock.converse()`), not the older `invoke_model`.

---

### 3.4 PS Resource Forecasts (Excel Import)

**Files:**
- `src/integrations/forecast_import.py` — DB import logic
- `src/integrations/forecast_parser.py` — Excel template parser

**Template format:**
- Row 1: Week date ranges (e.g. "16th-20th Dec")
- Row 2: Week labels (Week1, Week2, …)
- Row 4: Headers — Client, Comments, Type, PM, Stage, User, Plan columns
- Data rows: one row per user per project with Plan hours per week

**Import behaviour:**
- Archives the current forecast to `ps_resource_forecast_history` before replacing
- Rejects rows where the user name doesn't match any active Clockify user (logged to `forecast_dropped_users`)
- Unique constraint: `(user_name, week_start_date, client_name, project_name)`

---

### 3.5 Clockify Bulk Update

**File:** `src/integrations/update_clockify.py`

Allows bulk-updating Clockify custom fields on users and projects by uploading a CSV/Excel export. Supports dry-run preview. Logs all uploads to `clockify_upload_logs`.

---

## 4. Database Schema

### 4.1 Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `clockify_users` | Clockify team members | `clockify_user_id`, `name`, `email`, `daily_capacity`, `practice_alignment`, `skill_area`, `pod_assignment`, `cloudelligent_title`, `location`, `employment_designation`, `time_submission`, `status` |
| `clockify_projects` | Clockify project definitions | `clockify_project_id`, `name`, `client_id`, `client_name`, `billable`, `archived`, `project_type`, `pod_assignment`, `is_overtime`, `is_presales` |
| `clockify_detailed_time_entries` | Individual time entries | `clockify_entry_id`, `clockify_user_id`, `user_name`, `clockify_project_id`, `project_name`, `client_name`, `entry_date`, `week_start`, `duration_hours`, `billable`, `start_time`, `end_time` + all user custom fields denormalised |
| `ps_resource_forecasts` | Weekly resource forecast allocations | `forecast_id`, `week_start_date`, `week_end_date`, `user_name`, `client_name`, `project_name`, `pm_name`, `project_type`, `stage`, `forecasted_hours`, `actual_hours` |
| `ps_resource_forecast_history` | Archived forecast snapshots | Same columns as `ps_resource_forecasts` + `snapshot_id`, `archived_at` |
| `ps_project_status` | Jira project health records | `jira_issue_id`, `issue_key`, `client_name`, `project_name`, `category` (PS/MC), `status`, `health_overall`, `health_budget`, `health_scope`, `health_schedule`, `budget_hours`, all phase dates, team members, narrative fields, `is_excluded` |
| `ps_project_mapping` | Jira→Clockify client/project mapping | `ps_client_name`, `ps_project_name`, `clockify_client_name`, `clockify_project_name`, `category`, `pod_assignment`, `is_active` |
| `jira_projects` | Jira project metadata | `jira_project_id`, `project_key`, `project_name`, `lead_name` |
| `escalations` | Jira ES board escalation issues | `jira_issue_id`, `issue_key`, `customer_name`, `epic_key`, `summary`, `status`, `status_category`, `priority`, `assignee_name`, `created_date`, `days_open`, `days_to_resolve`, `description`, `previous_status`, `status_changed_at` |
| `import_logs` | Data import audit trail | `log_id`, `import_type`, `import_category`, `records_imported`, `records_updated`, `status`, `started_at`, `completed_at`, `error_message` |
| `app_users` | Streamlit login accounts | `username`, `display_name`, `password_hash` (bcrypt), `is_active` |
| `ai_analysis_prompts` | Configurable Bedrock prompts | `category` (PS/MC/MC_V2/FORECAST), `sequence_order`, `prompt_text`, `is_active` |
| `ai_analysis_by_user` | AI project health results per user | `week_start`, `category`, `user_name`, `role`, `project_name`, `jira_estimate_hours`, `clockify_actual_hours`, `delta`, `verdict`, `notes` |
| `ai_analysis_by_project` | AI project health results per project | `week_start`, `category`, `project_name`, `team_size`, `total_jira_estimate_hours`, `total_clockify_hours`, `verdict`, `notes` |
| `mc_v2_audit_by_customer` | MC V2 audit per customer | `week_start`, `customer_name`, `jira_project_key`, `pod`, `overall_completion_pct`, `executive_summary` |
| `mc_v2_audit_by_phase` | MC V2 audit per phase | `week_start`, `customer_name`, `phase_name`, `phase_order`, `completion_pct`, `narrative` |
| `ai_forecast_analysis` | Per-user forecast vs actual AI analysis | `week_start`, `user_name`, `total_forecasted_hours`, `total_actual_hours`, `pct_achieved`, `status`, `notes` |
| `ai_forecast_summary` | Week-level forecast analysis summary | `week_start`, `total_resources`, `on_track_count`, `over_count`, `under_count`, `key_observations`, `recommendations` |
| `ai_pm_forecast_accuracy` | PM-level forecast accuracy | `week_start`, `pm_name`, `accuracy_score`, `narrative` |
| `kpi_weekly_snapshots` | Weekly KPI values (one row per Monday) | `week_start_date` (PK), `billable_util_pct`, `productive_util_pct`, `time_compliance_pct`, `ps_active_projects`, `ps_projects_green/amber/red`, `mc_*`, `open_escalations`, `active_resource_count` |
| `ps_stage_weekly_snapshot` | PS/MC stage count per week | `week_start`, `stage`, `category`, `project_count` |
| `user_skills` | User skill and certification records | `clockify_user_id`, `skill_category`, `skill_name`, `proficiency_level`, `certification_name` |
| `mc_pods` | User-managed MC pod name list | `pod_name`, `is_active` |
| `clockify_upload_logs` | Audit log for Clockify bulk updates | `uploaded_by`, `file_name`, `file_type`, `records_updated`, `detail` (JSON) |
| `forecast_dropped_users` | Users rejected during forecast import | `user_name`, `import_log_id`, `dropped_at` |
| `missing_time_reasons` | Optional reasons for missing time | (week, user, reason) |

### 4.2 Migration Numbering

Current highest migration: **052**

Notable migrations:
- `001` — Remove service_line column
- `002` — Add week_start to time entries
- `006/008` — Add Jira tables
- `014` — PS/Clockify mapping table
- `017` — Forecast history table
- `019` — App users table
- `020` — AI analysis tables
- `027/028/029` — Category column on mapping and ps_project_status
- `034` — `is_excluded` flag on ps_project_status
- `037` — AI forecast analysis tables
- `038` — Escalations table
- `040` — PS stage weekly snapshot
- `044` — Forecast dropped users
- `045` — Time submission field on users
- `046` — Pod assignment on mapping + mc_pods table
- `047` — Escalation enhancements (description, previous_status, status_changed_at)
- `048` — Overtime/presales boolean columns on clockify_projects
- `049` — Clockify upload logs
- `050` — Project hours views (vw_project_hours_summary, vw_category_hours_summary, etc.)
- `051` — KPI weekly snapshots table + vw_kpi_ytd
- `052` — Add clockify_project_type column to project hours view


### 4.3 PostgreSQL Views

All views are defined in `src/database/create_views.sql` and applied via Lambda `mode=apply_views` or on Streamlit startup.

| View | Source Tables | Purpose |
|------|--------------|---------|
| `vw_weekly_time_summary` | `clockify_detailed_time_entries` | Weekly hours by practice alignment + location |
| `vw_resource_utilization` | `clockify_detailed_time_entries`, `clockify_users` | Per-user weekly utilisation % and billable % |
| `vw_project_time_tracking` | `clockify_detailed_time_entries` | Weekly hours by project/client |
| `vw_client_time_summary` | `clockify_detailed_time_entries` | Weekly hours by client |
| `vw_skill_area_summary` | `clockify_detailed_time_entries` | Weekly hours by skill area |
| `vw_daily_activity_trend` | `clockify_detailed_time_entries` | Daily hours by practice + location |
| `vw_active_resources` | `clockify_users`, `clockify_detailed_time_entries` | Active user directory with last entry date and 30-day hours |
| `vw_import_activity` | `import_logs` | Import log with duration in seconds |
| `vw_practice_alignment_performance_12w` | `clockify_detailed_time_entries` | 12-week practice performance |
| `vw_monthly_summary` | `clockify_detailed_time_entries` | Monthly hours by practice/pod/location |
| `vw_missing_time_submissions` | `clockify_users`, `clockify_detailed_time_entries`, `import_logs` | Active users who haven't submitted ≥90% of expected hours for the prior week. Excludes Exempt pod and `time_submission='No'` users. Statuses: No Time Submitted / Less Than 50% / Less Than 90% / Complete |
| `vw_pod_performance_analysis` | `clockify_detailed_time_entries` | POD-level hours with 4-week and 12-week averages, trend, variance. PODs: Free Agent, Alpha, Bravo, SurePoint, A2Z, Unassigned |
| `vw_practice_group_performance` | `clockify_detailed_time_entries`, `clockify_projects` | Practice group hours using Clockify project_type field (no ps_project_mapping dependency) |
| `vw_contractor_weekly_trend` | `clockify_detailed_time_entries`, `clockify_users` | Contractor hours for last 5 weeks |
| `vw_contractor_time_summary` | `clockify_detailed_time_entries`, `clockify_users` | Per-contractor last week vs 4-week average |
| `vw_forecast_vs_actual` | `ps_resource_forecasts`, `clockify_detailed_time_entries` | Forecast vs actual comparison with status (On Track/Over/Under/No Actuals/Unforecasted) |
| `vw_forecast_pivot` | `ps_resource_forecasts`, `clockify_users` | Forecast data in pivot format (4 weeks back to 16 weeks forward) |
| `vw_forecast_summary_by_client` | `ps_resource_forecasts` | Aggregated forecast by client/week |
| `vw_forecast_summary` | `ps_resource_forecasts` | Weekly forecast totals |
| `vw_forecast_over_40_hours` | `ps_resource_forecasts`, `clockify_users` | Users with >40 forecasted hours in any week |
| `vw_forecast_version_comparison` | `ps_resource_forecasts`, `ps_resource_forecast_history` | Current vs previous forecast snapshot diff |
| `vw_ps_project_status` | `ps_project_status`, `ps_project_mapping`, `ps_resource_forecasts`, `clockify_detailed_time_entries` | Full PS/MC project tracker with actual hours (YTD), last week hours, remaining forecast, budget %, projected ending. Excludes Done projects completed before current year and `is_excluded=true` rows |
| `vw_free_agent_availability` | `clockify_users`, `ps_resource_forecasts` | Free Agent weekly capacity minus forecasted hours for next 12 weeks |
| `vw_non_billable_project_analysis` | `clockify_detailed_time_entries`, `import_logs` | Non-billable time by resource/project/week |
| `vw_ps_profitability_2026` | `ps_project_status`, `ps_project_mapping`, `clockify_detailed_time_entries`, `ps_resource_forecasts` | Project-level profitability: actual hours + forecast hours by location and worker_type (FTE/Contractor) |
| `vw_ps_profitability_weekly_2026` | `ps_project_status`, `ps_project_mapping`, `clockify_detailed_time_entries` | Weekly actual hours for PS projects by location/worker_type |
| `vw_ps_profitability_chart` | `vw_ps_profitability_2026` | Unpivoted for QuickSight stacked bar charts (bar_type: Actual/Forecast/No Data) |
| `vw_data_freshness` | `import_logs` | Last successful import timestamp per category |
| `vw_mc_v2_audit_grid` | `mc_v2_audit_by_customer`, `mc_v2_audit_by_phase` | MC V2 audit pivoted — one row per customer, phase completion % as columns |
| `vw_project_hours_by_assignment` | `clockify_detailed_time_entries`, `clockify_projects`, `ps_project_mapping`, `ps_project_status` | Weekly hours by project/client with category (PS/MC/Other), pod, billable/non-billable breakdown |
| `vw_productive_utilization` | `clockify_users`, `clockify_detailed_time_entries`, `clockify_projects`, `ps_project_mapping` | Per-employee weekly billable/non-bill-productive/non-bill-non-productive/non-logged hours |
| `vw_time_submission_weekly` | `clockify_users`, `clockify_detailed_time_entries` | Historical time submission compliance per user per week |
| `vw_weekly_compliance_report` | `clockify_users`, `clockify_detailed_time_entries`, `import_logs` | Current reporting week compliance — all active non-exempt users (compliant + non-compliant) |
| `vw_project_time_detail` | `clockify_detailed_time_entries`, `clockify_projects` | Detailed time entries for last 4 complete weeks |
| `vw_project_directory` | `ps_project_status` | One row per (project, role, resource) — unpivots PM/SA/Engineer/AE/CSM |
| `vw_customer_status_assignments` | `ps_project_status` | Active Jira project queue with one row per (project, role, resource) |
| `vw_project_detail` | `vw_ps_project_status` | Thin alias view for COO Sheet 5 — renames budget_hours→sow_hours, actual_hours→actual_hours_ytd, etc. |
| `vw_escalations` | `escalations` | Flat escalation detail with priority sort order, escalation_state, is_new, changed_last_week flags |
| `vw_escalations_by_customer` | `escalations` | Per-customer escalation summary (totals, open, resolved, avg days) |
| `vw_ps_stage_trend` | `ps_stage_weekly_snapshot` | Week-over-week PS stage count comparison |
| `vw_project_hours_summary` | `clockify_detailed_time_entries`, `ps_project_mapping`, `ps_project_status`, `escalations` | 30-week project hours with rolling averages, trend, health, escalation flag (migration 050) |
| `vw_project_hours_current_week` | `vw_project_hours_summary` | Filter of above for the most recent complete week only |
| `vw_category_hours_summary` | `vw_project_hours_summary` | Practice-level rollup (PS/MC/FinOps/Other) per week with 4w/12w averages |
| `vw_kpi_ytd` | `kpi_weekly_snapshots` | KPI snapshots from 2026-01-01 with vs-target gaps and week-over-week deltas (migration 051) |

**Two-tier mapping hierarchy** (used by many views):
- **Tier 1:** Explicit `ps_project_mapping` entry — matches Clockify client/project to PS client/project
- **Tier 2:** Direct client name match from `ps_project_status` where no explicit mapping exists

---

## 5. Lambda Handler Modes

The Lambda (`src/lambda_handler.py`) is invoked with an event containing a `mode` key.

### Standard Import Modes

| Mode | What it does |
|------|-------------|
| `incremental` | Imports Clockify data since last successful import, then runs Jira import, KPI snapshot, AI project health analysis, MC V2 audit, escalations import, and refreshes all QuickSight SPICE datasets |
| `weekly` | Same as incremental but forces `weeks_back=1` |
| `full` | Same pipeline but forces `weeks_back=52` (full year) |

### Targeted Operation Modes

| Mode | What it does |
|------|-------------|
| `apply_views` | Recreates all PostgreSQL views from `create_views.sql` and grants SELECT to PUBLIC |
| `snapshot_kpis` | Computes and upserts weekly KPI snapshot. Optional param: `week_start` (ISO date string) |
| `run_escalations_import` | Creates escalations table/views if needed, imports from ES Jira board, refreshes `escalations-detail` and `escalations-by-customer` datasets |
| `refresh_quicksight_only` | Triggers SPICE refresh for specified dataset IDs. Param: `quicksight_dataset_ids` (list) |
| `run_migration` | Executes a named SQL migration file. Param: `migration_file` (filename only, e.g. `052_add_clockify_project_type_to_hours_view.sql`) |
| `run_query` | Executes a read-only SELECT and returns rows. Param: `sql` |
| `create_quicksight_datasets` | Creates the four manually-managed QuickSight datasets (project-hours-by-assignment, project-time-detail, project-directory, customer-status-assignments) |
| `jira_import` | Runs Jira PS/MC project status import. Params: `project_keys` (list, optional), `full_sync` (bool) |
| `analyze_project_health` | Runs Bedrock AI analysis for PS and MC. Params: `week_start` (ISO date) or `weeks_back` (int) |
| `mc_v2_audit` | Runs MC V2 methodology audit. Param: `week_start` (ISO date) |
| `analyze_forecast` | Runs Bedrock forecast vs actuals analysis. Params: `week_start`, `weeks_back` (int, default 4) |
| `mc_v2_customers` | Returns list of MC customers without running full audit |

### Diagnostic Modes

| Mode | What it does |
|------|-------------|
| `diagnose` | Checks `import_logs` table — statuses, categories, recent time_entries imports |
| `diagnose_users` | Checks user statuses, pod assignments, practice alignments, skill areas, view output |
| `diagnose_contractors` | Checks employment_designation values, contractor trend/summary views |
| `diagnose_dates` | Checks latest entry dates, entries by week, POD data for last 2 weeks |
| `diagnose_ps` | Checks ps_project_status count, view count, issue types, forecast info, mapping data |
| `diagnose_forecasts` | Checks forecast date range, duplicates, over-40-hours view, history snapshots |
| `diagnose_free_agents` | Checks Free Agent Clockify users vs forecast matches |
| `diagnose_pod` | Checks POD performance view data |
| `diagnose_report_mapping` | Shows which Clockify projects are included in PS/MC reports and via which tier |
| `debug_secrets` | Shows which env vars are set (masks sensitive values) |
| `debug_clockify` | Queries Clockify API with different status filters to count users |
| `jira_fields` | Discovers available Jira custom fields and surveys sample issues for board link fields |
| `restore_forecasts` | Restores forecast data from a history snapshot. Param: `snapshot_id` (optional, defaults to most recent) |

### Event Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `incremental` | Operation mode (see above) |
| `weeks_back` | int | null | Override weeks to import |
| `notify` | bool | false | Send SNS notification on completion/failure |
| `quicksight_dataset_ids` | list | [] | Override dataset IDs to refresh (empty = all) |
| `week_start` | string | null | ISO date for targeted week operations |
| `full_sync` | bool | false | Force full Jira sync |
| `project_keys` | list | null | Jira project keys to sync |
| `migration_file` | string | — | Migration filename for `run_migration` mode |
| `sql` | string | — | SQL query for `run_query` mode |

---

## 6. QuickSight Datasets

### CloudFormation-Managed Datasets (suffix `-prod`)

| Dataset ID | Source View | Description |
|-----------|-------------|-------------|
| `clockify-pod-performance-prod` | `vw_pod_performance_analysis` | POD performance with trends |
| `clockify-skill-area-summary-prod` | `vw_skill_area_summary` | Hours by skill area |
| `clockify-daily-activity-trend-prod` | `vw_daily_activity_trend` | Daily activity trend |
| `clockify-import-activity-prod` | `vw_import_activity` | Import log |
| `clockify-missing-time-submissions-prod` | `vw_missing_time_submissions` | Missing time submissions |
| `kpi-weekly-snapshots-prod` | `vw_kpi_ytd` | Weekly KPI snapshots with targets and deltas |
| `project-hours-summary-prod` | `vw_project_hours_summary` | 30-week project hours with health |
| `project-hours-current-week-prod` | `vw_project_hours_current_week` | Current week project hours |
| `category-hours-summary-prod` | `vw_category_hours_summary` | Practice-level weekly hours |
| `project-delivery-health-prod` | `ps_project_status` (direct) | Project health distribution |
| `escalations-detail-prod` | `escalations` (direct) | Escalation detail |

### Manually-Created Datasets (fixed UUIDs or custom IDs)

| Dataset ID | Source View | Description |
|-----------|-------------|-------------|
| `clockify-missing-time-submissions` | `vw_missing_time_submissions` | Legacy missing time dataset |
| `7833b3c6-cec4-4956-b02a-2316198187cb` | `vw_contractor_weekly_trend` | Contractor weekly trend |
| `c84d2b1f-de9d-42cd-a389-e425a100c4d4` | `vw_contractor_time_summary` | Contractor time summary |
| `3bdc816d-4df6-4db7-b3e6-64e230f28f14` | `vw_forecast_over_40_hours` | Users forecasted >40 hrs/week |
| `42098a5b-a94f-41d5-8300-396f1fec66bf` | `vw_forecast_summary` | Forecast summary by week |
| `fc56c886-f0d2-4935-8b32-f0862325d3f0` | `vw_forecast_vs_actual` | Forecast vs actual comparison |
| `8900f5dc-687e-4d5b-9f91-5efd0cd1daed` | `ps_resource_forecasts` | Raw forecast table |
| `ps-project-status-view` | `vw_ps_project_status` | Full PS/MC project tracker |
| `data-freshness` | `vw_data_freshness` | Last import timestamps |
| `non-billable-analysis` | `vw_non_billable_project_analysis` | Non-billable time analysis |
| `free-agent-availability` | `vw_free_agent_availability` | Free Agent capacity |
| `ai-ps-analysis-by-user` | `ai_analysis_by_user` (PS) | AI PS analysis per user |
| `ai-ps-analysis-by-project` | `ai_analysis_by_project` (PS) | AI PS analysis per project |
| `ai-mc-analysis-by-user` | `ai_analysis_by_user` (MC) | AI MC analysis per user |
| `ai-mc-analysis-by-project` | `ai_analysis_by_project` (MC) | AI MC analysis per project |
| `ps-profitability-2026` | `vw_ps_profitability_2026` | PS project profitability |
| `ps-profitability-weekly-2026` | `vw_ps_profitability_weekly_2026` | PS weekly profitability trend |
| `ps-profitability-chart` | `vw_ps_profitability_chart` | PS profitability stacked bar chart |
| `mc-v2-audit-by-customer` | `mc_v2_audit_by_customer` | MC V2 audit per customer |
| `mc-v2-audit-by-phase` | `mc_v2_audit_by_phase` | MC V2 audit per phase |
| `mc-v2-audit-grid` | `vw_mc_v2_audit_grid` | MC V2 audit pivoted grid |
| `project-hours-by-assignment` | `vw_project_hours_by_assignment` | Hours by project/client/category |
| `practice-group-performance` | `vw_practice_group_performance` | Practice group performance |
| `ai-forecast-analysis` | `ai_forecast_analysis` | AI forecast analysis per user |
| `ai-forecast-summary` | `ai_forecast_summary` | AI forecast summary |
| `pm-forecast-accuracy` | `ai_pm_forecast_accuracy` | PM forecast accuracy |
| `escalations-detail` | `vw_escalations` | Escalation detail (legacy) |
| `escalations-by-customer` | `vw_escalations_by_customer` | Escalations per customer |
| `ps-stage-trend` | `vw_ps_stage_trend` | PS stage week-over-week trend |
| `productive-utilization` | `vw_productive_utilization` | Per-employee productive utilisation |
| `missing-time-history` | `vw_time_submission_weekly` | Historical time submission compliance |
| `time-compliance-current-week` | `vw_weekly_compliance_report` | Current week compliance (all users) |
| `project-time-detail` | `vw_project_time_detail` | Detailed time entries last 4 weeks |
| `customer-status-assignments` | `vw_customer_status_assignments` | Active Jira queue with resource assignments |
| `project-directory` | `vw_project_directory` | Project directory with team members |
| `project-detail-view` | `vw_project_detail` | COO Sheet 5 — project detail with aliased columns (sow_hours, actual_hours_ytd, effective_end_date, budget_burn_pct, schedule_variance_days) |

### SPICE Refresh Mechanism

The Lambda's `refresh_quicksight_datasets()` function calls `quicksight.create_ingestion()` for each dataset ID. This is triggered:
- Automatically at the end of every standard import run (incremental/weekly/full)
- Manually via `mode=refresh_quicksight_only` with a list of dataset IDs
- From the Streamlit "Data Management" page (invokes Lambda via boto3)
- After specific operations (e.g. after `analyze_project_health`, after `mc_v2_audit`)

The QuickSight data source ARN is: `arn:aws:quicksight:us-east-1:961341524729:datasource/weekly-reporting-postgres`


---

## 7. CloudFormation Stacks

### Stack 1: `cloudelligent-quicksight-theme`

**Template:** `cloudformation/cloudelligent-quicksight-theme.yaml`

**What it creates:**
- `AWS::QuickSight::Theme` — Cloudelligent brand theme with corporate colours and typography

**Exports:**
- `CloudelligentQuickSightThemeArn` — imported by the `coo-dashboards` stack via `!ImportValue`

**Theme ID:** `cloudelligent-brand-theme`

**Parameters required:** `AwsAccountId`, `QuickSightUsername`

---

### Stack 2: `coo-dashboards`

**Template:** `cloudformation/coo-dashboards.yaml`

**What it creates:**

| Resource | CloudFormation Type | ID |
|----------|--------------------|----|
| COO Operational Analysis | `AWS::QuickSight::Analysis` | `coo-operational-analysis-prod` |
| Executive Summary Analysis | `AWS::QuickSight::Analysis` | `coo-executive-analysis-prod` |

**Parameters required:**

| Parameter | Description |
|-----------|-------------|
| `Environment` | `prod` / `staging` / `dev` (default: `prod`) |
| `QuickSightUsername` | QuickSight username granted owner access |
| `AwsAccountId` | AWS Account ID (`961341524729`) |

**Datasets referenced (must exist before deploying):**
- `kpi-weekly-snapshots-prod`
- `ps-project-status-view`
- `project-hours-by-assignment`
- `productive-utilization`
- `time-compliance-current-week`
- `escalations-detail`
- `ps-stage-trend`

**Theme dependency:** Imports `CloudelligentQuickSightThemeArn` from the theme stack — deploy theme stack first.

**COO Operational Analysis sheets:**
1. Weekly Summary
2. Project Hours
3. Delivery Health
4. Resource Utilization
5. Project Detail

---

### Post-Deploy Step: Visual Styling Patch

**Script:** `scripts/patch_qs_visual_styling.py`

Applies visual enhancements that cannot be set via CloudFormation:
- Legends (BOTTOM) on all line and bar charts
- DataLabels on bar charts
- Reference lines at 75% / 80% / 95% on the Utilization Trend chart
- Sparkline (AREA) + TrendArrows on KPI tiles
- Conditional row background colours (green/amber/red) on project health tables

**Usage:**
```bash
AWS_PROFILE=AWSAdministratorAccess-961341524729 python3 scripts/patch_qs_visual_styling.py
python3 scripts/patch_qs_visual_styling.py --dry-run   # preview only
```

Targets both analyses: `coo-operational-analysis-prod` and `coo-executive-analysis-prod`.

---

## 8. Streamlit Application

**Entry point:** `src/app.py`  
**Page config:** Title "Weekly Reporting - Cloudelligent", wide layout

### Pages / Navigation

| Page | Key Functionality |
|------|------------------|
| **Dashboard** | Practice alignment summary (PS + MC hours/resources), Managed Cloud POD breakdown (Alpha/Bravo/A2Z/SurePoint), Location breakdown (Onshore/Offshore %), Contractor summary, Recent time entries table with filters |
| **Resource Directory** | All users with hours for selected period, filters by status/practice/location/pod, Excel download |
| **Forecasting** | 4 tabs: Upload Excel (parse + import forecast template), Manual Entry (grid editor per project/staff), View Forecasts (pivot table or list view, Excel download), Forecast History (current vs previous diff, snapshot browser, dropped users log) |
| **Data Management** | Refresh Controls (invoke Lambda for views + SPICE refresh), Data Sources table (record counts + last updated), AI Analysis Configuration (prompt editors for PS/MC/MC_V2/FORECAST), Run AI Analysis / MC V2 Audit / Forecast Analysis buttons |
| **Project Mapping** | Map Jira PS/MC projects to Clockify clients/projects. Pre-populate from Clockify project type. Manage MC pods. |
| **Clockify Data Update** | Export Clockify members/projects to CSV, upload modified CSV to bulk-update custom fields in Clockify (dry-run + apply), upload history |
| **Settings** | Database statistics, User Management (add/edit/delete app login accounts), Default date range settings, Custom fields reference, Practice alignment distribution, Data freshness |

### Authentication

- **Library:** `streamlit-authenticator`
- **Backend:** `app_users` database table (bcrypt-hashed passwords)
- **Cookie:** `weekly_reporting_auth`, 7-day expiry
- **Cookie signing key:** `AUTH_COOKIE_KEY` env var
- **Seeding:** On first run with empty `app_users` table, seeds one user from `AUTH_USERNAME` / `AUTH_PASSWORD_HASH` / `AUTH_NAME` env vars
- **Bypass:** Set `DISABLE_AUTH=true` for local development

### Startup Behaviour

On every process start, `apply_pending_migrations()` runs all `.sql` files in `src/database/migrations/` in alphabetical order. Failures are logged but do not abort startup (migrations may already be applied).

### Lambda Invocation from Streamlit

The app invokes `production-clockify-import` Lambda directly via `boto3.client('lambda')` for:
- Refreshing database views (`mode=apply_views`)
- Refreshing QuickSight SPICE datasets (`mode=refresh_quicksight_only`)
- Running AI analysis (`mode=analyze_project_health`)
- Running MC V2 audit (`mode=mc_v2_audit`)
- Running forecast analysis (`mode=analyze_forecast`)

---

## 9. Key Environment Variables & Secrets

### Lambda Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `SECRET_NAME` | Env var | Secrets Manager secret name |
| `AWS_REGION` | Env var | AWS region (default: `us-east-1`) |
| `DB_ENDPOINT_PARAMETER` | Env var | SSM parameter name for RDS endpoint |
| `DB_HOST` | Env var | Fallback RDS hostname if SSM not configured |
| `DB_PORT` | Env var | PostgreSQL port (default: `5432`) |
| `DB_NAME` | Env var | Database name (default: `weekly_reporting`) |
| `DB_USER` | Env var | Database username (default: `report_user`) |
| `NOTIFICATION_TOPIC_ARN` | Env var | SNS topic ARN for import notifications |
| `ENVIRONMENT` | Env var | `production` / `staging` / `dev` |
| `BEDROCK_MODEL_ID` | Env var | Bedrock model ID (default: `us.anthropic.claude-3-5-sonnet-20241022-v2:0`) |

### Streamlit / ECS Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Full SQLAlchemy connection string (set by Lambda from secrets; set directly for Streamlit) |
| `AUTH_USERNAME` | Initial admin username (used to seed `app_users` on first run) |
| `AUTH_PASSWORD_HASH` | bcrypt hash of initial admin password |
| `AUTH_NAME` | Display name for initial admin user |
| `AUTH_COOKIE_KEY` | Random secret for cookie signing |
| `DISABLE_AUTH` | Set to `true` to bypass authentication (local dev only) |
| `AWS_PROFILE` | AWS profile for local development (loaded from `.env` via `python-dotenv`) |

### Secrets Manager Secret Structure

The secret (name from `SECRET_NAME` env var) is a JSON object with these keys:

| Key | Description |
|-----|-------------|
| `db_password` | PostgreSQL password for `report_user` |
| `clockify_api_key` | Clockify API key |
| `clockify_workspace_id` | Clockify workspace ID |
| `jira_base_url` | Jira instance base URL (e.g. `https://cloudelligent.atlassian.net`) |
| `jira_api_email` | Jira API user email |
| `jira_api_token` | Jira API token |
| `jira_project_keys` | Comma-separated Jira project keys to sync |
| `jira_phase_field_id` | Jira custom field ID for phase |

### SSM Parameter Store

| Parameter | Description |
|-----------|-------------|
| Value of `DB_ENDPOINT_PARAMETER` env var | RDS instance endpoint hostname |

---

## 10. Deployment Notes

### Lambda Deployment Package

- **Filename:** `lambda-deployment-package.zip`
- **Contents:** All source code under `src/`, plus Python dependencies
- **Key dependencies:** `pg8000` (pure-Python PostgreSQL driver), `SQLAlchemy`, `boto3`, `requests`, `openpyxl`, `bcrypt`
- **Why pg8000:** Lambda environment lacks native libs required by `psycopg2`; `pg8000` is pure Python
- **Connection string format:** `postgresql+pg8000://{user}:{password}@{host}:{port}/{dbname}`

### Deploying CloudFormation Stacks

**Step 1 — Theme stack (prerequisite):**
```bash
aws cloudformation deploy \
  --template-file cloudformation/cloudelligent-quicksight-theme.yaml \
  --stack-name cloudelligent-quicksight-theme \
  --parameter-overrides \
    AwsAccountId=961341524729 \
    QuickSightUsername=<your-qs-username> \
  --region us-east-1
```

**Step 2 — Ensure all prerequisite datasets exist** (create manually or via `mode=create_quicksight_datasets` Lambda invocation).

**Step 3 — COO dashboards stack:**
```bash
aws cloudformation deploy \
  --template-file cloudformation/coo-dashboards.yaml \
  --stack-name coo-dashboards \
  --parameter-overrides \
    Environment=prod \
    AwsAccountId=961341524729 \
    QuickSightUsername=<your-qs-username> \
  --region us-east-1
```

**Step 4 — Apply visual styling patch:**
```bash
AWS_PROFILE=AWSAdministratorAccess-961341524729 \
  python3 scripts/patch_qs_visual_styling.py
```

### Initial Database Setup

1. Deploy Lambda with correct env vars and secrets
2. Invoke Lambda with `{"mode": "full"}` to run initial 1-year Clockify import
3. Invoke Lambda with `{"mode": "jira_import", "full_sync": true}` to import all Jira projects
4. Invoke Lambda with `{"mode": "apply_views"}` to create all PostgreSQL views
5. Invoke Lambda with `{"mode": "snapshot_kpis"}` to write first KPI snapshot

### Updating Database Views

After any change to `src/database/create_views.sql`:
```json
{"mode": "apply_views"}
```
Or from the Streamlit "Data Management" page → "Refresh Database Views".

### Running a Migration

```json
{"mode": "run_migration", "migration_file": "052_add_clockify_project_type_to_hours_view.sql"}
```

---

## 11. Known Resource IDs

### AWS Account & Region

| Item | Value |
|------|-------|
| AWS Account ID | `961341524729` |
| Region | `us-east-1` |

### QuickSight Analyses

| Analysis | ID |
|----------|-----|
| COO Operational Analysis | `coo-operational-analysis-prod` |
| Executive Summary Analysis | `coo-executive-analysis-prod` |

### QuickSight Theme

| Item | Value |
|------|-------|
| Theme ID | `cloudelligent-brand-theme` |
| Theme ARN | `arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme` |
| CloudFormation export | `CloudelligentQuickSightThemeArn` |

### QuickSight Data Source

| Item | Value |
|------|-------|
| Data Source ID | `weekly-reporting-postgres` |
| Data Source ARN | `arn:aws:quicksight:us-east-1:961341524729:datasource/weekly-reporting-postgres` |

### Lambda Function

| Item | Value |
|------|-------|
| Function name | `production-clockify-import` |

### QuickSight Admin Users (known ARNs used in `create_quicksight_datasets` mode)

| User | ARN |
|------|-----|
| chris.xenos | `arn:aws:quicksight:us-east-1:961341524729:user/default/AWSReservedSSO_AWSAdministratorAccess_ed420cc098d02bac/chris.xenos` |
| tahir.nisar | `arn:aws:quicksight:us-east-1:961341524729:user/default/AWSReservedSSO_AdministratorAccess_2be0458d4fa377aa/tahir.nisar` |
| s.furlong | `arn:aws:quicksight:us-east-1:961341524729:user/default/AWSReservedSSO_AdministratorAccess_2be0458d4fa377aa/s.furlong` |
| fatima | `arn:aws:quicksight:us-east-1:961341524729:user/default/AWSReservedSSO_AWSAdministratorAccess_ed420cc098d02bac/fatima` |

### All QuickSight Dataset IDs (complete list from `get_all_dataset_ids()`)

```
clockify-pod-performance-prod
clockify-skill-area-summary-prod
clockify-daily-activity-trend-prod
clockify-import-activity-prod
clockify-missing-time-submissions-prod
clockify-missing-time-submissions
7833b3c6-cec4-4956-b02a-2316198187cb
c84d2b1f-de9d-42cd-a389-e425a100c4d4
3bdc816d-4df6-4db7-b3e6-64e230f28f14
42098a5b-a94f-41d5-8300-396f1fec66bf
fc56c886-f0d2-4935-8b32-f0862325d3f0
8900f5dc-687e-4d5b-9f91-5efd0cd1daed
ps-project-status-view
data-freshness
non-billable-analysis
free-agent-availability
ai-ps-analysis-by-user
ai-ps-analysis-by-project
ai-mc-analysis-by-user
ai-mc-analysis-by-project
ps-profitability-2026
ps-profitability-weekly-2026
ps-profitability-chart
mc-v2-audit-by-customer
mc-v2-audit-by-phase
mc-v2-audit-grid
project-hours-by-assignment
practice-group-performance
ai-forecast-analysis
ai-forecast-summary
pm-forecast-accuracy
escalations-detail
escalations-by-customer
ps-stage-trend
productive-utilization
missing-time-history
time-compliance-current-week
project-time-detail
customer-status-assignments
project-directory
project-detail-view
kpi-weekly-snapshots-prod
project-hours-summary-prod
project-hours-current-week-prod
category-hours-summary-prod
project-delivery-health-prod
escalations-detail-prod
```

---

*End of document.*
