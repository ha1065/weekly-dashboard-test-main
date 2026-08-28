# Weekly Reporting Dashboard — Implementation Plan

**Version:** 1.0  
**Date:** 2026-06-08  
**Team:** 1 developer (full-stack solo)  
**Sprint cadence:** 2 weeks · ~60 hours/sprint  
**Start date:** 2026-06-09  
**Migration baseline:** 065 (as of 2026-06-08)  
**SRS reference:** `docs/weekly-reporting-dashboard-spec.md` v1.1

---

## Phase Overview

| Phase | Focus | Sprints |
|-------|-------|---------|
| 1 — Foundation | DB migrations (no-dep blockers first) | S1 |
| 2 — Data Layer | Views + Lambda changes | S2–S3 |
| 3 — QuickSight Datasets | New + updated SPICE datasets | S3–S4 |
| 4 — Streamlit Tabs | All 17 tabs | S4–S9 |
| 5 — QS Tab 17 | Org KPI Scorecard (pure QuickSight) | S1 (quick win) |

---

## Sprint 1 — Foundation + Quick Win
**Dates:** 2026-06-09 – 2026-06-20  
**Goal:** All foundation migrations in place; Tab 17 live; Jira import data quality fixed  
**Capacity:** 60 hrs

| Story ID | Title | Type | Hrs | Depends On | FR Ref |
|----------|-------|------|-----|------------|--------|
| S01-01 | Migration 066: Add `practice_area` column to `clockify_users` + best-effort backfill SQL | Migration | 4 | — | FR-CCR-001 |
| S01-02 | **[HUMAN GATE]** Review & correct `practice_area` backfill output for all active users | Manual | 4 | S01-01 | FR-CCR-001 |
| S01-03 | Migration 067: Create `ps_profitability_rates` table (placeholder NULLs) | Migration | 2 | — | FR-CCR-002 |
| S01-04 | Migration 070: Create `artifact_verification` table | Migration | 2 | — | FR-10 |
| S01-05 | Migration 071: Dedup `ps_project_status` + add UNIQUE constraint on `jira_issue_id` | Migration | 4 | — | FR-CCR-005 |
| S01-06 | Fix Jira import upsert: `INSERT … ON CONFLICT` for `ps_project_status` | Lambda | 4 | S01-05 | FR-CCR-005 |
| S01-07 | Migration 068: Create `vw_time_compliance_history` view | View | 6 | S01-01 | FR-CCR-003 |
| S01-08 | Migration 069: Create `vw_utilization_history` view | View | 4 | S01-01 | FR-CCR-004 |
| S01-09 | **Tab 17 — Org KPI Scorecard** (QuickSight sheet: 4 QTD tiles + 4 trend lines on `kpi-weekly-snapshots-prod`) | QuickSight | 10 | — | FR-17-001/002 |
| S01-10 | Add `practice_area` Streamlit settings editor (Settings page) | Streamlit | 6 | S01-01 | FR-CCR-001 |
| S01-11 | Confirm `vw_project_time_detail` has `user_name`; re-apply view if needed | View | 2 | — | FR-CCR-006 |
| S01-12 | Register new QuickSight datasets: `time-compliance-history`, `utilization-history` | QuickSight | 4 | S01-07, S01-08 | FR-05, FR-13 |
| S01-13 | Update `project-time-detail` QS dataset to expose `user_name` field | QuickSight | 2 | S01-11 | FR-CCR-006 |

**Sprint total: 54 hrs**

> ⚠️ **S01-02 is a hard gate** — Lambda change S02-04 (practice_area filter in forecast_resources.py) cannot be deployed until this manual review is complete and validated.  
> ⚠️ **S01-03 is BLOCKED** on rate values from business stakeholder (onshore/offshore/contractor/billable rates). Table will be created with NULLs; Tab 3 implementation blocked until rates provided.

---

## Sprint 2 — Data Layer + Tab 1 & 2
**Dates:** 2026-06-23 – 2026-07-04  
**Goal:** Lambda enhancements done; Tab 1 and Tab 2 live  
**Capacity:** 60 hrs

| Story ID | Title | Type | Hrs | Depends On | FR Ref |
|----------|-------|------|-----|------------|--------|
| S02-01 | Lambda: `forecast_resources.py` — seasonal correction factor | Lambda | 6 | — | FR-CCR-007 |
| S02-02 | Lambda: `forecast_resources.py` — dynamic lookback window (4w vs 8w) | Lambda | 4 | — | FR-CCR-007 |
| S02-03 | Lambda: `forecast_resources.py` — PM forecast accuracy scoring → `ai_pm_forecast_accuracy` | Lambda | 6 | — | FR-CCR-007 |
| S02-04 | Lambda: `forecast_resources.py` — replace `practice_alignment ILIKE` with `practice_area IN ('PS','Both')` | Lambda | 2 | S01-02 ✅ human gate | FR-CCR-007 |
| S02-05 | **Tab 1 — Weekly Operations Summary** (6 KPI tiles + weekly drill-down table) | Streamlit | 12 | S01-06 | FR-01 |
| S02-06 | **Tab 2 — PS Project Status** (project table, health donut, stage bar) | Streamlit | 12 | S01-05, S01-06 | FR-02 |
| S02-07 | New QS dataset: `ps-stage-trend` verify sort_order fix working; add `ps-profitability-rates` dataset stub | QuickSight | 4 | S01-03 | FR-03 |
| S02-08 | Confirm `vw_project_hours_summary` project-based classification only (FR-CCR-008) | View | 4 | — | FR-CCR-008 |

**Sprint total: 50 hrs**

> ⚠️ **S02-04 blocked** if S01-02 human gate not complete.

---

## Sprint 3 — Tabs 4, 5, 12 + MC Lambda
**Dates:** 2026-07-07 – 2026-07-18  
**Goal:** MC delivery, missing time, and escalations tabs live  
**Capacity:** 60 hrs

| Story ID | Title | Type | Hrs | Depends On | FR Ref |
|----------|-------|------|-----|------------|--------|
| S03-01 | **Tab 4 — MC Service Delivery** (KPI tiles, customer table, health rollup) | Streamlit | 10 | S01-06 | FR-04 |
| S03-02 | **Tab 5 — Missing Time Report** (compliance history table + trend) | Streamlit | 8 | S01-07 | FR-05 |
| S03-03 | **Tab 12 — Escalations** (open escalations table, priority breakdown) | Streamlit | 8 | — | FR-12 |
| S03-04 | Lambda: `mc_v2_audit.py` — Confluence artifact verification → `artifact_verification` table | Lambda | 10 | S01-04 | FR-10 |
| S03-05 | Update `mc-v2-audit` QS dataset to JOIN `artifact_verification` | QuickSight | 4 | S03-04 | FR-10 |
| S03-06 | **Tab 10 — MC V2 Audit** (phase completion, artifact status) | Streamlit | 10 | S03-04, S03-05 | FR-10 |
| S03-07 | New QS dataset: `mc-v2-audit` artifact columns refresh + SPICE ingest | QuickSight | 4 | S03-05 | FR-10 |

**Sprint total: 54 hrs**

> ⚠️ **S03-04, S03-05, S03-06 BLOCKED** — requires `CONFLUENCE_API_TOKEN` and `CONFLUENCE_BASE_URL` in Secrets Manager. Mark as BLOCKED until DevOps provides credentials.

---

## Sprint 4 — Tabs 6, 7, 13
**Dates:** 2026-07-21 – 2026-08-01  
**Goal:** Forecasting, capacity, and utilization tabs live  
**Capacity:** 60 hrs

| Story ID | Title | Type | Hrs | Depends On | FR Ref |
|----------|-------|------|-----|------------|--------|
| S04-01 | **Tab 6 — Resource Forecast** (capacity model vs PM forecast, accuracy scoring) | Streamlit | 14 | S02-01–S02-03 | FR-06 |
| S04-02 | **Tab 7 — Resource Capacity** (available for assignment heatmap, conflict flags) | Streamlit | 12 | S02-04 | FR-07 |
| S04-03 | **Tab 13 — Productive Utilization** (utilization history trend, category breakdown) | Streamlit | 10 | S01-08 | FR-13 |
| S04-04 | New QS dataset: `utilization-history` SPICE refresh validation | QuickSight | 2 | S01-08, S01-12 | FR-13 |
| S04-05 | New QS dataset: `time-compliance-history` SPICE refresh validation | QuickSight | 2 | S01-07, S01-12 | FR-05 |
| S04-06 | QuickSight ML Insights setup on utilization % series | QuickSight | 8 | S04-04 | FR-CCR-007 |
| S04-07 | `ps_profitability_rates` Streamlit settings editor | Streamlit | 6 | S01-03 | FR-CCR-002 |

**Sprint total: 54 hrs**

> ⚠️ **S04-07 BLOCKED** until business stakeholder provides rate values.

---

## Sprint 5 — Tabs 3, 8, 9, 11
**Dates:** 2026-08-04 – 2026-08-15  
**Goal:** Profitability, AI analysis, NB analysis, project hours trend live  
**Capacity:** 60 hrs

| Story ID | Title | Type | Hrs | Depends On | FR Ref |
|----------|-------|------|-----|------------|--------|
| S05-01 | **Tab 3 — PS Profitability** (onshore/offshore mix, SOW burn, rates) | Streamlit | 14 | S01-03 ✅ rates provided, S04-07 | FR-03 |
| S05-02 | **Tab 8 — PS Delivery Analysis** (AI analysis tiles by project + user) | Streamlit | 8 | — | FR-08 |
| S05-03 | **Tab 9 — Non-Billable Analysis** (NB category breakdown, 12-week trend) | Streamlit | 12 | S02-08 | FR-09 |
| S05-04 | **Tab 11 — Project Hours Trend** (weekly hours per project, 4w/12w avg) | Streamlit | 10 | S01-12 | FR-11 |
| S05-05 | Add `nb_subcategory` field to `ps_project_mapping` (migration) | Migration | 4 | — | OQ-007 |
| S05-06 | Update `vw_project_hours_summary` to expose `nb_subcategory` | View | 4 | S05-05 | FR-09 |

**Sprint total: 52 hrs**

> ⚠️ **S05-01 BLOCKED** until rate values confirmed (same blocker as S04-07).

---

## Sprint 6 — Tabs 14, 15, 16 + Polish
**Dates:** 2026-08-18 – 2026-08-29  
**Goal:** Remaining tabs live; full dashboard complete  
**Capacity:** 60 hrs

| Story ID | Title | Type | Hrs | Depends On | FR Ref |
|----------|-------|------|-----|------------|--------|
| S06-01 | **Tab 14 — Project Time Detail** (drill-down time entry table with user_name) | Streamlit | 8 | S01-11, S01-13 | FR-14 |
| S06-02 | **Tab 15 — Customer Status Assignments** (PM/SA assignments, engineer list) | Streamlit | 8 | S01-06 | FR-15 |
| S06-03 | **Tab 16 — Project Runway** (burn rate, model est. completion, at-risk flags) | Streamlit | 12 | S04-01 | FR-16 |
| S06-04 | Data freshness timestamp in Streamlit sidebar (NFR-002) | Streamlit | 3 | — | NFR-002 |
| S06-05 | End-to-end smoke test: all 17 tabs, all KPI tiles, SPICE refresh validation | Testing | 12 | All tabs | — |
| S06-06 | Fix any issues found in smoke test | Bug Fix | 10 | S06-05 | — |
| S06-07 | Documentation update: README, deployment guide | Docs | 4 | — | — |

**Sprint total: 57 hrs**

---

## Timeline Summary

| # | Sprint | Dates | Goal |
|---|--------|-------|------|
| S1 | Sprint 1 | Jun 9 – Jun 20 | Foundation migrations + Tab 17 + Jira fix |
| S2 | Sprint 2 | Jun 23 – Jul 4 | Lambda enhancements + Tabs 1, 2 |
| S3 | Sprint 3 | Jul 7 – Jul 18 | Tabs 4, 5, 12 + MC Lambda |
| S4 | Sprint 4 | Jul 21 – Aug 1 | Tabs 6, 7, 13 + QS ML Insights |
| S5 | Sprint 5 | Aug 4 – Aug 15 | Tabs 3, 8, 9, 11 |
| S6 | Sprint 6 | Aug 18 – Aug 29 | Tabs 14, 15, 16 + polish + smoke test |

**Estimated completion: 2026-08-29** (6 sprints × 2 weeks)  
**Total stories: 46**  
**Total estimated hours: 331**

### Story count by type

| Type | Count |
|------|-------|
| Migration | 8 |
| View | 6 |
| Lambda | 6 |
| QuickSight | 9 |
| Streamlit | 15 |
| Testing/Docs | 2 |

---

## Blocked Stories (external dependencies)

| Story | Blocked By | Required Action |
|-------|-----------|-----------------|
| S01-02 | Human review | COO/ops lead must review + correct `practice_area` backfill for all active users |
| S02-04 | S01-02 gate | Cannot deploy until backfill validated — silently drops PS resources from forecast if deployed early |
| S01-03, S04-07, S05-01 | Business stakeholder | Must provide 4 rate values: onshore, offshore, contractor, billable ($/hr) |
| S03-04, S03-05, S03-06 | DevOps | Must add `CONFLUENCE_API_TOKEN` + `CONFLUENCE_BASE_URL` to Secrets Manager and Lambda env |

---

## Top 3 Risks to Timeline

| # | Risk | Impact | Mitigation |
|---|------|--------|-----------|
| R1 | `ps_profitability_rates` rate values not provided by stakeholder | Blocks Tab 3 (Sprint 5) and profitability settings editor (Sprint 4) | Parallelize: build Tab 3 UI with NULL-safe placeholders; activate when rates arrive |
| R2 | Confluence credentials not available | Blocks MC V2 audit Lambda + Tab 10 (Sprint 3) | Build Tab 10 UI without artifact column; add artifact section once credentials provided |
| R3 | `practice_area` backfill human review takes > 1 sprint | Delays Lambda 3.3d deployment; forecast accuracy degrades | `practice_alignment ILIKE` fallback stays in place until validated — no data loss, just technical debt |
