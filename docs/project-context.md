# Cloudelligent Weekly Reporting — Project Context

> Last updated: 2026-06-23
> This file is the authoritative context reference for all agents working on this project.

---

## System Overview

**Purpose:** Internal COO reporting and governance tool for Cloudelligent, a managed services / AWS consulting company.

**Data pipeline:**
```
Clockify API → AWS Lambda → RDS PostgreSQL (clockify_reporting) → QuickSight SPICE → 3 Dashboards
Jira API     ↗
```

**AWS Account:** 961341524729
**Region:** us-east-1
**Lambda function:** `production-clockify-import`
**RDS database:** `clockify_reporting` (PostgreSQL, private subnet)
**QuickSight theme:** `cloudelligent-brand-theme` (MIDNIGHT base)

---

## Three-Tier Reporting Model

| Dashboard | Audience | Purpose | Cadence |
|-----------|----------|---------|---------|
| Executive Summary (`coo-executive-analysis-prod`) | CEO/COO | 1-2 page pulse — delivery health at a glance | Weekly glance |
| COO Operational Analysis (`coo-operational-analysis-prod`) | Leadership team | Weekly meeting walkthrough — state of service delivery | Weekly meeting |
| Weekly Reporting (Streamlit, ECS) | COO governance | Granular detail — individual tracking, compliance, PM/project analysis | Weekly governance |

---

## COO Operational Analysis — 5 Sheets

| Sheet ID | Name | Datasets | Purpose |
|----------|------|----------|---------|
| `sheet-weekly-pulse` | Weekly Pulse | `kpi_snapshots`, `project_hours_summary` | Top-line KPIs + utilization trend + project word cloud |
| `sheet-ps-delivery` | PS Delivery | `kpi_snapshots`, `ps_projects`, `ps_at_risk`, `ps_stage` | PS health KPIs + donut + stage bar + project health table |
| `sheet-mc-delivery` | MC Service Delivery | `kpi_snapshots`, `mc_activity`, `mc_at_risk` | MC health KPIs + hours/tickets bars + customer health table |
| `sheet-escalations` | Escalations | `escalations` | KPI strip + by-customer/assignee bars + detail table |
| `sheet-time-util` | Time & Utilization | `kpi_snapshots`, `productive_util`, `compliance` | Compliance KPIs + non-compliant staff table + utilization table |

**Analysis ID:** `coo-operational-analysis-prod`
**Dashboard ID:** `coo-operational-dashboard-prod`
**Parameter:** `pWeekEnd` (DATE) — filters all KPI tiles to selected week

---

## Design Standards

### CE Brand Colors (MIDNIGHT theme)
| Token | Hex | Usage |
|-------|-----|-------|
| Primary blue | `#0089DD` | PS series, primary actions, line charts |
| Orange | `#FF9B00` | MC series, Amber/warning health |
| Red | `#D74018` | Red health, critical KPIs below target |
| Green | `#33A94F` | Green health, KPIs above target |
| Dark purple | `#27164F` | Headers, table text, titles |
| Background | `#F4F3F7` | Sheet background |
| Font | Inter Regular + Bold | All text |

### Layout Principles (CUDOS-inspired)
- KPI strip always at top (4-6 tiles, full width, equal span)
- One question per visual, stated in title
- Title format: `"[What] — [Context]"`
- Health: Green=`#33A94F`, Amber=`#FF9B00`, Red=`#D74018`, Not Assigned=`#AAAAAA`
- PS series always blue, MC series always orange
- Tables: `#27164F` header background, white header text, `#2A1545` alternating rows

---

## Data Sources & Governance

| Source | System of Record For | Sync Schedule |
|--------|---------------------|---------------|
| Clockify | Time entries, users, projects, utilization, compliance, billable hours | Mon 9am CT + Mon noon CT (incremental) |
| Jira | Project status, health (R/A/G), stage, PM/SA assignments, SOW hours, escalations | Daily 10am UTC |
| PS Resource Forecasts | Forecasted hours (Excel template → `ps_resource_forecasts`) | Manual upload |

**Key rule:** Clockify is authoritative for all time data. Jira is authoritative for project status and health. Never mix sources for the same metric.

---

## Key Database Tables & Views

### Core Tables
- `clockify_detailed_time_entries` — raw time entries
- `clockify_users` — user roster with capacity, pod, practice alignment
- `clockify_projects` — project metadata with project_type, pod_assignment
- `ps_project_status` — Jira PS/MC project health (synced daily)
- `ps_project_mapping` — Clockify→Jira client name mapping
- `escalations` — Jira escalation issues
- `kpi_weekly_snapshots` — weekly KPI point-in-time snapshots
- `mc_ticket_activity_snapshot` — MC customer ticket activity

### Key Views (in create_views.sql)
- `vw_ps_project_status` — enriched PS project view with Clockify actuals
- `vw_productive_utilization` — per-person weekly billable/NB hours
- `vw_missing_time_submissions` — zero-hours staff for last complete week
- `vw_weekly_compliance_report` — all staff compliance for last complete week
- `vw_mc_ticket_activity` — MC customer activity with WoW comparison
- `vw_kpi_ytd` — KPI snapshots with WoW deltas and _prev LAG columns (migration 060)

### QuickSight Datasets (COO Dashboard)
| Dataset ID | Source View/Table | Refresh |
|------------|-------------------|---------|
| `kpi-weekly-snapshots-prod` | `vw_kpi_ytd` | Mon noon CT |
| `ps-project-status-view` | `vw_ps_project_status` | Daily |
| `productive-utilization` | `vw_productive_utilization` | Mon noon CT |
| `clockify-missing-time-submissions-prod` | `vw_missing_time_submissions` | Mon noon CT |
| `escalations-detail` | `vw_escalations` | Daily |
| `ps-stage-trend` | `vw_ps_stage_trend` | Daily |
| `project-hours-summary-prod` | `vw_project_hours_summary` | Mon noon CT |
| `mc-ticket-activity` | `vw_mc_ticket_activity` | Daily |
| `ps-projects-at-risk` | custom view | Daily |
| `mc-projects-at-risk` | `mc_ticket_activity_snapshot` | Daily |

---

## Import Schedule (EventBridge)

| Rule | Schedule | Payload |
|------|----------|---------|
| `production-weekly-import-9am-ct` | Mon 9am CT | `{"mode":"weekly","weeks_back":2,"notify":true,"refresh_quicksight":true}` |
| `production-weekly-import-noon-ct` | Mon noon CT | `{"mode":"incremental","snapshot_kpis":true,"notify":true,"refresh_quicksight":true,"quicksight_dataset_ids":[...COO datasets...]}` |
| `production-jira-daily-refresh` | Daily 10am UTC | `{"mode":"jira_import","refresh_quicksight":true}` |

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/apply_views_direct.py` | Drop dependent views + apply create_views.sql directly (bypasses Lambda) |
| `scripts/publish_coo_dashboard.py` | Republish COO dashboard from current analysis definition |
| `scripts/republish_from_analysis.py` | Fetch live analysis + publish dashboard + wait for completion |
| `scripts/sync_coo_dashboard_iac.py` | Export live analysis → write to coo-dashboards.yaml |
| `scripts/export_live_analysis.py` | Export live analysis to coo-analysis-live.json |
| `scripts/check_all_spice.py` | Check SPICE ingestion status for all datasets |
| `scripts/dashboard_accuracy_audit.py` | Full accuracy audit: import schedule, data freshness, SPICE status |

---

## 2026 COO OKRs (Dashboard-Relevant)

| KR | Description | Q2 Target | Q4 Target | Dashboard Measurement |
|----|-------------|-----------|-----------|----------------------|
| KR2.1 | On-time delivery rate | 60% | 90% | `ps_on_time_pct` in kpi_snapshots |
| KR2.2 | Avg engagement duration | 10 weeks | 5 weeks | `ps_avg_duration_weeks` in kpi_snapshots |
| KR2.4 | Projects in Red <10% | Red <20% | Red <10% | `total_projects_red` in kpi_snapshots |
| KR5.1 | 95%+ data hygiene, real-time visibility | 80% hygiene | 95%+ | Time compliance %, data freshness |
| KR5.4 | Offshore talent in strategic roles | First elevated | Top 20% elevated | TBD — requires strategic_role flag |
| KR3.4 | Expansion signals from delivery | Logging active | 30%+ logging | TBD — requires HubSpot/Jira integration |

**KR2.3** (Kiro adoption) is **out of scope** — requires Kiro usage data not available in this pipeline.

---

## Current State (as of 2026-05-12)

### Working
- COO Operational Analysis: 5 sheets, 10 datasets, MIDNIGHT theme
- PS Project Health table: conditional formatting (health, budget health, schedule health, escalation)
- Compliance view: zero-hours threshold (people who logged nothing)
- KPI snapshot: PS active projects aligned with dashboard filter (issue_type='Emailed request')
- vw_kpi_ytd: _prev LAG columns for WoW comparisons
- Noon import: chains to KPI snapshot + targeted COO SPICE refresh
- IaC: coo-dashboards.yaml synced from live analysis

### Known Issues
1. `apply_views` Lambda mode broken — **FIXED 2026-06-23, deploy pending**
2. pWeekEnd parameter default stale — **FIXED 2026-06-23: renamed pWeekStart, update_analysis_week_parameter() updated**
3. PS Active Projects KPI (24) vs live view (19) — 5 project gap — **under investigation (verify after apply_views deploy)**
4. Executive Summary not yet redesigned
5. Streamlit Dashboard/Resource Directory pages redundant with QuickSight — **addressed in master-plan.md Phase 2**

### Recent Changes (2026-06-23)
- `kpi_snapshot.py` billable hours + total_logged queries now filter `reporting_excluded` users (C1)
- `vw_ps_projects_at_risk` filter expanded to any-dimension-at-risk, not health-only (C2)
- `vw_ps_project_status` escalation column normalized to `'Red'`/`'Green'` (C3)
- `update_analysis_week_parameter()` updated to handle both `pWeekEnd` and `pWeekStart` during rename transition
- Duplicate `run_migration` handler at line ~590 removed from `lambda_handler.py`
- `shared.py:apply_pending_migrations()` now idempotent via `schema_migrations` tracking table
- Migrations 083 (schema_migrations table), 084 (drop legacy views) added
- Master implementation plan written to `docs/master-plan.md`

### Implementation Plan
See `docs/dashboard-implementation-plan.md` for full sprint backlog.

---

## File Locations

| File | Purpose |
|------|---------|
| `src/database/create_views.sql` | All PostgreSQL views |
| `src/database/migrations/` | Numbered migration files (001-060) |
| `src/integrations/kpi_snapshot.py` | Weekly KPI snapshot computation |
| `src/lambda_handler.py` | Lambda entry point, all modes |
| `cloudformation/coo-dashboards.yaml` | COO dashboard IaC (synced from live) |
| `cloudformation/cloudelligent-quicksight-theme.yaml` | CE brand theme |
| `docs/2026-coo-okrs.md` | Full OKR definitions with quarterly targets |
| `docs/COO_DASHBOARD_VIEWS.md` | View derivation reference |
| `docs/dashboard-review-history.md` | Dashboard review session log |
| `docs/dashboard-implementation-plan.md` | Sprint backlog |
