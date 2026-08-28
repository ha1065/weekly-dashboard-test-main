# KPI Tracking Dashboard — Solution Proposal

**Date:** 2026-07-01
**Requested by:** Cloudelligent Leadership
**Project:** weekly-reporting (internal COO reporting platform)
**Status:** Draft — Pending Stakeholder Review

---

## Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v1.0 | 2026-07-01 | Product Analyst | Initial proposal |

---

## 1. Problem Statement

### Current Situation

Cloudelligent has a COO Operational Dashboard in QuickSight with an "Org KPI Scorecard" sheet showing four company-level KPI tiles: On-Time Delivery, Timesheet Compliance, Utilization, and Open Escalations. These tiles show a single week's snapshot at a time and are primarily designed for the COO's weekly operational meeting.

**What is missing:**

- No time-aggregated view: leaders cannot see QTD or YTD KPI progress against annual OKR targets
- No practice-level breakdown: PS, MC, and MIT each have different KPI targets, but there is no dedicated view per practice
- No team/POD-level view: staff cannot see how their POD is tracking
- No OKR progress visualization: the 2026 quarterly targets (e.g., KR2.1 on-time delivery 30% → 90% by Q4) are not visible anywhere in the dashboards
- No self-service access: staff members have no place to check their own practice's health — the COO dashboard is leadership-only in practice

### Who Is Affected

| User | Current Pain |
|------|-------------|
| COO / Executives | Must manually calculate QTD/YTD aggregates from weekly tiles; no OKR progress bar |
| Practice Leads (PS, MC, MIT) | No dedicated view of their practice KPIs; must read the full COO dashboard |
| Staff / Team Members | No visibility into how their practice or POD is performing vs. targets |

### Business Impact

The 2026 COO OKRs (KR5.1) explicitly require "real-time CEO/COO decision visibility" and "95%+ data hygiene." A KPI dashboard that shows weekly, monthly, quarterly, and annual progress against targets directly measures and supports KR5.1 delivery.

---

## 2. User Personas & Needs

### Persona 1: COO / Executive

**Goal:** Understand at a glance whether the company is on track for its 2026 OKR commitments — without pulling data manually.

**Needs:**
- Company-level KPI scorecard showing current value vs. OKR quarterly target, with a trend line showing progress week over week
- One visual per major KR: on-time delivery, utilization, compliance, escalations, avg engagement duration
- Ability to switch between week / month / QTD / YTD aggregation
- Red/Amber/Green status indicators anchored to OKR quarterly targets (not just arbitrary thresholds)
- A single view that can be shared or shown on a screen during exec meetings

**Does not need:** Individual staff-level drill-downs or POD-level detail.

### Persona 2: Practice Lead (PS, MC, MIT)

**Goal:** Monitor their practice's KPIs independently and take corrective action when their practice is falling behind target.

**Needs:**
- A practice-filtered view (e.g., "Show me only PS metrics") with the same KPI set as the company view
- Comparison of their practice's performance vs. the company average and vs. their practice-specific targets
- Project health summary for their practice (Green/Amber/Red count, on-time %)
- Compliance and utilization for staff in their practice
- Week/month/QTD time grain selection

**Does not need:** Other practices' detailed project lists.

### Persona 3: Staff / Team Member

**Goal:** See how their practice and POD are performing so they can understand context for their own work.

**Needs:**
- A simple, read-only view: "How is my practice doing this week/month vs. target?"
- POD-level utilization and compliance summary (are we logging time correctly?)
- Their practice's on-time delivery rate vs. target
- No individual-level data on other people — aggregate only

**Does not need:** Financial metrics, executive OKR detail, or project management controls.

---

## 3. Proposed KPIs to Track

All KPIs below are sourced from the 2026 COO OKRs and the existing `kpi_weekly_snapshots` table. Each entry includes availability status — **Available Now** means the column already exists in `kpi_weekly_snapshots`; **Gap** means new data work is required.

### 3.1 Company-Level KPIs

| KPI | Description | Time Grain | OKR Target (Q4) | Data Source | Status |
|-----|-------------|-----------|-----------------|-------------|--------|
| Billable Utilization % | Billable hours ÷ total available capacity | Week, Month, QTD, YTD | 75% (default target in table) | `kpi_weekly_snapshots.billable_util_pct` | ✅ Available |
| Productive Utilization % | (Billable + presales + productive NB) ÷ capacity | Week, Month, QTD, YTD | 80% | `kpi_weekly_snapshots.productive_util_pct` | ✅ Available |
| Timesheet Compliance % | Staff who logged ≥ weekly capacity hours | Week, Month, QTD, YTD | 95% (KR5.1) | `kpi_weekly_snapshots.time_compliance_pct` | ✅ Available |
| On-Time Delivery Rate | % of projects delivered on/ahead of schedule | Week, QTD, YTD | 90% by Q4 (KR2.1) | `kpi_weekly_snapshots.ps_on_time_pct` + `mc_on_time_pct` (combined) | ✅ Available |
| Avg Engagement Duration | Average weeks from kickoff to completion | QTD, YTD | 5 weeks by Q4 (KR2.2) | `kpi_weekly_snapshots.ps_avg_duration_weeks` | ✅ Available (PS only) |
| Open Escalations | Count of open escalation tickets | Week | 0 (implied) | `kpi_weekly_snapshots.open_escalations` | ✅ Available |
| Projects in Red | Count + % of active projects with Red health | Week, QTD | < 10% (KR2.4) | `kpi_weekly_snapshots.total_projects_red` / total | ✅ Available |
| Active Resource Count | Headcount of active billable staff | Week | N/A (context metric) | `kpi_weekly_snapshots.active_resource_count` | ✅ Available |

### 3.2 Practice-Level KPIs

Each of these exists today for PS and MC separately in `kpi_weekly_snapshots`. MIT is a **data gap** (see §6).

| KPI | PS Column | MC Column | MIT Column | OKR Link |
|-----|-----------|-----------|------------|----------|
| Billable Hours (week) | `ps_billable_hours` | `mc_billable_hours` | ⚠️ Gap | KR5.1 |
| On-Time Delivery % | `ps_on_time_pct` | `mc_on_time_pct` | ⚠️ Gap | KR2.1 |
| Active Projects | `ps_active_projects` | `mc_active_projects` | ⚠️ Gap | Context |
| Projects Green/Amber/Red | `ps_projects_green/amber/red` | `mc_projects_green/amber/red` | ⚠️ Gap | KR2.4 |
| Avg Duration (weeks) | `ps_avg_duration_weeks` | `mc_avg_duration_weeks` | ⚠️ Gap | KR2.2 |
| Hours YTD | `ps_actual_hours_ytd` | `mc_actual_hours_ytd` | ⚠️ Gap | Context |
| Utilization % (practice-level) | ⚠️ Gap — requires per-practice capacity | ⚠️ Gap | ⚠️ Gap | KR5.1 |
| Compliance % (practice-level) | ⚠️ Gap — requires per-practice filter on `clockify_users.practice_area` | ⚠️ Gap | ⚠️ Gap | KR5.1 |

### 3.3 Team / POD-Level KPIs

POD assignments are stored in `clockify_users.pod_assignment` (values: Alpha, Bravo, Charlie, A2Z, Free Agent). These are not currently rolled up in `kpi_weekly_snapshots`.

| KPI | Description | Time Grain | Data Source | Status |
|-----|-------------|-----------|-------------|--------|
| POD Billable Hours | Total billable hours per POD per week | Week, Month | `vw_project_hours_summary.pod_assignment` + time entries | ✅ Computable from existing views |
| POD Compliance % | % of POD members who logged ≥ capacity | Week, Month | `clockify_users.pod_assignment` + compliance logic | ⚠️ Gap — no view today |
| POD Utilization % | Billable hours ÷ POD capacity | Week, Month | Requires POD-level capacity rollup | ⚠️ Gap |
| POD Headcount | Active staff per POD | Week | `clockify_users.pod_assignment` | ✅ Computable |

> **Note on OKR KRs not addressable with current data:** KR2.3 (Kiro adoption %), KR5.2 (AI certification %), KR5.3 (org redesign), KR5.4 (offshore talent elevation), KR3.4 (expansion signals), KR6.1/6.2/6.4 (product revenue) — none of these have data in this pipeline. They require external data sources (Kiro usage logs, LMS, HubSpot, finance system). These are **out of scope** for this dashboard proposal.

---

## 4. Proposed Dashboard Structure

### 4.1 Time Filter Approach

A single **date range parameter** with preset buttons: **This Week | This Month | This Quarter (QTD) | This Year (YTD)**. The underlying logic aggregates `kpi_weekly_snapshots` rows within the selected range:

- **Week:** single row = most recent complete week
- **Month:** average or sum of weekly rows in the calendar month
- **QTD:** average or sum of weeks since the start of the current quarter
- **YTD:** average or sum of all 2026 weeks to date

Aggregation method per KPI: percentages (utilization, compliance, on-time) use **average of weekly values**; counts (hours, projects, escalations) use **sum** for period totals or **latest value** for point-in-time counts.

### 4.2 Breakdown Dimensions

| Filter | Values | Implementation |
|--------|--------|----------------|
| Practice | All / PS / MC / MIT | Parameter driving dataset filter on `practice_area` |
| Team / POD | All / Alpha / Bravo / Charlie / A2Z / Free Agent | Parameter driving filter on `pod_assignment` |
| Time grain | Week / Month / QTD / YTD | Parameter with preset buttons |

### 4.3 Sheet / Tab Layout

The dashboard is organized into **three sheets** to serve the three personas cleanly:

---

**Sheet 1 — Company OKR Scorecard** *(audience: COO, executives)*

Purpose: Single-screen view of company KPI health vs. 2026 OKR quarterly targets.

| Zone | Content | Visual Type |
|------|---------|-------------|
| Top strip | 6 KPI tiles: Billable Util %, Compliance %, On-Time Delivery %, Avg Duration (weeks), Open Escalations, Projects in Red % | KPI tiles with vs-target delta and RAG indicator |
| Middle left | Billable utilization trend vs. target line — full year | Line chart (actual=blue, target=dashed grey) |
| Middle center | On-time delivery rate — quarterly target steps overlaid | Line chart with step-function target bands |
| Middle right | Compliance % trend | Line chart |
| Bottom | Project health distribution (Green/Amber/Red) by week | Stacked bar chart |

Time grain selector: Week / Month / QTD / YTD (top-right corner).

---

**Sheet 2 — Practice Scorecard** *(audience: Practice Leads)*

Purpose: Practice-filtered KPI view. Default filter = All; Practice Lead selects their practice.

| Zone | Content | Visual Type |
|------|---------|-------------|
| Top strip | 5 KPI tiles: Billable Hours, Billable Util %, Compliance %, On-Time %, Active Projects | KPI tiles filtered to selected practice |
| Middle left | Practice billable hours trend (PS=blue, MC=orange, MIT=grey) | Line chart |
| Middle right | On-time delivery % vs. target for selected practice | Line chart with target line |
| Bottom left | Project health donut (Green/Amber/Red) for selected practice | Donut chart |
| Bottom right | Avg engagement duration trend vs. target (5-week Q4 target) | Line chart with target reference line |

Practice filter: All / PS / MC / MIT (top-left parameter control).

---

**Sheet 3 — Team / POD View** *(audience: Staff, Team Members)*

Purpose: POD-level utilization and compliance — simple and self-serve.

| Zone | Content | Visual Type |
|------|---------|-------------|
| Top strip | 3 KPI tiles: POD Billable Hours, POD Compliance %, POD Headcount | KPI tiles |
| Middle | Compliance % by POD (current week) — horizontal bar, target line at 95% | Horizontal bar chart |
| Bottom | Weekly billable hours by POD over last 12 weeks | Grouped bar or line chart |

POD filter: All / Alpha / Bravo / Charlie / A2Z / Free Agent.

> **Note:** Individual staff data is not shown on Sheet 3 — aggregates only. Staff-level compliance detail remains in the COO Operational Dashboard.

---

## 5. Build Options

### Option A — Extend the Existing COO Operational Dashboard

Add 3 new sheets to the existing `coo-operational-analysis-prod` analysis and republish the `coo-operational-dashboard-prod` dashboard.

**Pros:**
- Zero new infrastructure — uses existing SPICE datasets (`kpi-weekly-snapshots-prod`, `category-hours-summary-prod`, `project-hours-summary-prod`)
- Single dashboard URL for all users — no new sharing/permissions setup needed
- Consistent branding — same CE MIDNIGHT theme already applied
- Faster to build — existing datasets cover ~80% of required KPIs
- Easier to maintain — one IaC file (`coo-dashboards.yaml`)

**Cons:**
- The COO Operational Dashboard currently has 5 sheets and is a leadership tool. Adding staff-facing sheets (Sheet 3 — POD View) to it may feel inappropriate for staff access
- Dashboard already has known accuracy issues (C3, C4 from the technical findings report) — adding sheets before those are fixed risks embedding the same bugs in the new sheets
- QuickSight dashboard sharing is all-or-nothing per dashboard unless row-level security is configured — the COO's detailed project tables would be visible to all staff

**Effort estimate:** Medium (see §7)

---

### Option B — Build a New Standalone KPI Dashboard

Create a new QuickSight analysis and dashboard (`kpi-tracking-prod`) sharing the same SPICE datasets via dataset references.

**Pros:**
- Clean separation of concerns — the KPI dashboard is purpose-built for OKR tracking, not operational management
- Can be shared broadly with all staff without exposing COO operational detail (project PM assignments, individual compliance tables, etc.)
- Easier to evolve independently — changes to the KPI dashboard don't risk breaking the COO Operational Dashboard
- Better UX for staff — a focused, simplified dashboard vs. navigating an 8-sheet operational tool

**Cons:**
- Requires a new CloudFormation resource block in `coo-dashboards.yaml` (or a new template file) — additional IaC maintenance
- Slightly more setup time — new analysis, new dashboard, new sharing configuration
- SPICE datasets are already defined and shared; no new datasets needed for the company and practice KPIs

**Effort estimate:** Medium-High (see §7), ~4–6 hours more than Option A

---

### Recommendation: Option B (New Standalone Dashboard)

**Rationale:**

The request is explicitly for leaders *and staff* to see OKR tracking — a broader audience than the current COO dashboard serves. The COO Operational Dashboard contains individual staff compliance data, detailed project tables, and PM/SA assignments that should not be broadly visible. A standalone dashboard can be shared with the entire Cloudelligent organization without exposing that detail.

Additionally, the COO dashboard has active known accuracy issues (stale parameter default, PS project count gap). A new dashboard built against the same `kpi_weekly_snapshots` data source but with clean, purpose-built visuals avoids inheriting those issues.

The incremental effort for a standalone build is ~4–6 hours and is the right investment for a dashboard intended to be the company's OKR visibility tool throughout 2026.

> **Hybrid path available:** If speed is the priority, start with Option A (add sheets to the COO dashboard, restrict to leadership). Promote to Option B (standalone dashboard, staff-accessible) in a follow-up sprint once the data gaps in §6 are resolved. The visuals built for Option A can be copied to the new analysis.

---

## 6. Data Gaps

### What Exists Today

The following KPIs can be built immediately with no new data work:

| KPI | Source | Notes |
|-----|--------|-------|
| Company billable utilization %, compliance %, productive util % | `kpi_weekly_snapshots` | All columns present |
| PS and MC on-time delivery %, avg duration, active projects, health counts | `kpi_weekly_snapshots` | PS and MC columns present |
| Company-level escalation counts | `kpi_weekly_snapshots` | Present |
| Practice-level billable hours (PS and MC) | `kpi_weekly_snapshots` | `ps_billable_hours`, `mc_billable_hours` |
| POD-level billable hours (week) | `vw_project_hours_summary.pod_assignment` | Existing view, needs a SPICE dataset |
| Practice-level time trend (12 weeks) | `vw_category_hours_summary` | Existing view and SPICE dataset |

### Gaps — New Data Work Required

| Gap | What's Missing | Required Work | Effort |
|-----|---------------|---------------|--------|
| **MIT practice metrics** | `kpi_weekly_snapshots` has no `mit_*` columns. The `ps_project_status` and `escalations` tables don't classify MIT separately — MIT is currently treated as Internal in Clockify time entries. | (1) Confirm with stakeholders whether MIT projects exist in Jira/Clockify today. (2) If yes: add `mit_*` columns to `kpi_weekly_snapshots` and extend `kpi_snapshot.py` to compute them. | 1–2 days |
| **Practice-level utilization %** | `kpi_weekly_snapshots` stores company-level utilization only. Practice-level utilization requires capacity rollup per `clockify_users.practice_area`. | Add a new PostgreSQL view `vw_practice_kpi_weekly` that computes utilization and compliance per `practice_area` per week. Add a SPICE dataset for it. | 0.5–1 day |
| **Practice-level compliance %** | Same as above — compliance requires knowing which users belong to each practice and whether they met their weekly hours. | Included in `vw_practice_kpi_weekly` above. Depends on `clockify_users.practice_area` being populated correctly (migration 066 backfill should be verified). | Included above |
| **POD-level compliance % and utilization %** | No view today aggregates compliance or utilization by `pod_assignment`. | New view `vw_pod_kpi_weekly` joining `clockify_users.pod_assignment` with compliance and hours logic. | 0.5 day |
| **OKR quarterly target steps** | QuickSight needs a reference dataset to show "Q1 target: 45%, Q2 target: 60%" etc. as a step-function overlay on trend lines. | Create a small static PostgreSQL table `okr_quarterly_targets` (or a hardcoded reference dataset in QuickSight calculated fields) seeded with the 2026 KR targets per quarter. | 2–4 hours |
| **MC avg engagement duration** | `kpi_weekly_snapshots.mc_avg_duration_weeks` column exists in the table schema but may not be computed by `kpi_snapshot.py` (it was added later and the snapshot logic targets PS). | Verify `kpi_snapshot.py` populates `mc_avg_duration_weeks`. If not, add the computation. | 1–2 hours |

### Summary: Data Readiness by Sheet

| Sheet | Ready Now? | Blocking Gaps |
|-------|-----------|---------------|
| Sheet 1 — Company OKR Scorecard | ~90% ready | OKR quarterly target reference dataset needed |
| Sheet 2 — Practice Scorecard (PS + MC) | ~70% ready | Practice-level utilization % and compliance % views needed |
| Sheet 2 — Practice Scorecard (MIT) | ❌ Not ready | MIT classification in Clockify + `mit_*` snapshot columns needed |
| Sheet 3 — Team / POD View | ~50% ready | POD compliance % and utilization % views needed |

---

## 7. Effort Estimate

All estimates assume one developer familiar with the codebase (Python, PostgreSQL, QuickSight).

### Phase 1 — Data Layer (Backend Work)

| Task | Effort |
|------|--------|
| Create `vw_practice_kpi_weekly` view (utilization + compliance per `practice_area` per week) | 4 hours |
| Create `vw_pod_kpi_weekly` view (utilization + compliance per `pod_assignment` per week) | 3 hours |
| Create `okr_quarterly_targets` reference table with 2026 KR targets seeded | 2 hours |
| Verify and fix `mc_avg_duration_weeks` in `kpi_snapshot.py` if not computed | 1–2 hours |
| New SPICE datasets for `vw_practice_kpi_weekly` and `vw_pod_kpi_weekly` | 2 hours |
| **Phase 1 subtotal** | **12–13 hours** |

*MIT metrics are excluded from Phase 1 pending stakeholder confirmation (see Open Questions §8).*

### Phase 2 — Dashboard Build (QuickSight)

| Task | Effort |
|------|--------|
| New QuickSight analysis + dashboard skeleton with CE MIDNIGHT theme | 2 hours |
| Sheet 1 — Company OKR Scorecard (6 KPI tiles + 3 trend charts + health bar) | 5 hours |
| Sheet 2 — Practice Scorecard (5 KPI tiles + 4 charts + practice filter parameter) | 5 hours |
| Sheet 3 — Team / POD View (3 KPI tiles + 2 charts + POD filter parameter) | 3 hours |
| Time grain parameter (Week/Month/QTD/YTD) wired across all sheets | 3 hours |
| OKR quarterly target overlays on key trend lines | 2 hours |
| IaC: add new analysis + dashboard to `coo-dashboards.yaml` | 2 hours |
| Testing and accuracy verification | 3 hours |
| **Phase 2 subtotal** | **25 hours** |

### Total Estimate

| Option | Total Effort | Notes |
|--------|-------------|-------|
| **Option A** (extend COO dashboard) | ~30 hours | Saves ~5 hours on new dashboard skeleton + sharing setup |
| **Option B** (new standalone dashboard) *(recommended)* | **~37 hours** | Includes data layer + full dashboard build |
| Option B without MIT | ~30 hours | Defer MIT until data is confirmed |

**Recommended scope for initial build:** Option B, Phase 1 + Phase 2 excluding MIT (MIT deferred to a follow-up sprint after stakeholder confirmation). Total: ~30 hours.

---

## 8. Open Questions

The following must be confirmed before or during the build:

| # | Question | Who to Ask | Blocks |
|---|----------|-----------|--------|
| OQ-1 | **MIT practice scope:** Does MIT have active projects in Jira or Clockify today? Is MIT tracked separately as a practice, or are MIT staff categorized under PS or Internal? | COO / Practice Lead | MIT columns in Sheet 2; MIT `practice_area` in `clockify_users` migration 066 needs backfill |
| OQ-2 | **OKR targets for practice level:** KR2.1 (on-time delivery 90%) and KR2.2 (5-week duration) are company-level targets. Do PS and MC have the same targets, or different quarterly step values? | COO | `okr_quarterly_targets` table design; target reference lines on Sheet 2 |
| OQ-3 | **Dashboard audience and access:** Should Sheet 3 (POD View) be visible to all staff, or only to POD leads and above? This determines whether to build a standalone dashboard (Option B) or gate it behind the existing COO dashboard access. | COO | Build option selection (A vs B) |
| OQ-4 | **Utilization target by practice:** Is the 75% billable utilization target the same for PS, MC, and MIT staff? Or do Internal/Exempt staff have a different target (e.g., 0% billable)? | COO | `target_billable_util_pct` logic in `vw_practice_kpi_weekly` |
| OQ-5 | **Time grain aggregation preference for % KPIs:** When a user selects "QTD," should compliance % and utilization % show the average of weekly values, or be recomputed from raw hours? Averaging weekly values is simpler and already supported; raw recomputation is more accurate but requires additional backend work. | COO / Practice Leads | Phase 1 data layer design |
| OQ-6 | **POD naming and completeness:** Are Alpha, Bravo, Charlie, A2Z, and Free Agent the current and complete set of POD names in `clockify_users.pod_assignment`? Have any PODs been added or renamed recently? | Operations | Sheet 3 filter values and view design |
| OQ-7 | **"Projects in Red" target for KR2.4:** The OKR target is <10% of active projects in Red by Q4. Is this measured as a percentage of total active projects (PS + MC), or as an absolute count? | COO | KPI tile formula and target display on Sheet 1 |

---

## 9. Recommended Next Steps

1. **Confirm open questions** OQ-1 through OQ-3 with the COO — these are the blocking decisions before build can start.
2. **Start Phase 1 data layer** once OQ-1 is answered — the views and SPICE datasets can be built in parallel with stakeholder discussion on OQ-2 through OQ-7.
3. **Build Sheet 1 first** (Company OKR Scorecard) — it requires the least new data work and provides immediate value to the COO.
4. **Add Sheets 2 and 3** once `vw_practice_kpi_weekly` and `vw_pod_kpi_weekly` are deployed and SPICE is refreshed.
5. **Defer MIT** to a follow-up sprint pending OQ-1 resolution.

---

*Prepared by: Product Analyst | 2026-07-01*
*For questions or feedback, contact the weekly-reporting project team.*
