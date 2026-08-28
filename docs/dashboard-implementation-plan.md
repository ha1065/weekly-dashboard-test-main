# COO Dashboard Implementation Plan
> Generated: 2026-05-12 | Based on dashboard review sessions 2026-05-08 to 2026-05-12

---

## Sprint 1 — Immediate Fixes (Blocking Current Use)

### S1-01a · Verify apply_views_direct.py succeeds
**What:** Confirm the duplicate removal and CASCADE fixes in `create_views.sql` work by running `apply_views_direct.py` successfully end-to-end.
**Affects:** All views
**Complexity:** S
**How:** `python3 scripts/apply_views_direct.py` — must show `✅ create_views.sql applied successfully`
**OKR:** KR5.1

### S1-01b · Deploy fixed create_views.sql to Lambda
**What:** Rebuild Lambda package with the corrected `create_views.sql` and redeploy. Only run after S1-01a confirms success.
**Affects:** All views — `apply_views` mode currently broken
**Complexity:** S
**How:** `AWS_PROFILE=... ./scripts/update_lambda_and_apply_views.sh`
**OKR:** KR5.1

### S1-02 · Republish COO dashboard from current analysis
**What:** Run `republish_from_analysis.py` to push all CF fixes (escalation colors, MC health CF, WoW KPIs) to the published dashboard.
**Affects:** `coo-operational-dashboard-prod` — currently on stale version
**Complexity:** S
**How:** `python3 scripts/republish_from_analysis.py`
**OKR:** KR2.1, KR2.4

### S1-03 · Fix pWeekEnd parameter default
**What:** Update the `pWeekEnd` parameter default in the analysis from the hardcoded `2026-04-26` to a rolling expression that always defaults to the last complete week.
**Affects:** All 5 sheets of COO Operational Analysis — all KPI tiles filter by this parameter
**Complexity:** S
**How:** Patch via script — update `ParameterDeclarations[0].DateTimeParameterDeclaration.DefaultValues` to use a rolling date expression
**OKR:** KR5.1

### S1-04 · Investigate PS Active Projects count gap (24 vs 19)
**What:** Determine why KPI snapshot shows 24 but live view shows 19. Check if projects changed status between snapshot time and now, or if the `issue_type='Emailed request'` filter needs adjustment for MC-type PS projects.
**Affects:** `kpi-weekly-snapshots-prod`, `kpi-ps-active` KPI tile on PS Delivery sheet
**Complexity:** S
**How:** Query `ps_project_status` for projects that were `In Progress + Emailed request` at snapshot time vs now
**OKR:** KR2.1

### S1-05 · Confirm MC Customer Health CF working
**What:** Verify `tbl-mc` health_overall cell colors (Red/Green) are visible after republish. If not, apply same fix as PS table (disable row alternate colors or use cell-level CF).
**Affects:** MC Service Delivery sheet, `tbl-mc` visual
**Complexity:** S
**OKR:** KR2.4

### S1-06 · Add vw_kpi_ytd to create_views.sql
**What:** Add the full `vw_kpi_ytd` definition (including _prev LAG columns from migration 060) to `create_views.sql` so `apply_views` always rebuilds it. Currently it only exists in migration files and is not rebuilt by `apply_views`.
**Affects:** `src/database/create_views.sql`, `src/database/migrations/060_kpi_ytd_prev_columns.sql`
**Complexity:** S
**OKR:** KR5.1 (operational stability — view must be rebuildable)

---

## Sprint 2 — COO Operational Improvements

### S2-01 · Escalation KPI WoW comparisons
**What:** Wire `escalations_prev` calculated field to `kpi-esc-total` and `kpi-esc-high` TargetValues so the Escalations sheet shows WoW delta.
**Affects:** Escalations sheet, `kpi_snapshots` dataset
**Complexity:** S
**How:** `fix_esc_wow_mc_cf.py` already written — run after S1-02
**OKR:** KR2.4

### S2-02 · Weekly Pulse — fix word cloud filter
**What:** The project word cloud (`wc-project-hours`) uses `project_hours_summary` dataset filtered by `pWeekEnd`. Verify it shows the correct week after S1-03 fix.
**Affects:** Weekly Pulse sheet
**Complexity:** S
**OKR:** KR5.1

### S2-03 · PS Delivery — add Amber/Yellow health color
**What:** The PS Project Health table and donut currently handle Green/Red but not Yellow (Amber). Add Yellow → `#FF9B00` CF rules to `tbl-ps-projects` and `donut-ps-health`.
**Affects:** PS Delivery sheet
**Complexity:** S
**OKR:** KR2.4

### S2-04 · Time & Utilization — add compliance trend chart
**What:** Add a line chart showing time compliance % trend over the last 8 weeks (from `kpi_snapshots`). Currently the sheet only shows the current week snapshot.
**Affects:** Time & Utilization sheet, `kpi_snapshots` dataset
**Complexity:** M
**OKR:** KR5.1

### S2-05 · COO Operational — sync IaC after all fixes
**What:** After all Sprint 1+2 fixes are applied, run `export_live_analysis.py` + `sync_coo_dashboard_iac.py` + commit to git.
**Affects:** `cloudformation/coo-dashboards.yaml`
**Complexity:** S
**OKR:** KR5.1 (governance)

### S2-06 · Verify PS Delivery avg duration KPI target value
**What:** The `kpi-ps-duration` tile uses `target_ps_avg_duration_weeks` as its target. The Q4 target is 5 weeks but the Q2 target is 10 weeks. Verify the target column in `kpi_snapshots` reflects the current quarter target, not the year-end target. Update `kpi_snapshot.py` target values if needed.
**Affects:** PS Delivery sheet, `kpi_snapshots` table, `kpi_snapshot.py`
**Complexity:** S
**OKR:** KR2.2

---

## Sprint 3 — Executive Summary Redesign

### S3-00 · Confirm QuickSight PDF export capability
**What:** Verify the QuickSight subscription tier supports PDF export before designing the Executive Summary layout. If PDF export is needed, the layout must use fixed canvas size (not responsive). If not available, design for screen-only.
**Affects:** Executive Summary design decisions
**Complexity:** S
**OKR:** KR5.1

### S3-01 · Define Executive Summary sheet structure
**What:** Single sheet, 6-8 visuals max, no filters, no tables. Layout:
- Row 1: 6 KPI tiles — Billable Util %, Time Compliance %, Open Escalations, PS On-Time Rate, Projects in Red, Active Headcount
- Row 2: Utilization trend line (YTD, 3 series: billable/productive/compliance with reference lines)
- Row 3: Health distribution donut (PS + MC combined) + Escalations by customer bar
**Affects:** `coo-executive-analysis-prod` (currently has `sheet-executive` with basic visuals)
**Complexity:** M
**OKR:** KR2.1, KR2.4, KR5.1

### S3-02 · Executive Summary — OKR progress KPIs
**What:** Add KPI tiles showing YTD progress vs Q2 targets for KR2.1 (on-time rate target 60%) and KR2.4 (Red projects target <20%).
**Affects:** Executive Summary sheet, `kpi_snapshots` dataset
**Complexity:** M
**How:** Add `target_ps_on_time_pct` and `total_projects_red` KPIs with target comparison
**OKR:** KR2.1, KR2.4

### S3-03 · Executive Summary — publish and share
**What:** Publish the redesigned Executive Summary as a dashboard and configure sharing for CEO/COO access.
**Affects:** `coo-executive-dashboard-prod`
**Complexity:** S
**OKR:** KR5.1

---

## Sprint 4 — Weekly Reporting Governance Layer

### S4-01 · Individual compliance tracking sheet
**What:** New QuickSight dataset from existing `vw_time_submission_weekly` (already has per-person per-week data — no new view needed). New sheet showing: name, pod, last 4 weeks compliance (green/red cells), rolling compliance %, trend arrow.
**Affects:** New dataset `time-compliance-history` from `vw_time_submission_weekly`, new sheet
**Complexity:** M
**OKR:** KR5.1

### S4-03 · PM on-time delivery analysis
**What:** Create `vw_pm_delivery_performance` — per PM: active projects, % on time, avg duration, projects in Red. Source: `vw_ps_project_status`.
**Affects:** New dataset `pm-delivery-performance`, new sheet
**Complexity:** M
**OKR:** KR2.1, KR2.2

### S4-04 · Project Jira analysis sheet
**What:** New sheet showing per-project: stage, health trend (last 4 weeks), budget burn %, days to completion, last week hours. Source: `vw_ps_project_status` + `kpi_snapshots`.
**Affects:** New sheet in COO Operational (or Weekly Reporting dashboard)
**Complexity:** M
**OKR:** KR2.1, KR2.4

### S4-05 · Retire Streamlit Dashboard and Resource Directory pages
**What:** Remove or hide the Dashboard and Resource Directory pages from the Streamlit app. Replace with links to the relevant QuickSight dashboards. Keep: Forecasting, Data Management, Project Mapping, Clockify Data Update.
**Affects:** `src/app.py`
**Complexity:** S
**OKR:** KR5.1 (single source of truth)

---

## Sprint 5 — Data Quality and Automation

### S5-01 · Fix apply_views Lambda mode permanently
**What:** Refactor `apply_database_views()` in `lambda_handler.py` to run a pre-drop phase (drop all dependent views with CASCADE) then execute the full `create_views.sql` file. Do NOT split on `;\n` — this breaks CTEs and multi-statement blocks.
**Affects:** `src/lambda_handler.py`
**Complexity:** M
**OKR:** KR5.1

### S5-02 · ~~Add vw_kpi_ytd to apply_views pipeline~~ (moved to S1-06)

### S5-03 · Automate weekly KPI snapshot
**What:** The noon Monday import now chains to `snapshot_kpis`. Verify this is working end-to-end by checking `kpi_weekly_snapshots` table after next Monday's noon import.
**Affects:** EventBridge rule `production-weekly-import-noon-ct`, Lambda handler
**Complexity:** S (verification only)
**OKR:** KR5.1

### S5-04 · SPICE refresh monitoring
**What:** Add a weekly check (via Lambda or CloudWatch) that alerts if any COO dashboard dataset has a FAILED ingestion. Currently failures are only discovered manually.
**Affects:** New Lambda function or CloudWatch alarm
**Complexity:** M
**OKR:** KR5.1

### S5-05 · KR5.4 — Offshore talent tracking
**What:** Add a KPI to the COO Operational dashboard tracking % of offshore resources in strategic roles (PM, SA, practice lead). Requires a `strategic_role` flag on `clockify_users` or a mapping table.
**Affects:** `clockify_users` table, `kpi_snapshot.py`, `kpi_snapshots` table, Weekly Pulse sheet
**Complexity:** L (requires data definition with COO)
**OKR:** KR5.4

### S5-06 · KR3.4 — Expansion signals tracking
**What:** Add expansion signal logging to the system. Requires defining what constitutes an expansion signal (upsell opportunity logged in HubSpot or Jira) and building a data pipeline.
**Affects:** New data source integration, new KPI
**Complexity:** L (requires external system integration)
**OKR:** KR3.4

---

## Out of Scope

### KR2.3 — Kiro Adoption Tracking
KR2.3 (90% of engagements launched with Kiro steering file) requires Kiro usage data that is not available in the Clockify/Jira pipeline. This dashboard system cannot measure KR2.3 without a separate Kiro adoption data source. Explicitly excluded from this plan.

---

## Priority Matrix

| Sprint | Item | Priority | Effort | Impact |
|--------|------|----------|--------|--------|
| 1 | S1-01a Verify apply_views_direct | P0 | S | Confirms SQL fix |
| 1 | S1-01b Deploy Lambda fix | P0 | S | Unblocks apply_views |
| 1 | S1-02 Republish dashboard | P0 | S | Fixes all visual issues |
| 1 | S1-03 Fix pWeekEnd default | P0 | S | Data accuracy |
| 1 | S1-04 PS count gap | P1 | S | Data accuracy |
| 1 | S1-05 MC CF confirm | P1 | S | Visual quality |
| 1 | S1-06 vw_kpi_ytd in create_views | P1 | S | Operational stability |
| 2 | S2-01 Escalation WoW | P1 | S | KR2.4 visibility |
| 2 | S2-03 Amber health color | P1 | S | Visual completeness |
| 2 | S2-06 Avg duration target | P1 | S | KR2.2 accuracy |
| 2 | S2-04 Compliance trend | P2 | M | KR5.1 |
| 3 | S3-00 PDF export check | P1 | S | Design prerequisite |
| 3 | S3-01 Exec Summary | P1 | M | CEO/COO audience |
| 3 | S3-02 OKR progress KPIs | P1 | M | KR2.1/KR2.4 |
| 4 | S4-01 Compliance tracking | P2 | M | KR5.1 governance |
| 4 | S4-02 PM delivery analysis | P2 | M | KR2.1 |
| 4 | S4-05 Retire Streamlit pages | P2 | S | Simplification |
| 5 | S5-01 Fix apply_views properly | P1 | M | Operational stability |
| 5 | S5-04 SPICE monitoring | P2 | M | Reliability |
| 5 | S5-05 KR5.4 offshore tracking | P3 | L | OKR measurement |
| 5 | S5-06 KR3.4 expansion signals | P3 | L | OKR measurement |

---

## Architect Review Notes
> Reviewed: 2026-05-12 | Verdict: **Approved with changes** (changes applied above)
> - S1-01 split into verify + deploy steps
> - S5-02 moved to S1-06 (dependency ordering)
> - S5-01 approach corrected (pre-drop phase, not statement splitting)
> - S2-06 added for KR2.2 target accuracy
> - S3-00 added as design prerequisite
> - S4-01/S4-02 merged (vw_time_submission_weekly already exists)
> - KR2.3 explicitly noted as out of scope
