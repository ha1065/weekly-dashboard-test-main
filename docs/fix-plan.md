# Weekly Reporting — System Fix Plan

**Date:** 2026-06-23  
**Next Monday import:** 2026-06-29 9:00am CT  
**Total estimated effort:** ~14 hrs  
**Deploy tool:** `scripts/update_lambda_and_apply_views.sh` (Lambda), `scripts/apply_views_direct.py` (SQL)

---

## Block A — Before Monday 2026-06-29 (Critical Path)

These must be complete before the 9:00am CT import runs. Total: ~3.5 hrs.

- [ ] **A1 — Redeploy Lambda** · 15 min  
  `bash scripts/update_lambda_and_apply_views.sh`  
  Prerequisite for A2, A3, A4, A6.

- [ ] **A2 — Apply views to RDS** · 5 min  
  After A1: `aws lambda invoke --function-name production-clockify-import --payload '{"mode":"apply_views"}' /tmp/resp.json`  
  Pushes June 22 `create_views.sql` fixes live. Prerequisite for A4.

- [ ] **A3 — Fix pWeekStart parameter** · 20 min  
  1. In QuickSight console: rename parameter `pWeekEnd` → `pWeekStart` on `coo-operational-analysis-prod`  
  2. Set default to `2026-06-22`  
  3. Run `scripts/sync_coo_dashboard_iac.py` to regenerate `cloudformation/coo-dashboards.yaml`  
  4. In `src/lambda_handler.py` `update_analysis_week_parameter()`: change `pWeekEnd` → `pWeekStart`  
  5. Redeploy Lambda (A1 again with this change)

- [ ] **A4 — Fix PS Active Projects KPI gap** · 1-2 hrs  
  After A2: check if gap closes (`snapshot=24` vs live=19).  
  If gap persists: in `src/integrations/kpi_snapshot.py` `_compute_project_metrics()`, replace the inline `ps_project_status` query with:  
  ```sql
  SELECT COUNT(*) FROM vw_ps_project_status
  WHERE category = 'PS' AND status_category = 'In Progress'
  ```  
  Reseed: `aws lambda invoke --function-name production-clockify-import --payload '{"mode":"snapshot_kpis"}' /tmp/resp.json`  
  Verify tile = live view count.

- [ ] **A5 — Verify Bedrock + SES IAM permissions** · 15 min  
  In AWS console → IAM → Lambda execution role for `production-clockify-import`:  
  - Confirm `bedrock-runtime:InvokeModel` present  
  - Confirm `sesv2:SendEmail` present  
  If missing: add inline policy via console before Monday 9:30am CT.

- [ ] **A6 — Renumber duplicate migration files** · 30 min  
  9 collision groups: `002×2`, `004×2`, `053×2`, `059×3`, `060×3`, `061×2`, `062×2`, `065×2`  
  Rename each duplicate with `git mv` to next available number starting at 082.  
  Do NOT change SQL content. Commit.

- [ ] **A7 — Add schema_migrations tracking table** · 30 min  
  Create `src/database/migrations/083_schema_migrations_tracking.sql`:  
  ```sql
  CREATE TABLE IF NOT EXISTS schema_migrations (
      filename   TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```  
  Update `src/shared.py:apply_pending_migrations()`:  
  1. Bootstrap: create table if not exists  
  2. Skip filenames already in `schema_migrations`  
  3. Insert filename on successful apply  
  Apply: `aws lambda invoke --function-name production-clockify-import --payload '{"mode":"run_migration","sql":"CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"}' /tmp/resp.json`

---

## Block B — IaC Safety Fixes (This Week, Before Any Stack Update)

These fix the "stack update destroys production" risks. Template file changes only — do NOT run `update-stack` until all are done. Total: ~2.75 hrs.

| ID | Fix | File | Effort | Notes |
|----|-----|------|--------|-------|
| B1 | Fix Lambda `Code:` from ZipFile placeholder → S3-backed | `cloudformation/template.yaml` | 1 hr | Add `S3Bucket`/`S3Key` params; wires deploy script to CF |
| B2 | Add Bedrock + SES IAM to `LambdaExecutionRole` | `cloudformation/template.yaml` | 30 min | `bedrock-runtime:InvokeModel`, `sesv2:SendEmail` |
| B3 | Reconcile EventBridge rules — remove stale CF payloads or document as script-managed | `cloudformation/template.yaml` | 1 hr | Add `production-jira-daily-refresh`; align noon rule payload |
| B4 | Fix QuickSight SSL: `DisableSsl: true` → `false` | `cloudformation/coo-dashboards.yaml` | 15 min | Safe to apply immediately via `update-stack coo-dashboards-prod` |

- [ ] B1 complete
- [ ] B2 complete
- [ ] B3 complete
- [ ] B4 complete (apply: `aws cloudformation update-stack --stack-name coo-dashboards-prod ...`)

---

## Block C — Data Quality Fixes (This Week)

These fix the visible KPI inconsistencies. Total: ~3 hrs.

| ID | Fix | File | Effort | Depends |
|----|-----|------|--------|---------|
| C1 | Add `reporting_excluded` filter to billable hours + total_logged queries in `kpi_snapshot.py` | `src/integrations/kpi_snapshot.py` lines ~136-147, ~213 | 1 hr | Redeploy Lambda after |
| C2 | Fix `vw_ps_projects_at_risk` filter: health-only → any-dimension-at-risk | `src/database/create_views.sql` | 1 hr | Apply via `apply_views_direct.py` |
| C3 | Fix escalation column: normalize Jira free-text to `'Red'`/`'Green'` in view | `src/database/create_views.sql` `vw_ps_project_status` | 30 min | Apply via `apply_views_direct.py` |
| C4 | Add SPICE refresh to Jira daily rule payload | EventBridge console | 15 min | 5 Jira-sourced datasets: `ps-project-status-view`, `escalations-detail`, `mc-ticket-activity`, `mc-projects-at-risk`, `ps-projects-at-risk` |
| C5 | Add `refresh_quicksight` to Monday 9am rule | EventBridge console | 15 min | Use same COO dataset list as noon rule |

**C2 replacement WHERE clause:**
```sql
WHERE (
    health IN ('Red', 'Yellow')
    OR health_budget IN ('Red', 'Yellow')
    OR health_schedule IN ('Red', 'Yellow')
    OR budget_percent_used > 100
    OR (escalation IS NOT NULL AND UPPER(TRIM(escalation)) NOT IN ('NONE', 'GREEN', ''))
)
AND status_category != 'Done'
AND category = 'PS'
```

**C3 escalation fix (add to `vw_ps_project_status` SELECT):**
```sql
CASE
    WHEN COALESCE(TRIM(p.escalation), '') IN ('', 'None', 'No', 'N/A') THEN 'Green'
    ELSE 'Red'
END AS escalation
```

- [ ] C1 complete + Lambda redeployed
- [ ] C2 complete + views applied
- [ ] C3 complete + views applied
- [ ] C4 complete
- [ ] C5 complete

---

## Block D — Simplification (After Monday, Lower Urgency)

Schedule these once the Monday import cycle is stable. Total: ~4.75 hrs.

| ID | Fix | Effort | Notes |
|----|-----|--------|-------|
| D1 | Delete duplicate `run_migration` at line ~590 in `lambda_handler.py` | 5 min | Dead code; redeploy after |
| D2 | Delete stale repo artifacts | 10 min | 5 `.zip` files + 6 empty `--*` files; add `*.zip` to `.gitignore` |
| D3 | Archive stale scripts to `scripts/archive/` | 1 hr | `git mv` all `fix_*.py`, `diag_*.py`, `patch_*.py` pre-2026-05-01 |
| D4 | Drop 10 legacy scaffold views | 1 hr | Migration `084_drop_legacy_views.sql`; verify `quicksight-dashboards.yaml` stack unused first |
| D5 | Consolidate `vw_missing_time_submissions` → `vw_weekly_compliance_report` | 1 hr | Update 4 Lambda query sites; drop view; redeploy |
| D6 | Verify A3 sync: confirm `pWeekEnd` gone from `coo-dashboards.yaml` | 30 min | Auto-done after `sync_coo_dashboard_iac.py` runs in A3 |
| D7 | Verify + drop orphan views | 2 hrs | Check console for: `vw_practice_group_performance`, `vw_forecast_pivot`, `vw_forecast_summary`, `vw_forecast_summary_by_client`, `vw_non_billable_project_analysis`, `vw_escalations_by_customer`, `vw_project_directory`, `vw_customer_status_assignments`, `vw_mc_v2_audit_grid` |

- [ ] D1 complete
- [ ] D2 complete
- [ ] D3 complete
- [ ] D4 complete
- [ ] D5 complete
- [ ] D6 complete
- [ ] D7 complete

---

## Effort Summary

| Block | Focus | Estimated Hours |
|-------|-------|-----------------|
| A — Pre-Monday | Critical data + deploy fixes | 3.5 hrs |
| B — IaC safety | Template fixes before any stack update | 2.75 hrs |
| C — Data quality | KPI accuracy + dashboard correctness | 3 hrs |
| D — Simplification | Debt reduction, orphan cleanup | 4.75 hrs |
| **Total** | | **~14 hrs** |

---

## Do-Not-Break Checklist

Run after every Lambda deploy:

- [ ] Lambda version updated: `aws lambda get-function-configuration --function-name production-clockify-import --query 'LastModified'`
- [ ] `apply_views` mode works: invoke and check response for errors
- [ ] PS Active Projects KPI = live view count (run `scripts/diag_ps_count.py`)
- [ ] SPICE datasets healthy: `python scripts/check_spice_health.py`
- [ ] `pWeekStart` default = most recent Monday in QuickSight
- [ ] Compliance email still has SES permission (check IAM role)
- [ ] No new duplicate migration files: `ls src/database/migrations/ | cut -d_ -f1 | sort | uniq -d`

---

## Dependency Graph

```
A1 (redeploy)
 ├─ A2 (apply_views)
 │   └─ A4 (KPI gap fix)
 ├─ A3 (pWeekStart rename)
 │   └─ D6 (verify sync)
 ├─ C1 (excluded users)  → redeploy
 └─ D1 (dead code)       → redeploy

A6 (renumber migrations)
 └─ A7 (tracking table)

B1 + B2 + B3 (template fixes — all before any update-stack)
 └─ B4 (coo-dashboards SSL — safe to apply independently)

C2 + C3 (view fixes) → apply_views_direct.py
C4 + C5 (EventBridge) → console

D4 (drop legacy views) → verify quicksight-dashboards.yaml stack inactive first
D5 (consolidate compliance view) → update Lambda code + redeploy
```

---

## Block E — Streamlit Restructure (Strategic, Schedule After Block D)

**Guiding principle:** Streamlit owns the **write path**. QuickSight owns the **read path**. Every Streamlit feature decision should be filtered through this lens.

Streamlit's unique value is the 5-6 governance workflows that QuickSight cannot do:
- Toggling reporting exclusions (directly affects KPI accuracy)
- Uploading forecast templates
- Managing compliance report recipients
- Mapping Clockify → Jira project names
- Triggering imports and viewing import health
- User/access management

Everything else (utilization metrics, project health summaries, contractor breakdown, POD charts) duplicates QuickSight and should be removed or replaced with a link to the relevant QuickSight sheet.

### E1 — Fix hybrid navigation** · 30 min
- Delete or rename `src/pages/1_PS_Delivery.py`, `src/pages/resource_forecast.py`, `src/pages/resource_forecast_tab6.py` (prefix with `_` to hide from Streamlit auto-nav, or delete if content is absorbed)
- Removes the "two nav systems" confusion immediately

### E2 — Quick wins in app.py** · 2 hrs
- [ ] Wrap "Recent Time Entries" table in `st.expander("📋 Time Entry Detail", expanded=False)` — collapses by default so COO doesn't see 400 rows on load
- [ ] Move `_last_sync` data freshness from sidebar caption to inline `st.caption` above the Dashboard metric tiles
- [ ] Add WoW delta to PS/MC metric tiles (one extra prior-week query)
- [ ] Rename "Data Management" → "Operations" in sidebar radio
- [ ] Move Reporting Exclusions to top of Settings page + add `st.warning` if any users are excluded
- [ ] Collapse Resource Forecast to 3 tabs: `📤 Upload · 📊 View · 📋 History` — move Extensions/Run into `st.expander("⚙️ Advanced")`

### E3 — Reorganize to 4-page IA** · 4-6 hrs
Proposed structure replacing current 5-page radio + hybrid nav:

| Page | Content | Replaces |
|---|---|---|
| **Governance** | Compliance summary (who hasn't logged), utilization tiles with WoW delta, PS/MC health counts → link to QuickSight for detail | Dashboard (stripped of raw table + AI triggers) |
| **Forecast** | 3 tabs: Upload · View · History | Resource Forecast (8 tabs → 3) |
| **Project Config** | Project mapping table, Reporting Exclusions (with active-exclusion warning), Compliance recipients | Project Mapping + parts of Settings |
| **Admin** | Import controls + history, SPICE refresh, AI triggers, User management, DB stats, System config | Data Management + Settings |

### E4 — Audit and cut sprint plan tabs** · Planning only
Review `docs/implementation-plan.md` Sprint 4–9 tab backlog (17 tabs planned). For each tab ask: **does this add a write/config capability, or is it visualization?**

- Visualization tabs → cut or replace with a QuickSight link
- Write/config tabs → keep and build

Expected outcome: reduce from 17 planned tabs to 6-8 focused governance workflows.

### Effort Summary for Block E

| Item | Effort |
|---|---|
| E1 — Fix hybrid nav | 30 min |
| E2 — Quick wins | 2 hrs |
| E3 — IA reorganization | 4-6 hrs |
| E4 — Sprint plan audit | 1 hr (planning) |
| **Block E total** | **~8 hrs** |
