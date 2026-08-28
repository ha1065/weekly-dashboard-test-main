# KPI Tracking Dashboard — Strategic Redesign Brief
# KPI Tracking Dashboard — Strategic Redesign Brief

**Date:** 2026-07-09
**Prepared by:** Product Analyst
**Status:** Final — Analysis and Planning Only (No Implementation)
**Input documents:** `docs/kpi-dashboard-proposal.md`, `docs/2026-coo-okrs.md`, `docs/kpi-dashboard-assessment-2026-07-08.md`

---

## Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v1.0 | 2026-07-09 | Product Analyst | Initial redesign brief |

---

## 1. Strategic Assessment of Current Design

### Does the current dashboard answer the four business questions?

---

**Question 1: How are we doing against our KPIs as an organization?**

**Rating: Partially answered. Sheet 1 has the right KPIs but critical defects prevent reliable use.**

Sheet 1 (OKR Scorecard) was built for this question and has the right tile set: Billable Utilization %, Timesheet Compliance %, PS On-Time Delivery %, Open Escalations, Active Resources, Avg Engagement Duration, and Projects in Red %. Reference lines at OKR targets (75%, 95%, 90%) are correctly placed.

What fails this question:

- **MC is invisible at the organizational level.** The `kpi_snapshots` dataset has `mc_on_time_pct`, `mc_billable_hours`, `mc_active_projects`, and `mc_projects_green/amber/red`. None appear on Sheet 1. The COO sees PS delivery health but not MC. For a company where MC is a major line of business, this is a material omission.
- **"Projects in Red %" tile shows a raw count, not a percentage.** The tile displays the integer `3` rather than `8%`. The calculated field `projects_red_pct` exists in the code but is not wired to the tile. The OKR target (KR2.4: <10%) is percentage-based — comparing a count to a percentage target is meaningless.
- **On-Time Delivery trend shows only the Q4 final target (90%), not the quarterly step milestones.** In Q1 or Q2, the COO cannot determine whether current performance is on track for the quarter's intermediate goal. A trend line heading toward 90% looks different depending on whether the current quarter target is 45% or 75%.
- **Date controls default to the current in-progress week, not the last completed week.** The stakeholder requirement is one-week-in-arrears reporting. Opening the dashboard and seeing an incomplete week's data understates KPIs and creates confusion.
- **The time grain control does not aggregate data.** Selecting "Month" or "QTD" relabels the trend chart axis but does not collapse weekly rows into a monthly or quarterly aggregate. The COO cannot answer "What was our average Q2 compliance?" without manually counting data points.

---

**Question 2: How are we doing against our KPIs by line of business?**

**Rating: Not answered. Filter controls are non-functional and the data model does not fully support LoB-level KPI display.**

Sheet 2 (Practice Scorecard) was intended to answer this question. It shows three KPI tiles (Headcount, Billable Util %, Compliance %) and has LoB and Practice Alignment dropdowns. However:

- **Every filter control on Sheet 2 is non-functional.** Selecting "Professional Services" in the LoB dropdown has no effect on any visual. The FilterGroups use `FILTER_ALL_VALUES` and are not connected to the parameter values. This is the primary blocking defect.
- **On-Time Delivery % is absent from Sheet 2 entirely.** This is the most important PS-specific KPI and the subject of KR2.1. A Practice Lead for PS cannot see their on-time rate from this sheet.
- **Project health (Green/Amber/Red counts) is absent from Sheet 2.** The `kpi_snapshots` dataset has `ps_projects_green/amber/red` and `mc_projects_green/amber/red`. Neither is surfaced at the LoB level.
- **MIT has no data.** The `kpi_practice` dataset (sourced from `vw_practice_kpi_weekly`) groups by `practice_alignment`, not `line_of_business`. MIT staff may appear under specific practice alignments but there is no LoB-level rollup separating MIT from PS or MC.
- **On-Time Delivery does not apply to MC or MIT** — this KPI must be conditionally suppressed for those LoB selections. The current design shows a single PS on-time tile at all times regardless of LoB filter selection, which would be misleading once filters are fixed.

---

**Question 3: How are we doing against our KPIs by practice alignment?**

**Rating: Structurally present but non-functional due to broken filters and thin content.**

Sheet 2 uses the `kpi_practice` dataset which has the right granularity (`line_of_business × practice_alignment × week`). The data is loading. The SPICE dataset is ingested.

What fails this question:

- **Filters are broken** (same root cause as Question 2). Selecting a practice alignment does nothing.
- **The practice comparison view doesn't exist.** The most valuable view for a Practice Lead is a side-by-side bar chart showing current-week performance across all practice alignments. This enables a Practice Lead to see "DevOps is at 82%, Cloud Foundations is at 68% — Cloud Foundations needs attention." The current Sheet 2 shows only trend lines, not cross-practice comparisons.
- **On-Time Delivery is not in the `kpi_practice` dataset.** The `vw_practice_kpi_weekly` view has `billable_util_pct` and `compliance_pct` but no `on_time_pct`. On-time delivery tracking exists in `kpi_snapshots` at the LoB level (PS and MC separately) but not broken down by practice alignment within PS.
- **The headcount bar chart adds noise without insight.** Headcount varies by practice for structural reasons, not performance reasons. Using a chart slot on headcount when on-time delivery data is absent is a prioritization error.

---

**Question 4: How are we doing against our KPIs at an individual level?**

**Rating: Partially answered but raises a privacy concern that blocks broad deployment.**

Sheet 3 (Staff Detail) has the right structure for individual-level visibility: four KPI tiles, a POD compliance bar chart, a utilization trend, and a staff detail table showing every individual's name, hours, billable hours, utilization %, and compliance status.

What works: the staff detail table is the correct visual for this question. The four KPI tiles (Headcount, Avg Billable Util %, Compliance %, Total Billable Hours) provide the right summary context.

What fails this question:

- **Filters are non-functional.** A manager selecting their team's POD or a staff member selecting their own name has no effect. The table shows all staff regardless.
- **The staff detail table exposes individual performance data to all dashboard users.** If this dashboard is shared company-wide (the stated intent from the proposal's Option B rationale), every staff member can see every other staff member's utilization rate and compliance status. This is a privacy problem that blocks broad deployment.
- **Compliance % KPI tile displays as a decimal (0.72) not a percentage (72%).** The tile is unreadable as a business metric.
- **Individual filters cannot cascade correctly** without first fixing the filter wiring. Once fixed, the POD and Individual filters will need validation to confirm they produce correct subsets.

---

### Summary of current state

| Business Question | Current State | Primary Blocker |
|---|---|---|
| Q1: Org-level KPIs | Partially answered | Broken date default; MC invisible; Projects in Red % shows count not % |
| Q2: KPIs by LoB | Not answered | Broken filter controls; On-Time Delivery absent from Sheet 2 |
| Q3: KPIs by Practice Alignment | Not answered | Broken filter controls; no cross-practice comparison view |
| Q4: Individual-level KPIs | Partially answered | Broken filter controls; privacy risk from ungated staff table |

---

## 2. Recommended Dashboard Structure

### Keep three sheets. Rebalance the purpose and content of each.

Three sheets is the correct number for this audience structure. The personas are genuinely distinct and the data granularity changes across sheets. Four sheets would add navigation complexity without proportional value given the available data.

**The change is not structural — it is about what each sheet does:**

- **Sheet 1 (OKR Scorecard)** should be the executive summary screen. It answers Q1. No filters except date. Everything visible without interaction.
- **Sheet 2 (Practice Scorecard)** should answer Q2 and Q3 together. The LoB → Practice Alignment filter cascade narrows from business-line health down to practice health. The key insight this sheet must deliver — which it currently does not — is a cross-practice comparison view, not just a filtered-down version of Sheet 1.
- **Sheet 3 (Staff Detail)** answers Q4. It is the only sheet where individual data appears. Access to individual-level rows must be gated, not open.

### How the "one week in arrears" constraint changes the UX

The reporting cycle being one week behind means the dashboard's definition of "now" is always last week. Every date control, every default, every label that implies "current" must instead mean "last completed week." This is not a minor UI adjustment — it is a fundamental contract with the user about what the data represents.

Concretely:
- The default period on first load must be the most recently completed ISO week (Monday–Sunday), not the current calendar week.
- The KPI tiles (which use `TopBottomFilter` to show the most recent row) are already correct because the most recent complete row in SPICE is, by definition, last week's data — provided the SPICE refresh runs after Sunday close.
- The trend charts must default to showing completed weeks only. The current in-progress week, if it appears in SPICE at all, must be excluded.
- Date range controls must not offer "This Week" as an option since the current week's data is incomplete. The first selectable option must be "Last Completed Week."

### How LoB-specific KPI availability must be handled

On-Time Delivery applies to PS only. The dashboard must enforce this at the display level:

- On Sheet 1: Show On-Time Delivery at the company level labeled as "PS On-Time Delivery %" — not as a generic company KPI. This makes the scope explicit.
- On Sheet 2: When LoB filter = "PS," show the On-Time Delivery KPI tile. When LoB filter = "MC" or "MIT" or "Internal/Exempt," hide the tile or replace it with a placeholder that reads "N/A — On-Time Delivery applies to PS only."
- On Sheet 2: When LoB filter = "All," show On-Time Delivery but label it "PS On-Time Delivery %" so users understand it reflects PS data only.
- Never show an On-Time Delivery tile on Sheet 3 (Staff Detail) — the `kpi_staff` dataset has no on-time delivery column.

QuickSight does not support native conditional visibility of individual visuals based on parameter values. The practical implementation is to use a calculated field that returns null for non-PS rows and show the tile with a "No data for selected filter" empty state. Alternatively, use a text overlay visual that appears when LoB ≠ PS. The simpler approach is to always show the tile but label it "PS On-Time Delivery %" and include a subtitle: "Not applicable to MC/MIT." This approach works without custom visibility logic.

---

## 3. Sheet-by-Sheet Specification

---

### Sheet 1 — OKR Scorecard

**Purpose:** Give the COO and executive team a single-screen view of company KPI health against 2026 OKR targets. No filtering required — this sheet always shows company-wide data.

**Audience:** COO, executives, all-hands meetings, exec review screens.

**Default state on first load:**
- Date period = last completed week (the most recent `week_start_date` row in `kpi_snapshots` where `week_start_date < current Monday`)
- No practice or staff filters — this sheet has none
- Trend charts show last 52 weeks by default

**Filter controls:**
- **Date Range** — single date range control, defaults to last completed week. Preset options: Last Week | Last Month | Last Quarter (QTD) | Year to Date. No "This Week" option. Label the control "Reporting Period" not "Date Range" to reinforce the arrears context.
- No LoB, Practice, POD, or Individual filters on this sheet. Sheet 1 is always company-wide.

**KPI tiles — row of 7 tiles across the top:**

| Tile | Metric | Source Column | Target | RAG Thresholds | Comparison |
|------|--------|--------------|--------|----------------|------------|
| Billable Utilization % | `billable_util_pct` | `kpi_snapshots` | 75% | Green ≥75%, Amber 65–74%, Red <65% | vs. target (75%) and vs. prior week |
| Productive Utilization % | `productive_util_pct` | `kpi_snapshots` | 80% | Green ≥80%, Amber 70–79%, Red <70% | vs. target (80%) |
| Timesheet Compliance % | `time_compliance_pct` | `kpi_snapshots` | 95% | Green ≥95%, Amber 85–94%, Red <85% | vs. target (95%) and vs. prior week |
| PS On-Time Delivery % | `ps_on_time_pct` | `kpi_snapshots` | See quarterly steps | Green ≥ current quarter target, Amber within 10pp below, Red >10pp below | vs. current quarter OKR target |
| Avg Engagement Duration | `ps_avg_duration_weeks` | `kpi_snapshots` | See quarterly steps | Green ≤ current quarter target, Amber within 1 week above, Red >1 week above | vs. current quarter OKR target |
| Projects in Red % | `projects_red_pct` (calculated: `total_projects_red / (total_projects_green + total_projects_amber + total_projects_red) × 100`) | `kpi_snapshots` | <10% | Green <10%, Amber 10–19%, Red ≥20% | vs. 10% target |
| Open Escalations | `open_escalations` | `kpi_snapshots` | 0 | Green =0, Amber 1–2, Red ≥3 | vs. prior week (delta) |

**Note on PS On-Time Delivery RAG:** The quarterly step targets are Q1=45%, Q2=60%, Q3=75%, Q4=90%. The current quarter target is determined by the `week_start_date` of the selected period. A calculated field `current_quarter_otd_target` should return the appropriate step value based on `EXTRACT(QUARTER FROM week_start_date)`.

**Visuals — three chart zone below the tile row:**

| Zone | Visual | Type | Data | Config |
|------|--------|------|------|--------|
| Left (40% width) | Billable Utilization % trend | Line chart | `week_start_date` (x), `billable_util_pct` (y, blue line), `target_billable_util_pct` constant at 75% (dashed grey reference line) | Last 52 weeks. Y-axis 0–100%. Label: "Billable Utilization % — Weekly Trend" |
| Center (30% width) | PS On-Time Delivery % trend with quarterly step targets | Line chart | `week_start_date` (x), `ps_on_time_pct` (y, blue line), quarterly step-function reference line (orange dashed) | Step function drawn from `okr_quarterly_targets` reference: Q1 weeks show 45% line, Q2 show 60%, Q3 show 75%, Q4 show 90%. Y-axis 0–100%. |
| Right (30% width) | Timesheet Compliance % trend | Line chart | `week_start_date` (x), `time_compliance_pct` (y, blue line), 95% reference line (dashed grey) | Last 52 weeks. Y-axis 0–100%. |

**Bottom zone — project health stacked bar:**

| Visual | Type | Data | Config |
|--------|------|------|--------|
| Project Health by Week | Stacked bar chart | `week_start_date` (x), `ps_projects_green + mc_projects_green` (green stack), `ps_projects_amber + mc_projects_amber` (amber stack), `ps_projects_red + mc_projects_red` (red stack) | Last 26 weeks. Colors: green `#33A94F`, amber `#FF9B00`, red `#D74018`. Label: "Project Portfolio Health — Combined PS + MC" |

---

### Sheet 2 — Practice Scorecard

**Purpose:** Enable Practice Leads and the COO to compare KPI performance across lines of business and practice alignments. The primary value of this sheet is the cross-practice comparison view — seeing all practices simultaneously, not a filtered subset.

**Audience:** Practice Leads (PS, MC, MIT), COO, operations team.

**Default state on first load:**
- LoB = All (all lines of business shown)
- Practice Alignment = All (all practices shown)
- Date = last completed week
- Visuals show all practices side-by-side in comparison charts

**Filter controls (left-to-right in the filter bar):**
1. **Line of Business** — dropdown: All | PS | MC | MIT | Internal/Exempt. Default: All.
2. **Practice Alignment** — dropdown populated from `practice_alignment` values in `kpi_practice`. Default: All. Cascades from LoB selection (when LoB = PS, show only PS practice alignments).
3. **Reporting Period** — date range with presets: Last Week | Last Month | Last Quarter | Year to Date. Default: Last Week.

**Controls NOT on this sheet:** POD, Individual. The `kpi_practice` dataset has no `pod_assignment` or `user_name` column. Adding these controls would create non-functional decorative dropdowns (the current problem). They must not appear here.

**KPI tiles — row of 5 tiles:**

| Tile | Metric | Source Column | Target | RAG Thresholds | Show/Hide Rule |
|------|--------|--------------|--------|----------------|----------------|
| Headcount | `headcount` (sum across selected practices) | `kpi_practice` | None | No RAG — context metric | Always visible |
| Total Capacity Hours | `total_capacity_hours` (sum) | `kpi_practice` | None | No RAG — context metric | Always visible |
| Total Billable Hours | `total_billable_hours` (sum) | `kpi_practice` | None | No RAG — volume metric | Always visible |
| Billable Utilization % | `billable_util_pct` (weighted average by headcount) | `kpi_practice` | 75% | Green ≥75%, Amber 65–74%, Red <65% | Always visible |
| Timesheet Compliance % | `compliance_pct` (weighted average by headcount) | `kpi_practice` | 95% | Green ≥95%, Amber 85–94%, Red <85% | Always visible |

**Note on weighted average:** When multiple practices are selected, Billable Utilization % and Compliance % must be weighted by headcount, not a simple average of percentages. A simple average treats a 2-person team the same as a 20-person team. Use `SUM(total_billable_hours) / SUM(total_capacity_hours) × 100` for utilization. For compliance, use `SUM(compliant_staff_count) / SUM(headcount) × 100` — this requires adding a `compliant_staff_count` column to `vw_practice_kpi_weekly` (see Section 6 — Data Gaps).

**On-Time Delivery handling on Sheet 2:**
- On-Time Delivery is NOT available in the `kpi_practice` dataset. It exists only in `kpi_snapshots` at the PS and MC LoB level.
- Do NOT add a 6th KPI tile sourced from `kpi_snapshots` mixed with `kpi_practice` tiles — dataset mixing in a single visual row is error-prone and creates filter scope confusion.
- Instead, add a separate callout section below the tile row when LoB = PS or LoB = All: a single large-format KPI display showing `ps_on_time_pct` sourced from `kpi_snapshots`, labeled "PS On-Time Delivery % (company-level — practice breakdown not available)." This visually separates it from the `kpi_practice`-sourced tiles and makes the data scope explicit.
- When LoB = MC, MIT, or Internal/Exempt, hide the callout entirely.

**Visuals — two rows of charts:**

**Row 1 — Cross-practice comparison (current week snapshot):**

| Visual | Type | Data | Config |
|--------|------|------|--------|
| Billable Utilization % by Practice Alignment | Horizontal bar chart | `practice_alignment` (y-axis), `billable_util_pct` (x-axis, bar length) | Sorted descending by utilization. Reference line at 75% (dashed). Colors: bar = CE primary blue `#0089DD`. Bars below target = red `#D74018`. Label: "Current Week Billable Utilization % by Practice" |
| Compliance % by Practice Alignment | Horizontal bar chart | `practice_alignment` (y-axis), `compliance_pct` (x-axis) | Same layout. Reference line at 95%. Bars below target = red `#D74018`. Label: "Current Week Timesheet Compliance % by Practice" |

**Row 2 — Trend over time:**

| Visual | Type | Data | Config |
|--------|------|------|--------|
| Billable Utilization % trend, all practices | Multi-line chart | `week_start_date` (x), `billable_util_pct` (y), `practice_alignment` (color dimension) | Last 26 weeks. One line per practice. 75% reference line. Legend showing practice names. |
| Compliance % trend, all practices | Multi-line chart | `week_start_date` (x), `compliance_pct` (y), `practice_alignment` (color dimension) | Last 26 weeks. One line per practice. 95% reference line. |

**RAG thresholds:**
- Billable Utilization %: Green ≥75%, Amber 65–74%, Red <65%
- Compliance %: Green ≥95%, Amber 85–94%, Red <85%

---

### Sheet 3 — Staff Detail

**Purpose:** Enable managers and practice leads to drill into team-level and individual-level KPIs. POD-level and individual staff data. Not for broad self-service access without row-level security.

**Audience:** Practice Leads (managing their own staff), COO, operations team. NOT general staff until row-level security is configured.

**Default state on first load:**
- All filters = All (company-wide aggregate)
- Date = last completed week
- Staff detail table is visible but shows all staff — manager must apply filters to scope to their team

**Filter controls (left-to-right, labeled as parallel independent filters, not a cascade):**
1. **Line of Business** — dropdown: All | PS | MC | MIT | Internal/Exempt. Default: All.
2. **Practice Alignment** — dropdown from `practice_alignment` values in `kpi_staff`. Default: All.
3. **Individual Staff Member** — dropdown from `user_name` values. Default: All.
4. **POD** — dropdown: All | Alpha | Bravo | Charlie | A2Z | Free Agent. Default: All.
5. **Reporting Period** — date presets: Last Week | Last Month | Last Quarter | Year to Date. Default: Last Week.

**Visual separator rule:** Display LoB, Practice, and Individual as one group (labeled "Organization Filters") and POD as a separate group (labeled "Team Filter") with a visual divider between them. This communicates that POD is a parallel dimension, not a child of Practice Alignment.

**KPI tiles — row of 4 tiles:**

| Tile | Metric | Calculation | Target | RAG Thresholds |
|------|--------|------------|--------|----------------|
| Headcount | Count of distinct `user_name` in filtered set | `COUNT_DISTINCT(user_name)` | None | No RAG |
| Avg Billable Utilization % | `AVG(billable_util_pct) × 100` formatted as percentage | `kpi_staff` | 75% | Green ≥75%, Amber 65–74%, Red <65% |
| Timesheet Compliance % | `AVG(is_compliant) × 100` formatted as percentage | `kpi_staff` | 95% | Green ≥95%, Amber 85–94%, Red <85% |
| Total Billable Hours | `SUM(billable_hours)` | `kpi_staff` | None | No RAG — volume metric |

**Critical format fix:** Both Avg Billable Utilization % and Timesheet Compliance % must be multiplied by 100 and formatted with "%" suffix. Currently `AVG(is_compliant)` returns a decimal (0.72) and displays as "0.72." The calculated fields must be `AVG(is_compliant) * 100` and the tile format set to `#,##0.0'%'`.

**Visuals:**

| Visual | Type | Data | Config |
|--------|------|------|--------|
| Compliance % by POD | Horizontal bar chart | `pod_assignment` (y-axis), `AVG(is_compliant) * 100` (x-axis) | Reference line at 95%. Colors: bar above target = green, below = red. Filtered by all active filters. |
| Billable Utilization % trend by Practice | Multi-line chart | `week_start_date` (x), `AVG(billable_util_pct) * 100` (y), `practice_alignment` (color) | Last 26 weeks. 75% reference line. Responds to all filter selections. |
| Staff Detail Table | Table | Columns: `user_name`, `practice_alignment`, `pod_assignment`, `cloudelligent_title`, `week_start`, `hours_logged`, `billable_hours`, `billable_util_pct` (formatted as %), `compliance_status` | Sorted by `compliance_status` (Non-Compliant first), then by `billable_util_pct` ascending. Conditional formatting: `compliance_status = Non-Compliant` → red row background. **Access note:** This table must be removed from any version of the dashboard shared with general staff. It should only appear in the leadership/manager access version. |

**RAG thresholds:**
- Billable Utilization %: Green ≥75%, Amber 65–74%, Red <65%
- Compliance %: Green ≥95%, Amber 85–94%, Red <85%

---

## 4. Date Control Redesign

### Core principle: the dashboard's "now" is always last completed week

The reporting cycle is one week in arrears. Every date control must reflect this. The word "current" must not appear anywhere in the date UI — it implies live data that does not exist.

### Default period on first load

**All three sheets must default to the most recently completed ISO week (Monday–Sunday).**

Implementation: a calculated default parameter that returns the `MAX(week_start_date)` from `kpi_snapshots` where `week_start_date < DATE_TRUNC('week', CURRENT_DATE)`. This ensures:
- The default is always a complete week
- If SPICE refreshes run on Monday after Sunday close, the default shows last week
- The current in-progress week is never the default

QuickSight parameter defaults cannot execute dynamic SQL, so the "most recent complete week" logic must be enforced at the SPICE dataset level: add a boolean column `is_complete_week` to `kpi_snapshots` (or compute it as `week_start_date < DATE_TRUNC('week', CURRENT_DATE)`). Then filter the dataset or use a TopBottomFilter on `week_start_date` with rank = 1 to pin the default KPI tiles to the most recent complete row.

For trend charts, apply a persistent dataset-level filter that excludes any `week_start_date >= DATE_TRUNC('week', CURRENT_DATE)` — this prevents a partial current week from appearing as a dip at the right edge of every trend line.

### Preset label redesign

Remove or rename all presets that imply "current":

| Old Label | New Label | Definition |
|-----------|-----------|------------|
| This Week | *(remove)* | Current week is incomplete — never show |
| This Month | Last Full Month | Calendar month of last completed week |
| This Quarter | Quarter to Date (completed weeks) | All complete weeks in current quarter |
| YTD | Year to Date (completed weeks) | All complete weeks since Jan 1, 2026 |
| *(new)* | **Last Completed Week** | Single week — the default, always pinned to latest complete row |

The first preset must always be "Last Completed Week" and must be the selected default. This preset should also appear as a badge or label on each sheet header (e.g., "Showing: Week of Jun 30 – Jul 6, 2026") so users immediately understand what period the tiles represent without needing to inspect the date control.

### "Last Completed Week" preset — implementation spec

Add a dedicated parameter default calculation or a fixed filter:

```
week_start_date = MAX(week_start_date) WHERE week_start_date < CURRENT_DATE - DAYOFWEEK(CURRENT_DATE)
```

In QuickSight, implement as a TopBottomFilter on `week_start_date` with `TopBottomType: TOP`, `Count: 1`, applied only to KPI tile visuals. Trend charts use the full date range selected by the user.

### Sheet-by-sheet date control defaults

| Sheet | Default Period | Date Control Type | Trend Chart Default Range |
|-------|---------------|-------------------|---------------------------|
| Sheet 1 — OKR Scorecard | Last Completed Week | Date range with presets | Last 52 completed weeks |
| Sheet 2 — Practice Scorecard | Last Completed Week | Date range with presets | Last 26 completed weeks |
| Sheet 3 — Staff Detail | Last Completed Week | Date range with presets | Last 26 completed weeks |

---

## 5. KPI Tile Design

Full specification for every KPI tile across all three sheets. Each entry includes: display label, applicable lines of business, target, RAG thresholds, and comparison value shown below the main metric.

---

### Sheet 1 — OKR Scorecard Tiles

---

**Tile 1: Billable Utilization %**

- Display label: `Billable Utilization %`
- Subtitle: `Target: 75%`
- Applies to: All lines of business (company-wide)
- Source: `kpi_snapshots.billable_util_pct`
- Target: 75%
- RAG thresholds: Green ≥75% | Amber 65–74% | Red <65%
- Comparison shown: Delta vs. target (`actual − 75%`, displayed as `+3pp` or `−7pp`) and delta vs. prior week
- Format: `#,##0.0'%'`

---

**Tile 2: Productive Utilization %**

- Display label: `Productive Utilization %`
- Subtitle: `Target: 80%`
- Applies to: All lines of business (company-wide)
- Source: `kpi_snapshots.productive_util_pct`
- Target: 80%
- RAG thresholds: Green ≥80% | Amber 70–79% | Red <70%
- Comparison shown: Delta vs. target
- Format: `#,##0.0'%'`

---

**Tile 3: Timesheet Compliance %**

- Display label: `Timesheet Compliance %`
- Subtitle: `Target: 95% (KR5.1)`
- Applies to: All lines of business (company-wide including Internal/Exempt)
- Source: `kpi_snapshots.time_compliance_pct`
- Target: 95%
- RAG thresholds: Green ≥95% | Amber 85–94% | Red <85%
- Comparison shown: Delta vs. target and delta vs. prior week
- Format: `#,##0.0'%'`

---

**Tile 4: PS On-Time Delivery %**

- Display label: `PS On-Time Delivery %`
- Subtitle: Dynamic — shows current quarter target: e.g., `Q3 Target: 75%` (from `okr_quarterly_targets` reference table)
- Applies to: PS only. Label makes scope explicit. Always visible on Sheet 1 (company-wide sheet has no LoB filter).
- Source: `kpi_snapshots.ps_on_time_pct`
- Target: Quarterly step — Q1: 45%, Q2: 60%, Q3: 75%, Q4: 90%
- RAG thresholds (relative to current quarter target `T`): Green: actual ≥ T | Amber: actual between T−10pp and T | Red: actual < T−10pp
- Comparison shown: Delta vs. current quarter OKR target
- Format: `#,##0.0'%'`
- Note: Do NOT relabel as "On-Time Delivery %" without the "PS" qualifier. MC's on-time delivery is separate and this tile must never be interpreted as company-wide.

---

**Tile 5: Avg Engagement Duration (weeks)**

- Display label: `Avg Engagement Duration`
- Subtitle: Dynamic — shows current quarter target: e.g., `Q3 Target: 7 weeks`
- Applies to: PS only (the metric exists in `kpi_snapshots.ps_avg_duration_weeks`; MC equivalent is not reliably populated)
- Source: `kpi_snapshots.ps_avg_duration_weeks`
- Target: Quarterly step — Q1: 12 weeks, Q2: 10 weeks, Q3: 7 weeks, Q4: 5 weeks
- RAG thresholds (lower is better; relative to current quarter target `T`): Green: actual ≤ T | Amber: actual between T and T+1 week | Red: actual > T+1 week
- Comparison shown: Delta vs. current quarter OKR target (e.g., `+2.3 weeks above target`)
- Format: `#,##0.0' wks'`

---

**Tile 6: Projects in Red %**

- Display label: `Projects in Red %`
- Subtitle: `Target: <10% (KR2.4)`
- Applies to: PS + MC combined (use `ps_projects_red + mc_projects_red` as numerator, `ps_projects_green + ps_projects_amber + ps_projects_red + mc_projects_green + mc_projects_amber + mc_projects_red` as denominator)
- Source: Calculated field `projects_red_pct = (ps_projects_red + mc_projects_red) / (ps_projects_green + ps_projects_amber + ps_projects_red + mc_projects_green + mc_projects_amber + mc_projects_red) * 100`
- Target: <10%
- RAG thresholds: Green <10% | Amber 10–19% | Red ≥20%
- Comparison shown: Delta vs. 10% target and delta vs. prior week
- Format: `#,##0.0'%'`
- **Critical fix required:** The current tile shows the raw integer `total_projects_red`. This must be replaced with the `projects_red_pct` calculated field.

---

**Tile 7: Open Escalations**

- Display label: `Open Escalations`
- Subtitle: `Target: 0`
- Applies to: All lines of business
- Source: `kpi_snapshots.open_escalations`
- Target: 0
- RAG thresholds: Green =0 | Amber 1–2 | Red ≥3
- Comparison shown: Delta vs. prior week (e.g., `+1 from last week`)
- Format: `#,##0` (integer)

---

### Sheet 2 — Practice Scorecard Tiles

---

**Tile 1: Headcount**

- Display label: `Headcount`
- Subtitle: `Active staff in selected practices`
- Applies to: All (filtered by LoB and Practice Alignment selections)
- Source: `SUM(kpi_practice.headcount)`
- Target: None
- RAG: None — context metric
- Comparison shown: Delta vs. prior week
- Format: `#,##0`

---

**Tile 2: Total Capacity Hours**

- Display label: `Total Capacity Hours`
- Subtitle: `Scheduled available hours`
- Applies to: All (filtered)
- Source: `SUM(kpi_practice.total_capacity_hours)`
- Target: None
- RAG: None — context metric
- Comparison shown: None
- Format: `#,##0`

---

**Tile 3: Total Billable Hours**

- Display label: `Total Billable Hours`
- Subtitle: Period hours
- Applies to: All (filtered)
- Source: `SUM(kpi_practice.total_billable_hours)`
- Target: None
- RAG: None — volume metric
- Comparison shown: Delta vs. prior week
- Format: `#,##0`

---

**Tile 4: Billable Utilization %**

- Display label: `Billable Utilization %`
- Subtitle: `Target: 75%`
- Applies to: All (filtered). Note: Internal/Exempt staff have different effective targets — when LoB = Internal/Exempt, suppress the 75% target comparison or display "N/A — Internal staff" in the subtitle.
- Source: `SUM(total_billable_hours) / SUM(total_capacity_hours) * 100` (weighted average)
- Target: 75%
- RAG: Green ≥75% | Amber 65–74% | Red <65%
- Comparison shown: Delta vs. target
- Format: `#,##0.0'%'`

---

**Tile 5: Timesheet Compliance %**

- Display label: `Timesheet Compliance %`
- Subtitle: `Target: 95%`
- Applies to: All (filtered)
- Source: `SUM(compliant_staff_count) / SUM(headcount) * 100` (requires `compliant_staff_count` column in `vw_practice_kpi_weekly` — see Section 6)
- Target: 95%
- RAG: Green ≥95% | Amber 85–94% | Red <85%
- Comparison shown: Delta vs. target
- Format: `#,##0.0'%'`

---

**PS On-Time Delivery callout (separate from tile row, shown only when LoB = PS or All):**

- Display label: `PS On-Time Delivery %`
- Subtitle: `Source: company-level snapshot — practice breakdown not available`
- Source: `kpi_snapshots.ps_on_time_pct` (separate dataset reference)
- Target: Current quarter step target from `okr_quarterly_targets`
- RAG: Same as Sheet 1 Tile 4
- Format: Large KPI display, not a standard tile. Include a tooltip explaining it reflects all PS projects, not filtered to a sub-practice.

---

### Sheet 3 — Staff Detail Tiles

---

**Tile 1: Headcount**

- Display label: `Headcount`
- Subtitle: `Staff members in filtered view`
- Source: `COUNT_DISTINCT(kpi_staff.user_name)`
- Target: None | RAG: None
- Format: `#,##0`

---

**Tile 2: Avg Billable Utilization %**

- Display label: `Avg Billable Utilization %`
- Subtitle: `Target: 75%`
- Source: `AVG(kpi_staff.billable_util_pct) * 100`
- **Critical fix:** Must multiply by 100. The raw column values in `kpi_staff.billable_util_pct` may already be expressed as percentages (check source view) — verify whether the column stores 0.72 or 72. Apply format `#,##0.0'%'` regardless.
- Target: 75%
- RAG: Green ≥75% | Amber 65–74% | Red <65%
- Comparison shown: Delta vs. target

---

**Tile 3: Timesheet Compliance %**

- Display label: `Timesheet Compliance %`
- Subtitle: `Target: 95%`
- Source: `AVG(kpi_staff.is_compliant) * 100`
- **Critical fix:** `is_compliant` is 0/1. `AVG(is_compliant)` returns a decimal between 0 and 1. Must multiply by 100. Current tile shows `0.72` — this is the bug to fix.
- Target: 95%
- RAG: Green ≥95% | Amber 85–94% | Red <85%
- Format: `#,##0.0'%'`

---

**Tile 4: Total Billable Hours**

- Display label: `Total Billable Hours`
- Subtitle: Period total
- Source: `SUM(kpi_staff.billable_hours)`
- Target: None | RAG: None
- Format: `#,##0`


## 6. Data Gaps

### What the four business questions require vs. what is available

---

### Available now — no new data work needed

These KPIs can be surfaced immediately using existing SPICE datasets:

| KPI | Dataset | Column(s) | Sheet |
|-----|---------|-----------|-------|
| Company billable utilization % | `kpi_snapshots` | `billable_util_pct` | Sheet 1 |
| Company productive utilization % | `kpi_snapshots` | `productive_util_pct` | Sheet 1 |
| Company timesheet compliance % | `kpi_snapshots` | `time_compliance_pct` | Sheet 1 |
| PS on-time delivery % | `kpi_snapshots` | `ps_on_time_pct` | Sheet 1, Sheet 2 callout |
| PS avg engagement duration | `kpi_snapshots` | `ps_avg_duration_weeks` | Sheet 1 |
| PS project health counts | `kpi_snapshots` | `ps_projects_green/amber/red` | Sheet 1 |
| MC project health counts | `kpi_snapshots` | `mc_projects_green/amber/red` | Sheet 1 |
| MC billable hours | `kpi_snapshots` | `mc_billable_hours` | Sheet 1 |
| Open escalations | `kpi_snapshots` | `open_escalations` | Sheet 1 |
| Active resource count | `kpi_snapshots` | `active_resource_count` | Sheet 1 |
| Practice-level billable utilization % | `kpi_practice` | `billable_util_pct` | Sheet 2 |
| Practice-level compliance % | `kpi_practice` | `compliance_pct` | Sheet 2 |
| Practice-level headcount | `kpi_practice` | `headcount` | Sheet 2 |
| Practice-level total billable hours | `kpi_practice` | `total_billable_hours` | Sheet 2 |
| Practice-level total capacity hours | `kpi_practice` | `total_capacity_hours` | Sheet 2 |
| Staff billable utilization % | `kpi_staff` | `billable_util_pct` | Sheet 3 |
| Staff compliance (0/1) | `kpi_staff` | `is_compliant`, `compliance_status` | Sheet 3 |
| Staff billable and logged hours | `kpi_staff` | `billable_hours`, `hours_logged` | Sheet 3 |
| Staff POD assignment | `kpi_staff` | `pod_assignment` | Sheet 3 |

---

### Gap 1 — OKR quarterly step targets (MUST-HAVE for v1)

**What's missing:** There is no reference dataset for the quarterly step targets of KR2.1 (45/60/75/90%) and KR2.2 (12/10/7/5 weeks). The on-time delivery trend chart on Sheet 1 currently shows a flat 90% reference line regardless of what quarter it is. In Q1 or Q2 this is misleading — it makes performance look far behind a target that is not yet due.

**Business impact:** The COO cannot assess whether on-time delivery is on track for the current quarter. The single most important executive insight from KR2.1 is invisible.

**What's needed:** A small reference table `okr_quarterly_targets` with columns `(kr_id, quarter_label, week_start, week_end, target_value)`. Seed with:

| KR | Quarter | Week Start | Week End | Target Value |
|----|---------|-----------|----------|-------------|
| KR2.1 | Q1 2026 | 2026-01-05 | 2026-03-29 | 45 |
| KR2.1 | Q2 2026 | 2026-03-30 | 2026-06-28 | 60 |
| KR2.1 | Q3 2026 | 2026-06-29 | 2026-09-27 | 75 |
| KR2.1 | Q4 2026 | 2026-09-28 | 2026-12-27 | 90 |
| KR2.2 | Q1 2026 | 2026-01-05 | 2026-03-29 | 12 |
| KR2.2 | Q2 2026 | 2026-03-30 | 2026-06-28 | 10 |
| KR2.2 | Q3 2026 | 2026-06-29 | 2026-09-27 | 7 |
| KR2.2 | Q4 2026 | 2026-09-28 | 2026-12-27 | 5 |

**Implementation options:**
- Option A (preferred): Create the table in PostgreSQL, add a SPICE dataset, join to `kpi_snapshots` on `week_start_date BETWEEN week_start AND week_end`. Add as a reference line data source on the trend charts.
- Option B (no-code): Hardcode the step values as calculated fields in QuickSight using `ifelse(EXTRACT('quarter', week_start_date) = 1, 45, EXTRACT('quarter', week_start_date) = 2, 60, EXTRACT('quarter', week_start_date) = 3, 75, 90)`. Simpler, no new table, but harder to update if OKR targets change.

**Priority: Must-have for v1.** The OKR Scorecard is the primary executive view. Without quarterly step targets, it does not answer "are we on track this quarter?"

**Effort:** Option A = 2–3 hours. Option B = 30 minutes.

---

### Gap 2 — `compliant_staff_count` column in `vw_practice_kpi_weekly` (MUST-HAVE for v1)

**What's missing:** The `kpi_practice` dataset (`vw_practice_kpi_weekly`) has `compliance_pct` but no `compliant_staff_count`. To compute a correctly weighted compliance percentage when multiple practices are selected on Sheet 2, the formula must be `SUM(compliant_staff_count) / SUM(headcount)`. Without `compliant_staff_count`, the only option is `AVG(compliance_pct)` — a simple average that weights a 2-person practice the same as a 20-person practice.

**Business impact:** When a Practice Lead selects "All" practices on Sheet 2, the compliance tile will be wrong by up to several percentage points if practice sizes differ significantly.

**What's needed:** Add `compliant_staff_count = ROUND(compliance_pct * headcount)` to `vw_practice_kpi_weekly`. This is computable from existing columns — no new source data required.

**Effort:** 1 hour (update the PostgreSQL view, refresh SPICE).

**Priority: Must-have for v1.** Without it, the weighted average cannot be computed correctly.

---

### Gap 3 — `is_complete_week` flag on `kpi_snapshots` (MUST-HAVE for v1)

**What's missing:** No column identifies whether a `week_start_date` row represents a completed week or the current in-progress week. Without this, the default date filter logic cannot reliably exclude partial weeks, and trend charts may show a dip on the rightmost data point.

**What's needed:** Add `is_complete_week = (week_start_date < DATE_TRUNC('week', CURRENT_DATE))` to `kpi_snapshots` (or compute it as a SPICE calculated field). Apply a dataset-level filter to all three sheets: `is_complete_week = TRUE`.

**Effort:** 30 minutes (calculated field in SPICE or column in the view).

**Priority: Must-have for v1.** Required to enforce the one-week-in-arrears UX contract.

---

### Gap 4 — MC on-time delivery surfaced on Sheet 1 (MUST-HAVE for v1)

**What's missing:** `kpi_snapshots.mc_on_time_pct` exists in the dataset schema but is not displayed on any sheet. The COO cannot see MC delivery performance.

**What's needed:** Add an MC On-Time Delivery tile or combined company on-time metric to Sheet 1. Two options:
- Option A: Separate tile "MC On-Time Delivery %" alongside the PS tile.
- Option B: Combined company-level tile using a weighted average: `(ps_on_time_pct * ps_active_projects + mc_on_time_pct * mc_active_projects) / (ps_active_projects + mc_active_projects)`, labeled "Company On-Time Delivery % (PS + MC)."

**Stakeholder decision required:** Confirm whether MC on-time delivery has the same 90% Q4 target as PS, or a different target. The OKR (KR2.1) specifies a company-level target; if MC has no specific sub-target, Option B (combined) is cleaner.

**Effort:** 1–2 hours (add tile to Sheet 1, verify `mc_on_time_pct` is populated in `kpi_snapshot.py`).

**Priority: Must-have for v1.**

---

### Gap 5 — MC avg engagement duration (MEDIUM priority)

**What's missing:** `kpi_snapshots.mc_avg_duration_weeks` may not be computed by `kpi_snapshot.py`. The column was added to the schema later and the snapshot logic historically targeted PS. If the column is always NULL, the Avg Engagement Duration tile silently omits MC.

**What's needed:** Verify `kpi_snapshot.py` populates `mc_avg_duration_weeks`. If not, add the computation using the same logic as PS but filtering to MC Jira projects.

**Effort:** 1–2 hours (code audit + fix in `kpi_snapshot.py`).

**Priority: Medium — include in v1 if the column is already populated. If not, surface it as a labeled gap on the tile ("MC duration: pending data") rather than silently hiding it.**

---

### Gap 6 — POD-level compliance % and utilization % (NICE-TO-HAVE, v2)

**What's missing:** The `kpi_staff` dataset has `pod_assignment` per staff member, so the POD compliance bar chart on Sheet 3 is computable using `AVG(is_compliant)` grouped by `pod_assignment`. This currently works. However, there is no pre-aggregated POD-level view (`vw_pod_kpi_weekly`) that would allow a Sheet 2-style cross-POD comparison with capacity-weighted utilization.

**Business impact:** Low for v1. The Sheet 3 POD compliance bar chart answers the question adequately using the staff dataset. A dedicated POD view would enable POD-level trend lines, but this is a management-level view that is lower priority than the practice-level gaps.

**Effort:** 3–4 hours (new PostgreSQL view, new SPICE dataset, new Sheet 2 or Sheet 3 visuals).

**Priority: Nice-to-have. Defer to v2.**

---

### Gap 7 — MIT-specific metrics (NICE-TO-HAVE, v2, pending stakeholder confirmation)

**What's missing:** The `kpi_snapshots` table has no `mit_*` columns. MIT staff appear in `kpi_practice` under their individual practice alignments (e.g., "Cloud Foundations" practice members who happen to be on MIT engagements), but there is no MIT-specific on-time delivery rate, project count, or project health breakdown.

**Stakeholder decision required before any MIT work begins:** Does MIT have projects tracked in Jira with schedules and health status? If MIT is pure recurring managed services with no project delivery milestones, then on-time delivery and engagement duration are not meaningful KPIs for MIT and the current approach (Billable Utilization % and Compliance % only) is correct.

**If MIT does have project-tracked engagements:** Add `mit_*` columns to `kpi_snapshots` and extend `kpi_snapshot.py`. Estimate 1–2 days.

**Priority: Nice-to-have. Block on stakeholder confirmation. Do not build MIT columns until the data model is confirmed.**

---

### Data gap summary by priority

| Gap | Priority | Effort | Blocks |
|-----|----------|--------|--------|
| OKR quarterly step targets | Must-have v1 | 30 min – 3 hrs | Sheet 1 on-time delivery trend; quarterly milestone tracking |
| `compliant_staff_count` in `vw_practice_kpi_weekly` | Must-have v1 | 1 hr | Sheet 2 weighted compliance tile |
| `is_complete_week` flag | Must-have v1 | 30 min | In-arrears default date enforcement on all sheets |
| MC on-time delivery on Sheet 1 | Must-have v1 | 1–2 hrs | COO visibility into MC delivery performance |
| MC avg engagement duration verification | Medium | 1–2 hrs | Avg Duration tile accuracy |
| POD-level pre-aggregated view | Nice-to-have v2 | 3–4 hrs | Cross-POD trend comparisons |
| MIT-specific metrics | Nice-to-have v2 | 1–2 days | MIT LoB filter coverage (pending stakeholder confirmation) |

---

## 7. Implementation Roadmap

Ordered by effort and dependency. Items within each tier are independent and can be parallelized.

---

### Tier 1 — QuickSight patches only (no data pipeline changes required)

These can all be done as pure changes to `build_kpi_dashboard.py` and redeployed without touching PostgreSQL views, Lambda functions, or SPICE dataset definitions. Estimated total: **4–6 hours.**

| # | Change | File | Effort |
|---|--------|------|--------|
| 1.1 | **Fix FilterGroup wiring on Sheet 2 and Sheet 3** — replace `FilterListConfiguration / FILTER_ALL_VALUES` with `CustomFilterConfiguration / ParameterName` for all LoB, Practice, POD, and Individual FilterGroups | `build_kpi_dashboard.py` — `build_sheet2()`, `build_sheet3()` | 2 hrs |
| 1.2 | **Fix parameter defaults** — change `DefaultValues: StaticValues: ['All']` to empty string `''` and rely on `FILTER_ALL_VALUES` as the pass-through. Validate default state shows all data. | `build_kpi_dashboard.py` — parameter definitions | 30 min |
| 1.3 | **Remove POD and Individual filter controls from Sheet 2** — `kpi_practice` has no these columns. Removing eliminates user confusion post-fix 1.1. | `build_kpi_dashboard.py` — `build_sheet2()` | 15 min |
| 1.4 | **Fix "Projects in Red %" tile on Sheet 1** — replace `total_projects_red` (count) with calculated field `projects_red_pct`. The calculated field already exists in the code; it needs to be referenced by the tile visual. | `build_kpi_dashboard.py` — Sheet 1 KPI tile definition | 30 min |
| 1.5 | **Fix Compliance % tile format on Sheet 3** — change `AVG(is_compliant)` to `AVG(is_compliant) * 100` in the calculated field, apply `#,##0.0'%'` format. Same fix for Avg Billable Util % tile if stored as decimal. | `build_kpi_dashboard.py` — Sheet 3 tile calculated fields | 30 min |
| 1.6 | **Add PS On-Time Delivery callout to Sheet 2** — large-format KPI display sourced from `kpi_snapshots.ps_on_time_pct`, visible only when LoB = PS or All, with "PS only — practice breakdown not available" label | `build_kpi_dashboard.py` — `build_sheet2()` | 1 hr |
| 1.7 | **Add project health stacked bar to Sheet 1** — 12-week stacked bar using `ps_projects_green + mc_projects_green`, `*_amber`, `*_red` columns. Green/amber/red CE brand colors. | `build_kpi_dashboard.py` — `build_sheet1()` | 1 hr |
| 1.8 | **Add cross-practice comparison bar charts to Sheet 2** — two horizontal bar charts (Billable Util % by Practice Alignment, Compliance % by Practice Alignment), 75% and 95% reference lines, bars colored red when below target | `build_kpi_dashboard.py` — `build_sheet2()` | 1.5 hrs |
| 1.9 | **Remove headcount bar chart from Sheet 2** — replace with the cross-practice comparison charts from 1.8 | `build_kpi_dashboard.py` — `build_sheet2()` | 15 min |
| 1.10 | **Remove staff detail table from Sheet 3 (broad-access version)** — until row-level security is configured, the table must not be in the publicly shared dashboard | `build_kpi_dashboard.py` — `build_sheet3()` | 15 min |
| 1.11 | **Add "Reporting Period" label with last-completed-week badge to each sheet header** — text visual showing "Showing: Week of [date]" using `MAX(week_start_date)` | `build_kpi_dashboard.py` — all three sheet builders | 1 hr |
| 1.12 | **Rename date control presets** — remove "This Week", rename "This Month" → "Last Full Month", rename "This Quarter" → "Quarter to Date (completed weeks)", add "Last Completed Week" as the first preset and default | `build_kpi_dashboard.py` — parameter control definitions | 30 min |

---

### Tier 2 — Calculated fields and view changes (medium effort, no new Lambda)

These require changes to PostgreSQL views or new calculated fields in SPICE, plus QuickSight rebuild. Estimated total: **4–6 hours.**

| # | Change | Where | Effort |
|---|--------|-------|--------|
| 2.1 | **Add `compliant_staff_count` column to `vw_practice_kpi_weekly`** — `ROUND(compliance_pct * headcount)` — enables correct weighted average compliance on Sheet 2 | PostgreSQL: `src/database/create_views.sql` | 1 hr (view update + SPICE refresh) |
| 2.2 | **Add `is_complete_week` flag to SPICE** — calculated field `week_start_date < DATE_TRUNC('week', CURRENT_DATE)` in the `kpi_snapshots` SPICE dataset. Apply as a dataset-level filter on all three sheets. | QuickSight SPICE dataset / `build_kpi_dashboard.py` | 30 min |
| 2.3 | **OKR quarterly step targets — Option B (QuickSight calculated fields)** — add `ifelse()` calculated fields to `kpi_snapshots` for `current_quarter_otd_target` and `current_quarter_duration_target` based on `EXTRACT(QUARTER, week_start_date)`. Use as reference line data in trend charts and as comparison value in KPI tiles. | `build_kpi_dashboard.py` — calculated field definitions | 1 hr |
| 2.4 | **Update Sheet 1 on-time delivery trend chart** — replace flat 90% reference line with a step-function reference using the quarterly target calculated field from 2.3. The step function requires a separate reference line per quarter range or a line chart series from `okr_quarterly_targets`. | `build_kpi_dashboard.py` — `build_sheet1()` | 1.5 hrs |
| 2.5 | **Verify and surface MC on-time delivery** — add MC On-Time Delivery KPI tile to Sheet 1. Confirm `mc_on_time_pct` is populated in `kpi_snapshots`. If NULL in recent weeks, investigate `kpi_snapshot.py`. | `kpi_snapshot.py` (audit) + `build_kpi_dashboard.py` | 1–2 hrs |
| 2.6 | **Update Sheet 2 Billable Utilization % tile to use weighted average** — `SUM(total_billable_hours) / SUM(total_capacity_hours) * 100` instead of `AVG(billable_util_pct)` | `build_kpi_dashboard.py` — `build_sheet2()` calculated field | 30 min |
| 2.7 | **Update Sheet 2 Compliance % tile to use weighted average** — `SUM(compliant_staff_count) / SUM(headcount) * 100` (requires Gap 2.1 to be deployed first) | `build_kpi_dashboard.py` — `build_sheet2()` | 30 min (depends on 2.1) |

---

### Tier 3 — New data pipeline work (higher effort, requires Lambda or view changes)

These require new PostgreSQL tables/views, Lambda changes, or new SPICE datasets. Estimated total: **6–10 hours.**

| # | Change | Where | Effort | Priority |
|---|--------|-------|--------|----------|
| 3.1 | **Create `okr_quarterly_targets` PostgreSQL table** — seed with KR2.1 and KR2.2 quarterly step values. Create SPICE dataset. Use as a joined reference for step-function overlays on trend charts (Option A from Gap 1). This is more maintainable than Option B calculated fields — targets can be updated without code changes. | PostgreSQL: new migration file + `coo-dashboards.yaml` (new SPICE dataset) | 2–3 hrs | Medium — do if there is appetite for maintainability; Option B from Tier 2 is sufficient for v1 |
| 3.2 | **Row-level security for Staff Detail table** — configure QuickSight RLS on `kpi_staff` dataset so each user's `user_name` JWT claim filters the table to their own row. Enables re-adding the staff table to a broadly shared version of the dashboard. | QuickSight RLS config + IAM / Cognito attribute mapping | 3–4 hrs | High if broad deployment is required; otherwise keep table in leadership version only |
| 3.3 | **Verify `mc_avg_duration_weeks` computation in `kpi_snapshot.py`** — if the column is not being populated, add the computation. This requires access to Jira MC project data with planned/actual dates. | `src/integrations/kpi_snapshot.py` | 1–2 hrs | Medium |
| 3.4 | **POD-level pre-aggregated KPI view** — create `vw_pod_kpi_weekly` joining `clockify_users.pod_assignment` with compliance and hours logic. Add SPICE dataset. Enable cross-POD trend comparisons. | PostgreSQL: `src/database/create_views.sql` + new SPICE dataset | 3–4 hrs | Nice-to-have v2 |
| 3.5 | **MIT-specific metrics** — add `mit_*` columns to `kpi_weekly_snapshots`, extend `kpi_snapshot.py` to compute MIT project health and utilization. Requires stakeholder confirmation that MIT has Jira-tracked projects with schedules. | `kpi_snapshot.py`, `vw_kpi_weekly_snapshots.sql`, `coo-dashboards.yaml` | 1–2 days | Nice-to-have v2 — blocked on stakeholder decision |

---

### Recommended sprint sequencing

**Sprint 1 (this week) — fix blockers, deliver usable dashboard:**
Complete all Tier 1 items (1.1–1.12) plus Tier 2 items 2.2 and 2.5 (MC on-time audit). These are pure QuickSight changes or minimal data layer changes. This sprint makes the dashboard usable: filters work, default date is correct, tiles are accurate, MC is visible, Sheet 2 has comparative value.

**Sprint 2 (next week) — add OKR milestone tracking and practice accuracy:**
Complete Tier 2 items 2.1, 2.3, 2.4, 2.6, 2.7. This sprint adds the quarterly step-function targets to the on-time delivery chart (the key OKR insight the COO needs) and fixes the weighted average calculations on Sheet 2.

**Sprint 3 (future) — infrastructure and v2 features:**
Tier 3 items. RLS for broad deployment, `okr_quarterly_targets` table for maintainability, POD-level view, MIT pending stakeholder confirmation.

