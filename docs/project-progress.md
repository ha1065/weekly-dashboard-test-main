# Project Progress — Weekly Reporting

> Cloudelligent internal tool: Clockify → PostgreSQL → QuickSight dashboards
> Initialized: 2026-05-04

## Current State

**Deployed and actively developed.** This is not a greenfield build — the orchestrator workflow is adapted for an existing, organically grown tool that needs formalization and continued feature work.

**Requirements source:** 2026 COO OKRs (docs/2026-coo-okrs.md)
**Data governance:** docs/COO_DASHBOARD_VIEWS.md

---

## Phase 1: System Documentation (formalize what exists)

- [x] 1.1 README and IMPLEMENTATION_SUMMARY exist (Jan 2026)
- [x] 1.2 AWS_DEPLOYMENT guide exists (Jan 2026)
- [x] 1.3 COO Dashboard Views derivation reference (Apr 2026)
- [x] 1.4 COO OKRs documented (May 2026)
- [ ] 1.5 System architecture doc — formalize current state (data flow, services, integrations, DB schema)
- [ ] 1.6 Data source inventory — complete mapping of all external data sources and their sync schedules

## Phase 2: Architecture Baseline (document current deployed state)

- [x] 2.1 CloudFormation infra template (template.yaml) — deployed
- [x] 2.2 QuickSight dashboard templates (quicksight-dashboards.yaml, coo-dashboards.yaml) — deployed
- [x] 2.3 QuickSight theme template (cloudelligent-quicksight-theme.yaml) — deployed
- [x] 2.4 Streamlit ECS template (streamlit-ecs.yaml) — exists
- [ ] 2.5 Security review of deployed infrastructure (IAM, VPC, encryption, secrets)
- [ ] 2.6 Cost baseline — current monthly AWS spend documented

## Phase 3: Backlog & Planning (ongoing feature work)

- [x] 3.1 Feature backlog created from COO OKR gaps and known TODOs
- [x] 3.2 Priority ranking based on OKR quarterly targets
- [x] 3.3 Sprint plan for next development cycle (docs/implementation-plan.md — 6-sprint plan)

## Phase 4: Active Development

### Data Pipeline
- [x] Clockify import (incremental, full, weekly modes)
- [x] Jira import (project status, health, schedule)
- [x] Escalations import from Jira
- [x] KPI snapshot Lambda (weekly automated)
- [x] Forecast import from Excel
- [x] MC v2 audit import
- [ ] DeliverPro integration (KR2.4 — not yet available, deferred)

### Database (72 migrations through 097)
- [x] Core tables (users, projects, time_entries)
- [x] PS project mapping and status
- [x] Escalations table
- [x] KPI weekly snapshots table
- [x] MC ticket activity snapshots
- [x] COO dashboard views (project hours, category hours, KPI YTD)
- [x] Forecast config table (migration 095)
- [x] PS at-risk expanded filter (migration 096)
- [x] Escalation normalization (migration 097)

### QuickSight Dashboards
- [x] Base reporting dashboards (quicksight-dashboards.yaml)
- [x] COO operational dashboard (coo-dashboards.yaml)
- [x] CE branding theme
- [x] COO analysis: Compliance History, Utilization History, Resource Capacity sheets added
- [x] coo-dashboards.yaml synced from live (pWeekEnd → pWeekStart, default 2026-06-23)
- [ ] Theme update to official brand colors (#0089DD, #FF9B00, #D74018, #33A94F)

### Streamlit Dashboard
- [x] Local dashboard with import management
- [x] ECS deployment template exists
- [x] All 17 tabs implemented (Sprints 1–6)
- [x] AI Analysis extracted to own page
- [x] Settings sections collapsed, Operations renamed to Data Management
- [x] Forecast Config editor

### Scripts (active development — May 2026)
- [x] QuickSight visual styling patches
- [x] Escalation status fixes
- [x] 5x5 matrix user access
- [x] Donut chart fixes
- [x] NB KPI additions
- [x] Time filter fixes
- [x] CE theme application

---

## Session Log

| Date | What | Category |
|------|------|----------|
| 2026-05-14 | Fixed ~/.aws/config (broken INI format — shell commands pasted as values, region set to "bash"). Backed up to ~/.aws/config.backup. AWS CLI now functional. | Infrastructure / DevEx |
| 2026-05-14 | Disabled Figma MCP server — OAuth not supported in Kiro CLI, only IDE. (.kiro/settings/mcp.json) | Configuration |
| 2026-05-14 | Created 4 AIDLC tracking hooks: track-doc-changes, track-new-files, audit-writes, sync-progress. Ensures out-of-band work is logged. | Process / Governance |
| 2026-05-14 | Created `docs/secrets-manager-migration-review.md` — team review document summarizing the Secrets Manager migration plan for `jira-data-pull-lambda` and `clockify-data-processor`. Companion to existing `docs/secrets-manager-migration-plan.md`. Status: Proposed, awaiting team approval. | Security / Infrastructure |
| 2026-05-14 | Created `docs/secrets-manager-migration-review.md` — team review summary for migrating `jira-data-pull-lambda` and `clockify-data-processor` API keys to Secrets Manager. Pending team approval before implementation. | Security / Documentation |
| 2026-05-14 | Created `docs/hook-based-methodology-compliance.md` — generic framework doc for using Kiro hooks to enforce development methodology compliance. Covers 6 layers of enforcement, example hooks, maturity-based recommendations, and anti-patterns. Ad-hoc request, not tied to a story. | Process / Documentation |
| 2026-05-14 | Created `docs/hook-based-methodology-compliance.md` — general framework doc for using Kiro agent hooks as automated process guardrails (pre-write gates, file watchers, session audits, task lifecycle gates). Out-of-band addition, not tied to a specific backlog story. | Process / Governance |
| 2026-06-08 | S01-02 human gate complete: practice_area backfill reviewed and corrected for all 69 active timekeeping users. MIT added as valid value for Managed IT practice. CHECK constraint updated. Zero remaining NULLs. | Implementation / Data |
| 2026-06-08 | Created `docs/implementation-plan.md` — 6-sprint plan for 17-tab dashboard redesign. 1 solo developer, 2-week sprints, est. completion 2026-08-29. 46 stories, 331 hrs. | Planning |
| 2026-06-08 | Added Tab 17 — Organizational KPI Scorecard to SRS (v1.0 → v1.1). COO requirement: QTD view of on-time delivery (PS only, point-in-time), timesheet compliance, utilization, and escalations with monthly trend lines. Zero new migrations/views/datasets needed — reuses kpi-weekly-snapshots-prod. FR-17-001, FR-17-002. | Product / Planning |
| 2026-06-08 | Fixed 4 failing SPICE datasets (all from 08:14 Monday run): (1) `vw_category_hours_summary` + `vw_project_hours_current_week` missing — re-applied migration 050; (2) `nb_nonproductive_hours` column missing on `kpi_weekly_snapshots` — applied migration 061 + rebuilt `vw_kpi_ytd` via migration 065; (3) `sort_order` column missing on `ps_stage_weekly_snapshot` — added column + backfilled. All 4 SPICE ingestions completed. Script: `scripts/fix_spice_refresh_errors.py`. | QuickSight / Data Pipeline |
| 2026-06-10 | S01-09 complete: Added "Org KPI Scorecard" sheet to COO Operational Dashboard. 4 QTD KPI tiles (On-Time Delivery, Compliance, Utilization, Open Escalations) with prior-quarter delta comparison + 4 monthly trend line charts. Script: `scripts/add_kpi_scorecard_sheet.py`. | QuickSight / Sprint 1 |
| 2026-06-10 | Fixed blank "Utilization Detail" sheet on COO Operational Dashboard. Root cause: column name mismatches (`user_name` → `employee_name`, `week_start_date` → `week_start`). Rebuilt sheet with correct schema. Script: `scripts/fix_util_detail_sheet.py`. | QuickSight / Bug Fix |
| 2026-06-10 | S01-10 complete: Added `practice_area` editor to Streamlit Settings page. Inline selectbox per active user (options: PS/MC/Both/MIT/Internal/Exempt), single-form save, null-count warning banner. Also added `practice_area` column to `ClockifyUser` SQLAlchemy model. | Streamlit / Sprint 1 |
| 2026-06-10 | Sprint 2 complete: S02-01–S02-08 all done. Lambda enhancements: seasonal correction factor, 8-week dynamic lookback, PM forecast accuracy scoring (ai_pm_forecast_accuracy), practice_area filter replacing practice_alignment ILIKE. Tab 1 (Weekly Ops) and Tab 2 (PS Projects) added to Streamlit. S02-08: vw_project_hours_by_assignment confirmed FR-CCR-008 compliant (project-based classification only). | Streamlit / Lambda / Sprint 2 |
| 2026-06-10 | Sprint 3 partial: S03-01 (Tab 4 MC Delivery), S03-02 (Tab 5 Missing Time), S03-03 (Tab 12 Escalations) complete. S03-04/05/06/07 BLOCKED — awaiting CONFLUENCE_API_TOKEN + CONFLUENCE_BASE_URL from DevOps. | Streamlit / Sprint 3 |
| 2026-06-10 | S03-04/S03-05 unblocked: Confluence uses same Atlassian credentials as Jira (JIRA_API_TOKEN + JIRA_BASE_URL already in Secrets Manager). Implemented Confluence artifact verification in mc_v2_audit.py — seeds artifact_verification from Done MC issues, verifies remote links via /wiki/ HEAD requests, batches 10 at a time. S03-05 inspection script created. S03-06 (Tab 10 MC V2 Audit) implemented. Sprint 3 fully complete. | Lambda / Streamlit / Sprint 3 |
| 2026-06-10 | Sprint 4 complete: S04-01 (Tab 6 Resource Forecast), S04-02 (Tab 7 Resource Capacity), S04-03 (Tab 13 Utilization), S04-07 (Profitability Rates editor in Settings) done. S04-04/05 QS SPICE validations deferred (no errors reported). S04-06 QS ML Insights deferred (Should Have, not blocking). | Streamlit / Sprint 4 |
| 2026-06-10 | Sprint 5 complete: S05-02 (Tab 8 PS Delivery Analysis), S05-03 (Tab 9 NB Analysis), S05-04 (Tab 11 Project Hours Trend), S05-05 (migration 072 nb_subcategory), S05-06 (vw_project_hours_summary updated). S05-01 (Tab 3 Profitability) BLOCKED — awaiting profitability rate values from stakeholder. | Streamlit / Sprint 5 |
| 2026-06-10 | S05-01 unblocked + complete: Tab 3 PS Profitability implemented. Rates confirmed: onshore=$150/hr, offshore=$35/hr, contractor=$120/hr, billable=$150/hr. Seeder script: scripts/seed_profitability_rates.py. All 17 tabs now fully implemented. | Streamlit / Sprint 5 |
| 2026-06-10 | Sprint 6 complete: S06-01 (Tab 14 Time Detail), S06-02 (Tab 15 Assignments), S06-03 (Tab 16 Project Runway), S06-04 (data freshness sidebar timestamp NFR-002), S06-07 (migration count updated to 072). S06-05/S06-06 smoke test deferred — all 17 tabs now implemented. | Streamlit / Sprint 6 |
| 2026-06-10 | Multi-page split attempted — deferred. src/shared.py created (auth/DB shared module). src/app.py restored from lambda_package_temp backup after accidental overwrite. All 23 page handlers confirmed in src/app.py (~3400 lines). Split will resume after smoke test. | Architecture / Refactor |

---

## Known Gaps & TODOs

| # | Area | Gap | Source |
|---|------|-----|--------|
| 1 | Architecture | No formal architecture doc — system knowledge is spread across README, IMPLEMENTATION_SUMMARY, AWS_DEPLOYMENT | Orchestrator assessment |
| 2 | Branding | QuickSight theme uses #1B2766/#2D6DF6 instead of official CE colors | docs/2026-coo-okrs.md |
| 3 | Data | DeliverPro not yet available — KR2.4 governance metrics use existing sources | docs/2026-coo-okrs.md |
| 4 | Backlog | No formal feature backlog — work is driven ad-hoc from OKR needs | Orchestrator assessment |
| 5 | Testing | Tests exist but coverage unknown for recent features (COO views, KPI snapshots) | tests/ directory |
| 6 | Steering | .kiro steering files are from iCivics LMS project — not adapted for this project | .kiro/steering/ |
| 2026-06-10 | ps_profitability_rates seeded via Lambda: onshore=$150/hr, offshore=$35/hr, contractor=$120/hr, billable=$150/hr. | Data / Config |
| 2026-06-10 | COO Operational Dashboard v22 published: Org KPI Scorecard sheet added (4 QTD KPI tiles + 4 monthly trend charts on kpi-weekly-snapshots-prod). Utilization Detail sheet rebuilt with correct column names (employee_name, week_start). Theme: cloudelligent-brand-theme. | QuickSight |
| 2026-06-10 | practice_area backfill complete: 0 NULLs for active timekeeping users (69 users). Distribution: ~20 MC, ~40 PS, 8 MIT, 1 Internal. | Data / Governance |
| 2026-06-12 | Fixed clockify-missing-time-submissions SPICE dataset failure. Root cause: vw_missing_time_submissions was rebuilt without last_updated_date column during sprint migrations. Re-applied view via Lambda (separate DROP + CREATE statements). Dataset now ingesting 16 rows. Script: scripts/fix_missing_time_view.py. | QuickSight / Data Pipeline |
| 2026-06-12 | Fixed clockify-missing-time-submissions SPICE dataset failure. Root cause: vw_missing_time_submissions rebuilt without last_updated_date during sprint migrations. Re-applied view via Lambda (separate DROP + CREATE), 16 rows ingested. Script: scripts/fix_missing_time_view.py. | QuickSight / Bug Fix |
| 2026-06-26 | Phase 0 complete: Lambda v173 deployed, views applied, EventBridge noon rule fixed, KPI count gap closed (24→27), SES IAM added. All Monday readiness checks pass. | Infrastructure / Data Pipeline |
| 2026-06-26 | Sprint 1 complete: S1-06 (EventBridge IaC warning), S1-09/10 (migrations 096/097 — PS at-risk expanded filter + escalation normalization), S1-11 (Jira daily rule fixed), S1-14 (stale files deleted). S1-15/16/17 audited — no action needed. | Infrastructure / Data Quality |
| 2026-06-26 | Sprint 2 (UX) complete: 5 Streamlit quick wins — AI Analysis extracted to own page, Settings sections collapsed, Governance data freshness row added, SPICE table height capped, Operations renamed to Data Management. | Streamlit / UX |
| 2026-06-26 | Sprint 3 complete: forecast_config table (095), 3-signal blend in forecast_resources.py, Streamlit Forecast Config editor (S3-03), Jira upsert ON CONFLICT confirmed. Views vw_time_compliance_history + vw_utilization_history confirmed live. | Lambda / Data Layer |
| 2026-06-26 | Sprint 4 complete: S4-01 Resource Capacity tab, S4-02 Project Time Detail expander (Governance), S4-03 Customer Status Assignments expander (Project Config). QuickSight: 3 new sheets added to COO analysis (Compliance History, Utilization History, Resource Capacity). coo-dashboards-prod deployed UPDATE_COMPLETE. | Streamlit / QuickSight |
| 2026-06-26 | P0-3 complete: coo-dashboards.yaml synced from live analysis, pWeekEnd renamed to pWeekStart (15 occurrences), default set to 2026-06-23T00:00:00Z. Stack deployed UPDATE_COMPLETE. | IaC / QuickSight |
| 2026-06-26 | P0-4 complete: KPI active project count gap fixed. Root cause: kpi_snapshot.py filtered status_category = 'In Progress' excluding 2 'To Do' projects. Changed to != 'Done'. Lambda redeployed v172, KPI reseeded. ps_active_projects now = 27 matching vw_ps_project_status. | Data Quality |
| 2026-06-26 | S6-03 complete: Operational runbooks created — docs/runbooks/monday-import-failure.md, docs/runbooks/spice-refresh-failure.md, docs/runbooks/view-deploy-procedure.md. Covers Monday recovery, 14 SPICE datasets, view deploy paths, EventBridge safety check. | Documentation / Operations |
| 2026-07-01 | CE theme restored on COO Operational Dashboard (v36 published). Root cause: `add_tu_filters.py` called `update_dashboard` without `ThemeArn` — theme stripped to AWS default on v35 (Jun 29 18:02). Fix: `restore_dashboard_theme.py` run → v36 published with `cloudelligent-brand-theme`. Prevention: `add_tu_filters.py` patched to include `ThemeArn` on every `update_dashboard` call. `sync_coo_dashboard_iac.py` updated with ⚠️ warning. Full analysis: `docs/theme-issue-analysis-2026-06-29.md`. | QuickSight / Bug Fix |
