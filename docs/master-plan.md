# Weekly Reporting — Master Implementation Plan

**Version:** 2.0  
**Date:** 2026-06-23  
**Supersedes:** `docs/fix-plan.md`, `docs/implementation-plan.md`  
**Developer:** Solo · ~60 hrs/sprint · 2-week sprints  
**Next Monday import:** 2026-06-29 9:00am CT

---

## Guiding Principles

1. **Fix before build** — infrastructure and data quality issues are resolved before new feature work
2. **Streamlit owns the write path** — QuickSight owns the read path. Streamlit features that duplicate QuickSight visualization are cut.
3. **Every deploy is tested** — a verification checklist runs after every Lambda deploy and view change
4. **IaC must match live** — no resource exists outside CloudFormation without explicit documentation

---

## Phase Overview

| Phase | Focus | Sprints | Key Outcome |
|-------|-------|---------|-------------|
| 0 — Emergency | Critical fixes before Monday import | Done ✅ | System stable, KPIs accurate |
| 1 — Foundation | IaC safety + data quality + view cleanup | Done ✅ | No drift bombs, views consolidated |
| 2 — Streamlit UX | Quick wins + IA restructure + sprint plan audit | Done ✅ | Streamlit focused on write path |
| 3 — Data Layer | Lambda enhancements + forecast config + new views | S3 (Jun 25–Jul 11) | Forecast model complete, config in Streamlit |
| 4 — Feature Build | Resource Capacity tab + QS datasets | S4 (Jul 14–Jul 25) | Governance workflows live |
| 5 — Hardening | Testing, docs, operational runbooks | S5 (Jul 28–Aug 8) | Production-grade |

### Tab Scope (post S2-12 audit)

**Keep — write-path capabilities:**
| Tab | Where | Rationale |
|---|---|---|
| Resource Forecast | Streamlit (built) | Upload forecasts, view capacity model |
| Resource Capacity | Streamlit + QuickSight | QS: allocation heatmap · Streamlit: manual overrides |
| Project Time Detail | Streamlit | Raw drill-down not in COO dashboards |
| Customer Status Assignments | Streamlit | Assignment management |
| PS Profitability | Streamlit (blocked: rates) | Config + burn analysis |
| MC V2 Audit | Streamlit (blocked: Confluence) | Artifact verification |

**Cut — duplicates QuickSight:**
Tabs 1, 2, 4, 8, 9, 11, 12, 13, 16, 17 → handled by COO Operational Analysis sheets

---

## Phase 0 — Emergency Fixes (Before Monday 2026-06-29)

**Goal:** Monday 9am CT import runs against correct code and accurate views.  
**Effort:** ~3.5 hrs  
**Deploy:** `bash scripts/update_lambda_and_apply_views.sh` then `apply_views` invocation

### Checklist

- [ ] **P0-1 · Redeploy Lambda** (15 min) — `bash scripts/update_lambda_and_apply_views.sh`. Prerequisite for everything below.
- [ ] **P0-2 · Apply views to RDS** (5 min) — `aws lambda invoke --function-name production-clockify-import --payload '{"mode":"apply_views"}' /tmp/r.json`. Pushes June 22 `create_views.sql` fixes live.
- [ ] **P0-3 · Fix pWeekStart** (20 min) — In QuickSight console: rename `pWeekEnd` → `pWeekStart`, set default to `2026-06-22`. Run `scripts/sync_coo_dashboard_iac.py`. Update `update_analysis_week_parameter()` in `lambda_handler.py` → redeploy.
- [ ] **P0-4 · Fix PS Active Projects KPI gap** (1-2 hrs) — After P0-2: check if gap closes (snapshot=24 vs live=19). If not: rewrite `_compute_project_metrics()` in `kpi_snapshot.py` to `SELECT COUNT(*) FROM vw_ps_project_status WHERE category='PS' AND status_category='In Progress'`. Reseed: `{"mode":"snapshot_kpis"}`. Verify tile matches view.
- [ ] **P0-5 · Verify IAM permissions** (15 min) — Confirm `bedrock-runtime:InvokeModel` and `sesv2:SendEmail` on Lambda execution role before Monday 9:30am CT compliance email.

### Post-Deploy Verification (run after every Phase 0 deploy)

```bash
# 1. Lambda updated
aws lambda get-function-configuration --function-name production-clockify-import --query 'LastModified'

# 2. Views applied
aws lambda invoke --function-name production-clockify-import \
  --payload '{"mode":"run_query","sql":"SELECT COUNT(*) FROM vw_ps_project_status WHERE status_category=''In Progress''"}' /tmp/r.json && cat /tmp/r.json

# 3. KPI gap closed
python scripts/diag_ps_count.py

# 4. SPICE health
python scripts/check_spice_health.py

# 5. No duplicate migrations
ls src/database/migrations/ | cut -d_ -f1 | sort | uniq -d
```

---

## Sprint 1 — Infrastructure + Data Quality (Jun 23 – Jul 4)

**Goal:** IaC safety, migration stability, view consolidation, KPI accuracy  
**Capacity:** 60 hrs

### 1A — Migration Safety

| ID | Story | Type | Hrs | Depends |
|----|-------|------|-----|---------|
| S1-01 | Renumber 9 duplicate migration files (git mv, no SQL changes) — collision groups: 002×2, 004×2, 053×2, 059×3, 060×3, 061×2, 062×2, 065×2 → renumber to 082+ | Mig | 30m | — |
| S1-02 | Create `083_schema_migrations_tracking.sql`: `schema_migrations(filename TEXT PK, applied_at TIMESTAMPTZ)` table | Mig | 15m | S1-01 |
| S1-03 | Update `src/shared.py:apply_pending_migrations()` to skip already-applied filenames, insert on success | Code | 45m | S1-02 |

**Test:** Restart Streamlit ECS task, confirm no migration errors in logs, confirm all filenames appear in `schema_migrations` table.

### 1B — IaC Safety (template file changes only — do NOT run update-stack until all B items done)

| ID | Story | Type | Hrs | Notes |
|----|-------|------|-----|-------|
| S1-04 | Fix Lambda `Code:` in `template.yaml`: ZipFile placeholder → S3-backed `S3Bucket`/`S3Key` params | IaC | 1h | Eliminates "stack update destroys Lambda" bomb |
| S1-05 | Add Bedrock + SES IAM to `LambdaExecutionRole` in `template.yaml` | IaC | 30m | `bedrock-runtime:InvokeModel`, `sesv2:SendEmail` |
| S1-06 | Reconcile EventBridge rules in `template.yaml`: align noon payload, add `jira-daily-refresh`, or document as script-managed | IaC | 1h | Prevents accidental payload overwrite on stack update |
| S1-07 | Fix `DisableSsl: true` → `false` in `coo-dashboards.yaml`; apply to `coo-dashboards-prod` stack only | IaC | 15m | Safe isolated stack update |

**Test:** Run `aws cloudformation detect-stack-drift --stack-name weekly-reporting-production` after template updates. Confirm no unexpected drift beyond documented deviations.

### 1C — KPI Accuracy Fixes

| ID | Story | Type | Hrs | Depends |
|----|-------|------|-----|---------|
| S1-08 | Add `reporting_excluded` filter to billable hours + total_logged queries in `kpi_snapshot.py` (lines ~136-147, ~213) | Code | 1h | Redeploy after |
| S1-09 | Fix `vw_ps_projects_at_risk`: expand filter from health-only to any-dimension-at-risk (see WHERE clause below) | View | 1h | `apply_views_direct.py` |
| S1-10 | Fix escalation column in `vw_ps_project_status`: normalize free-text to `'Red'`/`'Green'` (see CASE below) | View | 30m | `apply_views_direct.py` |
| S1-11 | Add SPICE refresh to Jira daily EventBridge rule: add 5 Jira-sourced dataset IDs | Config | 15m | Console |
| S1-12 | Add `refresh_quicksight` to Monday 9am EventBridge rule | Config | 15m | Console |

**S1-09 WHERE clause:**
```sql
WHERE (
    health IN ('Red', 'Yellow')
    OR health_budget IN ('Red', 'Yellow')
    OR health_schedule IN ('Red', 'Yellow')
    OR budget_percent_used > 100
    OR (escalation IS NOT NULL AND UPPER(TRIM(escalation)) NOT IN ('NONE', 'GREEN', ''))
) AND status_category != 'Done' AND category = 'PS'
```

**S1-10 escalation CASE (replace `COALESCE(TRIM(p.escalation), 'None')`):**
```sql
CASE
    WHEN COALESCE(TRIM(p.escalation), '') IN ('', 'None', 'No', 'N/A') THEN 'Green'
    ELSE 'Red'
END AS escalation
```

**Test after S1-08 through S1-10:**
- Verify PS projects with budget > 100% appear in the at-risk table
- Verify escalation column shows color in QuickSight conditional formatting
- Verify excluded users' billable hours are removed from utilization KPIs: compare snapshot before/after for any excluded user

### 1D — View Cleanup

| ID | Story | Type | Hrs | Depends |
|----|-------|------|-----|---------|
| S1-13 | Delete dead code: duplicate `run_migration` at line ~590 of `lambda_handler.py` | Code | 5m | Redeploy |
| S1-14 | Delete stale repo artifacts: 5 zip files + 6 empty `--*` files; add `*.zip` to `.gitignore` | Cleanup | 10m | — |
| S1-15 | Archive stale scripts: `git mv` all `fix_*.py`, `diag_*.py`, `patch_*.py` pre-2026-05-01 to `scripts/archive/` | Cleanup | 1h | — |
| S1-16 | Create `084_drop_legacy_views.sql`: drop 10 original scaffold views (verify `quicksight-dashboards.yaml` stack inactive first) | View | 1h | Verify QS stack |
| S1-17 | Verify + drop orphan views: check QuickSight console for `vw_practice_group_performance`, `vw_forecast_pivot`, `vw_forecast_summary`, `vw_forecast_summary_by_client`, `vw_non_billable_project_analysis`, `vw_escalations_by_customer`, `vw_project_directory`, `vw_customer_status_assignments`, `vw_mc_v2_audit_grid` | View | 2h | — |
| S1-18 | Consolidate `vw_missing_time_submissions` → `vw_weekly_compliance_report`: update 4 Lambda query sites to `WHERE is_compliant = 0`, drop view | Code | 1h | Redeploy |

**Test for view drops:** After each drop migration, run `python scripts/check_all_spice.py` and `python scripts/dashboard_accuracy_audit.py` to confirm no QuickSight dataset references the dropped view.

**Sprint 1 total: ~13 hrs**

---

## Sprint 2 — Streamlit UX Restructure (Jul 7 – Jul 18)

**Goal:** Fix navigation, strip QuickSight duplicates, focus Streamlit on write path, audit feature backlog  
**Capacity:** 60 hrs

### 2A — Navigation Fix

| ID | Story | Type | Hrs | Notes |
|----|-------|------|-----|-------|
| S2-01 | Fix hybrid nav: rename `src/pages/1_PS_Delivery.py` → `src/pages/_1_PS_Delivery.py` and similarly for `resource_forecast.py`, `resource_forecast_tab6.py` to hide from Streamlit auto-nav | Code | 30m | Eliminates two-nav-system confusion |

### 2B — Quick Wins in app.py

| ID | Story | Type | Hrs | Notes |
|----|-------|------|-----|-------|
| S2-02 | Wrap "Recent Time Entries" in `st.expander(expanded=False)` | Code | 30m | |
| S2-03 | Move `_last_sync` data freshness inline above metric tiles; add WoW delta to PS/MC tiles | Code | 1h | One prior-week query added |
| S2-04 | Rename "Data Management" → "Operations" in sidebar radio | Code | 5m | |
| S2-05 | Promote Reporting Exclusions to top of Settings page; add `st.warning` if any users excluded | Code | 30m | |
| S2-06 | Collapse Resource Forecast to 3 tabs: `📤 Upload · 📊 View · 📋 History`; move Extensions/Run to `st.expander("⚙️ Advanced")` | Code | 1h | |

### 2C — IA Reorganization (4-page structure)

**Target structure:**

| Page | Content | Replaces |
|---|---|---|
| **Governance** | Compliance summary + utilization tiles (WoW delta) + PS/MC health counts → QuickSight links | Dashboard (stripped of raw table + AI triggers) |
| **Forecast** | Upload · View · History (3 tabs) | Resource Forecast |
| **Project Config** | Project mapping + Reporting Exclusions (with warning) + Compliance recipients | Project Mapping + parts of Settings |
| **Admin** | Import controls + history + SPICE refresh + AI triggers + User mgmt + DB stats + System config | Data Management + Settings |

| ID | Story | Type | Hrs | Notes |
|----|-------|------|-----|-------|
| S2-07 | Restructure sidebar radio to 4 pages: Governance, Forecast, Project Config, Admin | Code | 1h | |
| S2-08 | Move Reporting Exclusions + Compliance Recipients from Settings → Project Config page | Code | 1h | |
| S2-09 | Move import controls + AI triggers from Data Management → Admin page | Code | 1h | |
| S2-10 | Strip QuickSight-duplicate sections from Governance page; replace with `st.link_button` to relevant QS sheet URLs | Code | 2h | Remove: POD breakdown, Location breakdown, Contractor summary, AI analysis section |
| S2-11 | Add compliance "who hasn't logged this week" summary as first section on Governance page | Code | 2h | Query `vw_weekly_compliance_report WHERE is_compliant = 0` |

### 2D — Sprint Plan Audit

| ID | Story | Type | Hrs | Notes |
|----|-------|------|-----|-------|
| S2-12 | Audit Sprint 4–9 tab backlog (17 tabs) against write-path filter: visualization tabs → cut, write/config tabs → keep | Planning | 1h | Expected outcome: 17 → 6-8 tabs retained |

**Test for Sprint 2:**
- Navigate all 4 pages, confirm no broken imports or missing sections
- Confirm Reporting Exclusions warning fires when users are excluded
- Confirm Governance page loads without the stripped sections
- Confirm `scripts/check_spice_health.py` still passes (no Streamlit change affects SPICE)

**Sprint 2 total: ~12 hrs**

---

## Sprint 3 — Data Layer + Forecast Model (Jun 25 – Jul 11)

**Goal:** Forecast config in Streamlit, 3-signal weighted model live, Jira import fixed, new QS datasets  
**Capacity:** 60 hrs

### 3A — Forecast Config & Weights

| ID | Story | Type | Hrs | Notes |
|----|-------|------|-----|-------|
| S3-01 | Migration: Create `forecast_config` table with all weight keys and defaults | Migration | 1h | Fixes mismatch between `capacity_model_config` and `forecast_config` |
| S3-02 | Update `forecast_resources.py`: add `weight_pm_forecast` to 3-signal blend; add `seasonal_correction_enabled` guard | Lambda | 3h | Blend: `weight_hours × actuals + weight_jira × velocity + weight_pm × pm_forecast` |
| S3-03 | Streamlit Admin page: Forecast Config editor (sliders for 3 weights summing to 1.0, seasonal toggle, lookback selector) | Streamlit | 4h | Writes to `forecast_config` table |

**forecast_config keys:**

| Key | Default | Description |
|-----|---------|-------------|
| `weight_historical_hours` | 0.50 | Clockify actuals weight |
| `weight_jira_velocity` | 0.30 | Jira ticket burn rate weight |
| `weight_pm_forecast` | 0.20 | PM-uploaded forecast weight |
| `seasonal_correction_enabled` | 1 | 1=on, 0=off |
| `decay_start_weeks` | 2.0 | Weeks before completion when decay begins |
| `lookback_weeks_default` | 8 | Historical lookback window |
| `lookback_weeks_min_data` | 4 | Minimum lookback if data is sparse |

**Test:** Run `{"mode":"forecast_resources"}`, verify `ps_resource_forecast_v2` rows reflect the 3-signal blend. Change a weight in Streamlit, re-run, verify forecast hours change.

### 3B — Lambda + Jira Fixes

| ID | Story | Type | Hrs | Depends |
|----|-------|------|-----|---------|
| S3-04 | Fix Jira import upsert: `INSERT … ON CONFLICT (jira_issue_id) DO UPDATE` in `import_jira_data.py` | Lambda | 4h | Prevents duplicate ps_project_status rows |
| S3-05 | Migration: Add `practice_area` column to `clockify_users` + best-effort backfill | Migration | 2h | Enables practice-based filtering |
| S3-06 | **[HUMAN GATE]** Review + correct `practice_area` backfill for all active users | Manual | 2h | Must complete before S3-07 |
| S3-07 | Update `forecast_resources.py`: replace `practice_alignment ILIKE` with `practice_area IN ('PS','Both')` | Lambda | 1h | Depends S3-06 ✅ |

### 3C — New Views + QuickSight Datasets

| ID | Story | Type | Hrs | Notes |
|----|-------|------|-----|-------|
| S3-08 | Create `vw_time_compliance_history` view (weekly compliance % trend) | View | 3h | Feeds compliance history tab |
| S3-09 | Create `vw_utilization_history` view (weekly utilization % trend per employee) | View | 2h | Feeds utilization trend |
| S3-10 | Add `vw_resource_capacity_plan` as QS dataset `resource-capacity-plan` | QS | 2h | For QuickSight capacity heatmap |
| S3-11 | Register QS datasets: `time-compliance-history`, `utilization-history` | QS | 2h | Depends S3-08, S3-09 |

**Sprint 3 total: ~26 hrs**

---

## Sprint 4 — Feature Build (Jul 14 – Jul 25)

**Goal:** Resource Capacity tab, Project Time Detail tab, Customer Status Assignments tab  
**Capacity:** 60 hrs

| ID | Story | Type | Hrs | Depends |
|----|-------|------|-----|---------|
| S4-01 | **Resource Capacity tab** — manual override form for `ps_resource_forecast_v2` (set hours/allocation_pct per person/project/week) | Streamlit | 10h | S3-02 |
| S4-02 | **Project Time Detail tab** — filterable time entry drill-down (client, project, user, week) from `vw_project_time_detail` | Streamlit | 6h | — |
| S4-03 | **Customer Status Assignments tab** — PM/SA/engineer list per project from `vw_customer_status_assignments` | Streamlit | 6h | S3-04 |
| S4-04 | QuickSight: Resource Capacity heatmap sheet using `resource-capacity-plan` dataset | QS | 8h | S3-10 |
| S4-05 | QuickSight: compliance history + utilization history sheets | QS | 6h | S3-11 |

**Sprint 4 total: ~36 hrs**

---

## Sprint 5 — Hardening (Jul 28 – Aug 8)

**Goal:** End-to-end testing, runbooks, documentation  
(see Testing Plan section below — T-01 through T-10)

**Goal:** Lambda enhancements done; new views + QS datasets ready for feature build  
**Capacity:** 60 hrs

This sprint picks up the remaining items from the original Sprint 1–2 feature backlog that survived the audit.

| ID | Story | Type | Hrs | Depends | FR Ref |
|----|-------|------|-----|---------|--------|
| S3-01 | Migration: Add `practice_area` column to `clockify_users` + backfill | Mig | 4h | — | FR-CCR-001 |
| S3-02 | **[HUMAN GATE]** Review + correct `practice_area` backfill for all active users | Manual | 4h | S3-01 | FR-CCR-001 |
| S3-03 | `practice_area` editor in Admin page (was Settings) | Code | 6h | S3-01 | FR-CCR-001 |
| S3-04 | Lambda: `forecast_resources.py` — replace `practice_alignment ILIKE` with `practice_area IN ('PS','Both')` | Lambda | 2h | S3-02 ✅ | FR-CCR-007 |
| S3-05 | Lambda: `forecast_resources.py` — seasonal correction + dynamic lookback window | Lambda | 10h | — | FR-CCR-007 |
| S3-06 | Lambda: `forecast_resources.py` — PM forecast accuracy scoring → `ai_pm_forecast_accuracy` | Lambda | 6h | — | FR-CCR-007 |
| S3-07 | Fix Jira import upsert: `INSERT … ON CONFLICT` for `ps_project_status` | Lambda | 4h | — | FR-CCR-005 |
| S3-08 | Create `vw_time_compliance_history` view | View | 6h | S3-01 | FR-CCR-003 |
| S3-09 | Create `vw_utilization_history` view | View | 4h | S3-01 | FR-CCR-004 |
| S3-10 | Register QuickSight datasets: `time-compliance-history`, `utilization-history` | QS | 4h | S3-08, S3-09 | FR-05/13 |
| S3-11 | Confirm `vw_project_hours_summary` project-based classification (FR-CCR-008) | View | 4h | — | FR-CCR-008 |

**Test:** `python scripts/dashboard_accuracy_audit.py` after each Lambda deploy. Verify `practice_area` backfill output before S3-04 deploys.

**Sprint 3 total: 54 hrs**

---

## Sprint 4 — Governance Feature Build (Aug 4 – Aug 15)

**Goal:** Write-path Streamlit tabs live (post-audit list only)  
**Capacity:** 60 hrs

> ⚠️ Tab list is subject to S2-12 audit. Only tabs that add write/config capability are built. Visualization-only tabs are replaced with QuickSight links.

**Retained tabs (write-path confirmed):**

| ID | Story | Type | Hrs | Depends | FR Ref |
|----|-------|------|-----|---------|--------|
| S4-01 | **Governance: Weekly Operations Summary** (6 KPI tiles + drill-down table) | Code | 12h | S3-07 | FR-01 |
| S4-02 | **Governance: Missing Time Report** (non-compliant list + trend, exportable) | Code | 8h | S3-08 | FR-05 |
| S4-03 | **Forecast: Upload tab** (Excel template upload + validation feedback) | Code | 8h | — | FR-06 |
| S4-04 | **Forecast: View tab** (pivot table + list view, week range filter) | Code | 8h | — | FR-06 |
| S4-05 | **Project Config: PS Project Mapping** (mapping table with edit + unmapped warning) | Code | 8h | S3-07 | FR-02 |
| S4-06 | **Admin: Import controls + history** (Clockify + Jira triggers, status table) | Code | 8h | — | — |
| S4-07 | `ps_profitability_rates` editor in Admin page | Code | 6h | BLOCKED: rates | FR-CCR-002 |

**Test after each tab:**
- Tab loads with real data (not empty state)
- Write operations (form submits, file uploads) commit to DB and show confirmation
- No regression on existing navigation (run full nav smoke test)

**Sprint 4 total: ~58 hrs**

---

## Sprint 5 — Remaining Features + QuickSight (Aug 18 – Aug 29)

**Goal:** Remaining write-path tabs + QuickSight dataset updates  
**Capacity:** 60 hrs

| ID | Story | Type | Hrs | Depends | FR Ref |
|----|-------|------|-----|---------|--------|
| S5-01 | **Governance: Escalations** (open escalations list, priority breakdown) | Code | 8h | — | FR-12 |
| S5-02 | **Governance: Productive Utilization history** (trend by employee, exportable) | Code | 10h | S3-09 | FR-13 |
| S5-03 | **Admin: AI analysis triggers** (with last-run timestamp + expected runtime) | Code | 4h | — | FR-08 |
| S5-04 | **Tab 17 — Org KPI Scorecard** (QuickSight sheet: 4 QTD tiles + trend lines) | QS | 10h | — | FR-17 |
| S5-05 | QuickSight ML Insights on utilization % series | QS | 8h | S3-10 | FR-CCR-007 |
| S5-06 | Update `project-time-detail` QS dataset to expose `user_name` | QS | 2h | — | FR-CCR-006 |
| S5-07 | MC V2 Audit Lambda + Tab (BLOCKED on Confluence credentials) | Lambda/Code | 14h | BLOCKED | FR-10 |

**Sprint 5 total: ~56 hrs (42 hrs if S5-07 stays blocked)**

---

## Sprint 6 — Hardening + Testing (Sep 1 – Sep 12)

**Goal:** End-to-end testing, documentation, operational runbooks  
**Capacity:** 60 hrs

### Testing Plan

| ID | Test Type | Scope | Hrs | Pass Criteria |
|----|-----------|-------|-----|---------------|
| T-01 | **Import cycle integration test** | Trigger full Monday import sequence manually: `weekly` → `snapshot_kpis` → `refresh_quicksight`. Verify each stage completes and KPI tiles update. | 4h | All 10 COO datasets refresh; `ps_active_projects` matches `vw_ps_project_status` COUNT |
| T-02 | **KPI accuracy validation** | Compare `kpi_weekly_snapshots` values against direct DB queries for last 4 weeks. Check: billable_util_pct, ps_active_projects, mc_active_projects, time_compliance_pct, open_escalations | 3h | All values within 0.5% of direct query; no excluded users in billable hours |
| T-03 | **View consistency test** | For each QuickSight dataset, query its source view and compare row counts + key aggregates against what SPICE shows after refresh | 4h | Row count matches; no >1% variance on any KPI column |
| T-04 | **Streamlit write-path tests** | Exercise every write operation: reporting exclusion toggle, compliance recipient add/remove, project mapping edit, forecast upload, import trigger | 3h | All writes commit and reflect immediately on page reload |
| T-05 | **Migration idempotency test** | Restart Streamlit ECS task 3 times; confirm `schema_migrations` table prevents re-execution; confirm no errors in ECS logs | 1h | Zero migration errors in logs; `schema_migrations` row count stable |
| T-06 | **EventBridge rule validation** | Invoke each of the 5 EventBridge rules manually; verify correct Lambda mode fires and payload is correct | 2h | Each rule triggers expected Lambda mode; no stale CF payloads active |
| T-07 | **IaC drift check** | Run `detect-stack-drift` on all 4 stacks; document any remaining intentional drift | 2h | Zero unintentional drift; all drift documented |
| T-08 | **Compliance email test** | Trigger `send_compliance_report` Lambda manually; verify email arrives, contains correct non-compliant list, formatting correct | 1h | Email received; names match `vw_weekly_compliance_report WHERE is_compliant = 0` |
| T-09 | **pWeekStart parameter test** | Open COO dashboard; confirm KPI tiles show most recent Monday's data; confirm parameter picker works; confirm Monday noon import auto-updates the default | 1h | Default = most recent Monday; tiles update after `snapshot_kpis` runs |
| T-10 | **Full navigation smoke test** | Click through every page and tab in Streamlit; verify no broken queries, no 500 errors, no blank sections | 2h | All pages load with data; no unhandled exceptions in ECS logs |

**Sprint 6 stories:**

| ID | Story | Type | Hrs |
|----|-------|------|-----|
| S6-01 | Run T-01 through T-10 test suite | Testing | 23h |
| S6-02 | Fix issues found in testing | Bug Fix | 10h |
| S6-03 | Update `docs/project-context.md` to current state | Docs | 2h |
| S6-04 | Write operational runbook: Monday import failure recovery | Docs | 3h |
| S6-05 | Write operational runbook: SPICE refresh failure recovery | Docs | 2h |
| S6-06 | Write operational runbook: view deploy procedure | Docs | 2h |
| S6-07 | Final `sync_coo_dashboard_iac.py` run — freeze IaC snapshot | IaC | 30m |

**Sprint 6 total: ~43 hrs**

---

## Timeline Summary

| Sprint | Dates | Focus | Hrs |
|--------|-------|-------|-----|
| Phase 0 | Jun 23–27 | Emergency fixes | ~3.5 |
| Sprint 1 | Jun 23–Jul 4 | IaC + data quality + view cleanup | ~13 |
| Sprint 2 | Jul 7–Jul 18 | Streamlit UX restructure | ~12 |
| Sprint 3 | Jul 21–Aug 1 | Data layer + Lambda enhancements | ~54 |
| Sprint 4 | Aug 4–Aug 15 | Governance feature build | ~58 |
| Sprint 5 | Aug 18–Aug 29 | Remaining features + QuickSight | ~56 |
| Sprint 6 | Sep 1–Sep 12 | Testing + hardening + docs | ~43 |
| **Total** | | | **~240 hrs** |

**Estimated completion: 2026-09-12**

---

## Blocked Items (external dependencies)

| Item | Blocked By | Required Action |
|------|-----------|-----------------|
| `practice_area` backfill gate (S3-02) | Human review | COO/ops lead reviews + corrects backfill for all active users before S3-04 deploys |
| `ps_profitability_rates` (S4-07) | Business stakeholder | Must provide 4 rate values: onshore, offshore, contractor, billable ($/hr) |
| MC V2 Audit (S5-07) | DevOps | Add `CONFLUENCE_API_TOKEN` + `CONFLUENCE_BASE_URL` to Secrets Manager |

---

## Do-Not-Break Checklist (run after every Lambda deploy or view change)

```bash
# Lambda version updated
aws lambda get-function-configuration \
  --function-name production-clockify-import --query 'LastModified'

# Views applied cleanly
aws lambda invoke --function-name production-clockify-import \
  --payload '{"mode":"apply_views"}' /tmp/r.json && cat /tmp/r.json

# KPI counts sane
python scripts/diag_ps_count.py

# SPICE healthy
python scripts/check_spice_health.py

# No duplicate migrations
ls src/database/migrations/ | cut -d_ -f1 | sort | uniq -d

# pWeekStart default is last Monday
python scripts/dashboard_accuracy_audit.py
```

---

## Dependency Graph

```
Phase 0 (P0-1 → P0-2 → P0-4)
  └─ unblocks accurate KPIs for all subsequent work

S1-01 → S1-02 → S1-03 (migration safety — do first in Sprint 1)
S1-04 + S1-05 + S1-06 (IaC template — all before any update-stack)
  └─ S1-07 (SSL fix — safe to apply independently)
S1-08 → redeploy (excluded users in KPI)
S1-09 + S1-10 → apply_views_direct.py (view fixes)
S1-16 + S1-17 → verify QS console first (view drops)
S1-18 → redeploy (compliance view consolidation)

S2-01 through S2-11 (Streamlit — no Lambda dependency)
S2-12 (tab audit — gates Sprint 4 scope)

S3-01 → S3-02 [HUMAN GATE] → S3-04
S3-07 → S4-01, S4-05 (Jira upsert fix gates project status tabs)

S4-07 [BLOCKED: rates]
S5-07 [BLOCKED: Confluence]

Sprint 6 (testing) — gates on all Sprint 4+5 features complete
```
