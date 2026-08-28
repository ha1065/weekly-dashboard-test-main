# KPI Tracking Dashboard — Usability & Strategic Assessment

**Dashboard:** kpi-tracking-dashboard-prod
**Built:** 2026-07-08
**Assessment date:** 2026-07-08
**Prepared by:** Product Analyst

---

## Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v1.0 | 2026-07-08 | Product Analyst | Initial assessment |

---

## Executive Summary

The KPI Tracking Dashboard was built today and covers the right strategic territory — three sheets aligned to three personas, the correct KPI set, and reference lines anchored to OKR targets. However, it has one critical functional defect and several significant structural gaps that collectively prevent it from being usable as-is.

**The critical defect:** Filter controls on Sheet 2 and Sheet 3 are decorative. Users can select a Line of Business, Practice, POD, or Individual, and nothing changes on screen. This is the primary blocker.

**The structural gaps:** Sheet 1 (OKR Scorecard) has no filters wired to it at all. The time grain control exists on all three sheets but does not aggregate data — it only changes a label. The default state shows unfiltered totals, which actually satisfies the stakeholder's "start at highest level" requirement, but only by accident. Sheet 2 redundantly duplicates Sheet 3 visuals without adding practice-level insight. Sheet 3's staff table is ungated, exposing every individual's hours and compliance status to anyone with dashboard access.

**What works:** The KPI tile selection is correct and OKR-aligned. Reference lines at 75%, 95%, and 90% are in the right places. The trend charts are structurally sound. The data is loading. The CE brand theme is applied.

**Bottom line:** Fix the filter wiring first. Then address the sheet structure and data gaps. The dashboard is not production-ready today in its current state.

---

## 1. Usability Assessment

### 1.1 Default State

**Rating: Acceptable with caveats.**

The stakeholder requirement is "start at the highest level, filter down." The current default state does show company-wide aggregates on Sheet 1 — there are no filters applied, so all rows are included. This is correct behavior for the OKR Scorecard.

On Sheet 2 and Sheet 3, the default is also "all data" because the filter controls don't work. This accidentally satisfies the requirement, but for the wrong reason. When the filters are fixed, the default state must be explicitly validated — each parameter defaults to `'All'` per the code, which is correct, but the FilterGroups use `FILTER_ALL_VALUES` with `CONTAINS` operator. When the filter is repaired, the default `'All'` string will need to map to "show everything" rather than filtering for rows where the column value equals the literal string "All."

**Specific issue:** The `pLob`, `pPracticeAlignment`, `pPod`, and `pStaff` parameters all default to the static string `'All'`. The FilterGroups use `MatchOperator: CONTAINS` and `SelectAllOptions: FILTER_ALL_VALUES`. This means in the "show everything" default state, the filter is relying on `FILTER_ALL_VALUES` to pass all rows through — which is correct QuickSight behavior when no value is explicitly selected. However, the parameter control dropdowns present a static default of `'All'` as a selectable string, not as a true "Select All" state. When a user opens the dashboard, they will see "All" pre-selected in each dropdown, which looks correct but may not behave correctly depending on whether QuickSight interprets the parameter value `'All'` as a select-all or as a literal match. This needs to be verified after the filter fix.

### 1.2 Filter Cascade Logic

**Rating: Structurally wrong — POD does not belong in the practice hierarchy.**

The confirmed filter hierarchy is:

```
Line of Business → Practice Alignment → POD → Individual Staff Member
```

This hierarchy has a fundamental data problem: **POD is not a sub-dimension of Practice Alignment in Cloudelligent's org structure.** POD (Alpha, Bravo, Charlie, A2Z, Free Agent) is a delivery team assignment that cuts across practices. A staff member in the PS practice can be in any POD. A member of the DevOps practice alignment and a member of the Cloud Foundations practice alignment can both be in the Alpha POD.

The cascade logic as built implies that selecting "Professional Services" then selecting "Alpha" would narrow to PS staff in the Alpha POD. This is a valid compound filter, but presenting it as a hierarchy suggests that PODs sit under Practice Alignments, which is misleading. The correct mental model is:

- **LoB → Practice Alignment** is a true hierarchy (Practice Alignment is a sub-dimension of LoB)
- **POD** is an independent organizational dimension, not a child of Practice Alignment
- **Individual** is filtered by whichever dimensions are selected above

As built, the four dropdowns are presented left-to-right as if they are a cascade, but they are actually independent parallel filters. The UI implies a dependency that doesn't exist in the data. This won't cause wrong numbers (any combination of the four filters will narrow correctly), but it will cause user confusion — a Practice Lead selecting "PS" then looking at the POD dropdown will see all PODs, not just PODs that contain PS staff.

**Recommendation:** Keep all four controls but label them as parallel filters, not a cascade. Add a visual separator or grouping to indicate they operate independently. The order LoB → Practice → Individual is a natural hierarchy; POD sits alongside, not beneath, Practice.

Additionally, the **kpi_practice dataset does not have a POD column** (`vw_practice_kpi_weekly` schema: `line_of_business`, `practice_alignment`, `week_start`, `headcount`, `billable_util_pct`, `compliance_pct`, etc. — no `pod_assignment`). The POD filter control on Sheet 2 references parameter `pPod`, but there is no FilterGroup wiring `pPod` to the `kpi_practice` dataset. Even after fixing the filter issue, POD filtering will have no effect on Sheet 2 visuals because the underlying data doesn't have that dimension. The POD control on Sheet 2 should be removed or the dataset needs a join.

### 1.3 Time Grain Control

**Rating: Not functional as designed — the control exists but doesn't aggregate.**

The time grain control (`pTimeGrain`: Week / Month / Quarter / YTD) appears on all three sheets. On Sheet 1, it drives a calculated field `time_grain_label` that reformats the x-axis label of the trend charts. It does **not** actually aggregate data differently — the trend charts always show weekly rows regardless of what the user selects. Selecting "Month" will relabel the axis but still plot one data point per week.

True time grain aggregation (collapsing weekly rows into monthly or quarterly aggregates) would require either:
1. Calculated fields that bucket `week_start_date` into the selected grain and re-aggregate, or
2. Separate datasets or pre-aggregated views per grain

What was built is a presentation label change, not a data aggregation change. For the COO use case this matters significantly — "show me Q2 compliance rate" should return a single number representing the average of the Q2 weekly values, not 13 individual data points labeled "Quarter."

On Sheets 2 and 3, the time grain control has no effect at all — there is no calculated field referencing `pTimeGrain` in those sheets' visuals. The control is displayed but wired to nothing.

**Assessment:** The time grain control is cosmetic on Sheet 1 and inert on Sheets 2 and 3.

### 1.4 Sheet Structure

**Rating: Three sheets is the right number, but Sheet 2 and Sheet 3 are too similar.**

Three sheets matching three personas is correct in principle:

| Sheet | Intended Persona | Assessment |
|-------|-----------------|------------|
| Sheet 1 — OKR Scorecard | COO / Executive | Correctly designed. KPIs match OKR KRs. Trend charts are appropriate. |
| Sheet 2 — Practice Scorecard | Practice Leads | Redundant with Sheet 3. Shows practice-level aggregates, but the data it uses (`kpi_practice`) doesn't have significantly more insight than Sheet 3. |
| Sheet 3 — Staff Detail | Staff / Managers | Correctly positioned for drill-down, but ungated individual data is a privacy concern. |

The naming is clear and accurate. "OKR Scorecard," "Practice Scorecard," and "Staff Detail" correctly describe the content of each sheet.

The main structural problem is that Sheet 2 is thin. It shows three KPI tiles (Headcount, Billable Util %, Compliance %) and two trend charts that are nearly identical to what Sheet 3 shows when filtered by Practice Alignment. The original proposal called for Sheet 2 to show on-time delivery %, active projects, and project health (green/amber/red counts) — practice-level project delivery metrics that Sheet 3 cannot show because the `kpi_staff` dataset has no project health data. As built, Sheet 2 omits these project delivery metrics and ends up being a less detailed version of Sheet 3.

### 1.5 KPI Tile Design

**Rating: Good on Sheet 1; thin on Sheets 2 and 3.**

**Sheet 1 KPI tiles:**
- Billable Utilization %, Timesheet Compliance %, PS On-Time Delivery %, Open Escalations, Active Resources, Avg Engagement Duration (weeks), Projects in Red % — this is the correct set for an OKR-level scorecard
- On-Time Delivery and Avg Engagement Duration have target values wired — comparison will show vs-target delta once the correct target columns exist
- Open Escalations and Active Resources have no targets — correct, these are context metrics
- Projects in Red % uses raw `total_projects_red` count rather than the percentage formula — the KPI tile will show an integer (e.g., "3") not a percentage (e.g., "8%"). A calculated field `projects_red_pct` was defined in the code but not referenced in the KPI tile visual

**Sheet 2 KPI tiles:**
- Headcount, Billable Util %, Compliance % — correct but minimal
- Missing: Total Billable Hours, On-Time Delivery % per practice (the proposal specified 5 KPI tiles including these)
- No OKR target comparisons on any Sheet 2 tile

**Sheet 3 KPI tiles:**
- Headcount, Avg Billable Util %, Compliance %, Total Billable Hours — appropriate for staff/manager view
- Compliance % is calculated as `AVG(is_compliant)` where `is_compliant` is 0 or 1 — this will produce a decimal between 0 and 1, not a percentage. The tile will show "0.72" not "72%." This needs a format or calculation fix.

### 1.6 Visual Types

**Rating: Appropriate choices for the data stories.**

Line charts for time-series trends: correct. Horizontal bar chart for POD compliance: correct — it reads cleanly for a small number of categories (5 PODs). Staff detail as a table: appropriate for the individual lookup use case. Trend charts with reference lines at OKR targets: correct and well-executed.

What's missing that the proposal specified:
- No stacked bar chart showing project health (Green/Amber/Red) by week on Sheet 1
- No donut chart for project health distribution on Sheet 2
- No bar chart comparison of individual staff compliance (Sheet 3 shows POD-level only)

These are gaps against the proposal, not wrong choices — the data for some of these (per-practice project health) was in the "data gap" category. The missing visuals represent scope that couldn't be built without the `kpi_snapshots` project health columns being surfaced properly.


---

## 2. Strategic Analysis

### 2.1 OKR Alignment

The dashboard was built to support KR5.1 directly ("real-time CEO/COO decision visibility") and to surface progress on KR2.1, KR2.4, and other delivery KRs. Here is the honest assessment of what is and is not visible.

**KRs with direct dashboard coverage:**

| KR | What's Required | What's Built | Gap |
|----|----------------|--------------|-----|
| KR2.1 — On-Time Delivery (30% → 90%) | Trend line showing % vs. quarterly step targets | PS on-time trend chart on Sheet 1 with 90% target reference line | Target is flat 90% — quarterly step targets (Q1: 45%, Q2: 60%, Q3: 75%) are not shown. MC on-time delivery is missing entirely. |
| KR2.4 — Projects in Red (<10%) | Red/Amber/Green count + % vs. 10% target | KPI tile for "Projects in Red %" on Sheet 1, but shows raw count not % | Calculated field `projects_red_pct` was built but not connected to the tile. No project health trend chart. |
| KR5.1 — Data hygiene / real-time visibility | Compliance %, utilization %, time reporting coverage | Compliance % and utilization % tiles and trends on all 3 sheets | Compliance on Sheet 3 formats as decimal not percentage. Time grain doesn't aggregate. |
| KR2.2 — Avg Engagement Duration (15.2 → 5 weeks) | Trend showing avg duration vs. quarterly targets | Sheet 1 KPI tile for Avg Engagement Duration vs. target | PS only. MC excluded. Quarterly step targets not shown (12 → 10 → 7 → 5 wks). |

**KRs with no dashboard coverage (confirmed out of scope):**

| KR | Why Not Covered |
|----|----------------|
| KR2.3 — Kiro adoption 90% | No Kiro usage data in this pipeline |
| KR5.2 — AI certification 95% | No LMS/certification data |
| KR5.3 — Org redesign (max 8 direct reports) | No org chart data |
| KR5.4 — Offshore talent elevation | No role assignment data |
| KR3.4 — Expansion signals 50% | No HubSpot data |
| KR6.1/6.2/6.4 — Product revenue, margins | No finance system data |

These are correctly out of scope. The proposal was explicit about this.

**The most significant OKR visibility gap that is fixable:** The quarterly step targets for KR2.1 (45/60/75/90%) and KR2.2 (12/10/7/5 weeks) are not visible. The trend charts show a flat target reference line at the Q4 final target. This means in Q1 or Q2, the COO cannot tell if current performance is on track for the quarter — they can only see how far they are from the final Q4 goal. Adding a step-function target line using the `okr_quarterly_targets` reference table (which was proposed in the data gap section) would fix this.

### 2.2 Persona Coverage

**COO / Executive (Sheet 1):** Partially served. The KPI tiles are right. The trend charts are right. The time grain control doesn't aggregate, which means the COO can't easily answer "What was our average compliance rate for Q2?" without manually counting weeks. The lack of quarterly step targets on the on-time delivery chart means the COO can see the direction of travel but not whether they're on track for this quarter's intermediate milestone.

**Practice Leads (Sheet 2):** Under-served. The three KPI tiles (Headcount, Billable Util %, Compliance %) are meaningful, but the proposal specified five tiles including On-Time Delivery % and Total Billable Hours. More importantly, Sheet 2 has no project delivery data — a Practice Lead cannot see how many of their projects are Green vs. Red, or what their practice's on-time delivery rate is. These are arguably the most important metrics for a Practice Lead taking corrective action. The sheet as built shows workforce metrics only.

**Staff / Team Members (Sheet 3):** Over-served and under-protected. The staff detail table shows every individual's name, hours, billable hours, utilization %, and compliance status. If this dashboard is intended for broad staff access (the proposal's Option B rationale), this table exposes one staff member's performance data to every other staff member. That is a privacy problem. Staff should see practice/POD aggregate data, not a ranked list of their colleagues' utilization rates.

At the same time, Staff are missing the one thing they most need: "How is my practice doing this week vs. target?" The individual-level table answers "how am I doing" but doesn't provide the practice context. The bar chart showing compliance by POD is useful, but the trend chart repeats what Sheet 2 already shows.

### 2.3 Decision Support Gap Analysis

**What each persona can decide today with the dashboard:**

| Persona | Decisions Enabled | Decisions Still Blind |
|---------|------------------|-----------------------|
| COO | "Is overall utilization above/below 75% this week?" "Is compliance tracking above 95%?" "How many open escalations are there?" | "Are we on track for Q2 on-time delivery milestone?" "Is MC or PS the underperformer?" "Which quarter did compliance first drop below target?" "Is engagement duration improving at the right rate?" |
| Practice Lead | "What is my practice's utilization % right now?" "What is my practice's headcount?" | "How many of my projects are Red vs. Green?" "What is my practice's on-time delivery rate?" "How does my practice compare to the company average?" "Which staff in my practice are non-compliant?" |
| Staff | "What is compliance across PODs?" "What is my billable util % this week?" | "How is my practice trending vs. target this month?" "Am I above or below the practice average?" "Has POD compliance been improving?" |

### 2.4 Missing Data Stories

These are analytically valid questions the data supports but the dashboard doesn't surface:

1. **MC performance visibility.** The `kpi_snapshots` dataset has `mc_on_time_pct`, `mc_billable_hours`, `mc_active_projects`, and `mc_projects_red/green/amber` columns. None of these appear on the dashboard. Sheet 1 shows PS on-time delivery but not MC. The COO cannot see how the MC practice is performing at a delivery level from this dashboard.

2. **Practice comparison side-by-side.** The `kpi_practice` dataset has billable utilization and compliance by practice alignment. A bar chart showing the current week's utilization across all practices simultaneously (DevOps: 82%, Cloud Foundations: 71%, Professional Services: 78%) would immediately surface which practices need attention. Currently the data exists but is only shown as a time trend — not as a cross-practice comparison at a point in time.

3. **Compliance trend by individual POD over time.** The POD compliance bar chart on Sheet 3 shows a single-period snapshot. A 12-week trend line per POD would show whether a POD that's below target is improving or declining — the difference between "this POD needs a conversation today" vs. "this POD has been declining for 6 weeks and needs a structural fix."

4. **Hours logged vs. capacity.** The `kpi_staff` dataset has `hours_logged`, `billable_hours`, and `weekly_capacity`. The gap between logged hours and capacity (non-compliance) is not surfaced visually. A stacked bar showing "logged vs. capacity" per POD per week would be more intuitive than a compliance percentage for staff to understand the operational picture.

5. **YTD hours actuals.** Total billable hours year-to-date by practice is a standard management metric. The data exists in the `kpi_practice` dataset (sum of `total_billable_hours` year-to-date) but isn't surfaced as a KPI tile or chart.

### 2.5 Data Hierarchy Gap

The stakeholder-confirmed hierarchy is **LoB → Practice Alignment → POD → Individual**. As noted in Section 1.2, POD does not sit below Practice Alignment in Cloudelligent's actual organizational structure — it is a parallel dimension.

The `kpi_practice` dataset is built from `vw_practice_kpi_weekly`, which groups by `(line_of_business, practice_alignment, week_start)`. It has no POD column. This means Sheet 2 (which uses `kpi_practice`) cannot filter by POD regardless of the filter wiring — the data isn't structured that way.

The `kpi_staff` dataset is built from `vw_staff_kpi_weekly`, which has all four dimensions: `line_of_business`, `practice_alignment`, `pod_assignment`, `user_name`. Sheet 3 can correctly filter by all four.

**Practical consequence:** The filter hierarchy as presented implies that a Practice Lead can see "my practice, broken down by POD." This is not possible on Sheet 2 with the current data model. It is possible on Sheet 3. If the filter hierarchy is a firm requirement, `vw_practice_kpi_weekly` needs a redesign to add a POD dimension — or Sheet 2 needs to be sourced from the staff dataset with appropriate aggregation.

---

## 3. Root Cause: Non-Functional Filter Controls

### Why the filters don't work — explained plainly

Think of the dashboard as a TV with a remote control. The filter dropdowns are the remote control buttons. The data visuals are the TV channels. For pressing a button on the remote to change what's on the TV, there needs to be a **wire** connecting the button to the TV's input system.

In QuickSight, this wire is called a **FilterGroup**. Each FilterGroup says: "When parameter X has a value, apply that value as a filter to dataset Y, and apply that filter to visual Z on sheet W."

**What was built:** The filter buttons (parameter controls) were created correctly. They appear on screen, accept user input, and store the selected value in a parameter (e.g., `pLob = "Professional Services"`). The filter specifications (FilterGroups) were also created — they describe which column to filter on and which sheet to apply the filter to.

**The missing connection:** The FilterGroups define the filter logic but **do not reference the parameter**. A FilterGroup that says "filter `line_of_business` to contain X" — where X is a hardcoded value or a `FILTER_ALL_VALUES` pass-through — will either filter to a fixed value or pass all values through regardless of what the user selects. What's needed is a FilterGroup that says "filter `line_of_business` to equal **whatever the user selected in the `pLob` parameter**."

In QuickSight's API, the way you connect a parameter to a filter is through a `CustomFilterConfiguration` or `CustomFilterListConfiguration` that includes a `ParameterName` field pointing at the parameter. The code uses `FilterListConfiguration` with `FILTER_ALL_VALUES` — this tells QuickSight "show all values, don't filter" and it never reads the parameter value.

**Result:** Every filter control on Sheet 2 and Sheet 3 is visually present and appears interactive, but selecting any value has no effect on the visuals. The data always shows the full unfiltered dataset.

**What the fix requires:** Each FilterGroup needs its `Configuration` changed from `FilterListConfiguration` with `SelectAllOptions: FILTER_ALL_VALUES` to a `CustomFilterConfiguration` with `MatchOperator: EQUALS` and `ParameterName: <parameter-name>`. Additionally, a "show all" condition needs to be handled — typically by setting the parameter default to empty (not `'All'`) and using `ValueWhenUnset: RECOMMENDED_VALUE` to pass all rows through when nothing is selected.

This is a code change in `build_kpi_dashboard.py`, not a data change. The datasets and SPICE ingestions are fine.


---

## 4. Recommended Redesign

### 4.1 Sheet Structure — Keep Three Sheets, Rebalance Content

The three-sheet structure is correct. The changes below rebalance each sheet to better serve its persona and eliminate redundancy between Sheets 2 and 3.

---

**Sheet 1 — OKR Scorecard** *(no structural change — fix KPI tile formulas and add MC visibility)*

Default state: All company-level data, most recent week.

Recommended changes:
- Fix "Projects in Red %" tile to use the `projects_red_pct` calculated field (already exists in the code, just not wired to the tile)
- Add an MC On-Time Delivery tile alongside the PS tile, or replace "PS On-Time Delivery %" with a combined company-level on-time rate
- Replace the flat 90% reference line on the on-time delivery chart with a step-function overlay showing Q1/Q2/Q3/Q4 quarterly targets (45%/60%/75%/90%)
- Add a small project health stacked bar (Green/Amber/Red count by week, last 12 weeks) in the bottom zone — the `total_projects_green/amber/red` columns exist in `kpi_snapshots`
- The time grain control can remain but should be labeled "Display grain" with a tooltip noting it reformats the axis (not an aggregate filter) until true aggregation is implemented

---

**Sheet 2 — Practice Scorecard** *(significant redesign — remove what duplicates Sheet 3, add what only Practice data can show)*

Default state: All practices, company-wide. Practice Lead selects their LoB and Practice Alignment to narrow.

Filter controls: LoB (top-left) and Practice Alignment (next to it). Remove POD and Individual from Sheet 2 — the `kpi_practice` dataset doesn't have these dimensions, so those controls are misleading. Retain Time Grain.

KPI tiles (replace current 3 with 5 meaningful ones):
1. Headcount — same as now
2. Billable Utilization % — same as now, add 75% target comparison
3. Compliance % — same as now, add 95% target comparison
4. Total Billable Hours (week/period) — currently missing, source from `total_billable_hours`
5. Total Capacity Hours — provides context for utilization; source from `total_capacity_hours`

Visuals (replace current trend charts with cross-practice comparison view):
- **Bar chart: Billable Utilization % by Practice Alignment, current week** — this is the highest-value visual for a Practice Lead. Shows all practices side-by-side with a 75% target line. Immediately surfaces which practices are under target.
- **Bar chart: Compliance % by Practice Alignment, current week** — same pattern, 95% target line
- **Line chart: Billable Utilization % trend, last 12 weeks, colored by Practice Alignment** — keep from current build, useful for trending
- Remove the headcount bar chart (not a performance metric; headcount is already in the KPI tile)

This redesign makes Sheet 2 the "practice health comparison" view — you can see all practices at once and understand who is on track vs. who needs attention.

---

**Sheet 3 — Staff Detail** *(targeted changes — restrict table visibility, improve summary value)*

Default state: All staff, all practices, current week. A manager selects LoB/Practice/POD to scope their view; an individual selects their own name.

Filter controls: Keep all four (LoB, Practice Alignment, POD, Individual). These are independent parallel filters, not a cascade — reorder to LoB | Practice Alignment | Individual | POD so that the most commonly used filters come first. POD is a secondary filter for managers who organize by team.

KPI tiles: Keep current four (Headcount, Avg Billable Util %, Compliance %, Total Billable Hours). Fix the Compliance % tile to display as a percentage (multiply `is_compliant` average by 100 or apply percent format).

Visuals:
- **POD Compliance % bar chart** — keep, but fix the reference line value. The current code draws the target line at `0.95` (a raw decimal) when the axis shows values as averages of the 0/1 `is_compliant` column, also between 0 and 1. The label says "95%" but the line is at the correct position — this is visually correct but the label is misleading without proper percentage formatting. Apply consistent percentage formatting.
- **Billable Util % trend by Practice** — keep as useful context
- **Staff detail table** — restrict access. This table should only be visible to the viewer's own row, or it should be removed from the broadly-shared dashboard version and kept only in the admin/leadership-facing view. At minimum, do not include this table in any version shared company-wide until row-level security is configured. For today, remove the table from the dashboard and add a note that individual drill-down requires the COO Operational Dashboard.

### 4.2 Filter Control Redesign

The filter controls need two changes:

**1. Wire parameters to FilterGroups correctly.**

Replace `FilterListConfiguration` with `CustomFilterConfiguration` in each FilterGroup:

```python
# Current (broken — ignores parameter value)
'Configuration': {
    'FilterListConfiguration': {
        'MatchOperator': 'CONTAINS',
        'SelectAllOptions': 'FILTER_ALL_VALUES',
        'NullOption': 'ALL_VALUES',
    }
}

# Fixed (reads parameter value, passes all rows when parameter is empty)
'Configuration': {
    'CustomFilterConfiguration': {
        'MatchOperator': 'EQUALS',
        'ParameterName': 'pLob',        # <- links to the parameter
        'NullOption': 'ALL_VALUES',
        'SelectAllOptions': 'FILTER_ALL_VALUES',
    }
}
```

Set parameter defaults to `''` (empty string) rather than `'All'`. When the parameter is empty, `FILTER_ALL_VALUES` passes all rows through. When the user selects a value, `EQUALS` filters to that value. The dropdown control should use `SelectAllOptions: VISIBLE` to show a "Select All" option at the top.

**2. Remove controls that have no data backing.**

- Remove POD control from Sheet 2 — `kpi_practice` has no `pod_assignment` column
- Remove Individual control from Sheet 2 — `kpi_practice` aggregates by practice, not by person

### 4.3 Default State Per Sheet

| Sheet | Default Parameter Values | What User Sees |
|-------|--------------------------|----------------|
| Sheet 1 — OKR Scorecard | No filters (time grain = Week) | Company-wide KPIs for most recent week, full YTD trend charts |
| Sheet 2 — Practice Scorecard | LoB = All, Practice = All, Time Grain = Week | All practices side-by-side in bar charts; company totals in KPI tiles |
| Sheet 3 — Staff Detail | LoB = All, Practice = All, POD = All, Individual = All, Time Grain = Week | All-staff aggregate KPIs; POD compliance bar; practice utilization trend |

This satisfies the stakeholder requirement: every sheet opens at the highest aggregation level, and users narrow using the controls.

### 4.4 Visuals to Add, Remove, or Move

| Visual | Action | Reason |
|--------|--------|--------|
| Project health stacked bar (Green/Amber/Red by week) | Add to Sheet 1 | KR2.4 requires visibility into project health trend; data exists in `kpi_snapshots` |
| MC On-Time Delivery trend | Add to Sheet 1 | MC is a major practice; currently invisible at the OKR level |
| Quarterly step-function target overlay on on-time delivery chart | Add to Sheet 1 | COO needs to know if current performance is on track for this quarter's milestone, not just the Q4 target |
| Cross-practice utilization comparison bar (current week) | Add to Sheet 2 | Highest-value view for Practice Leads; makes inter-practice comparison immediate |
| Headcount bar chart by Practice Alignment | Remove from Sheet 2 | Headcount is in the KPI tile; the bar chart adds noise without insight |
| Staff detail table | Remove from Sheet 3 (broad access version) | Privacy concern; individual data visible to all staff. Keep in leadership version. |
| Compliance % KPI tile (Sheet 3) | Fix format | Currently shows 0.72 instead of 72% |
| Projects in Red % KPI tile (Sheet 1) | Fix formula | Currently shows raw count; should use `projects_red_pct` calculated field |

---

## 5. Priority Fix List

These are ordered by impact and by blocking dependency — fixes that unblock other fixes come first.

| # | Fix | Why | Effort |
|---|-----|-----|--------|
| 1 | **Wire FilterGroups to parameters** — replace `FilterListConfiguration / FILTER_ALL_VALUES` with `CustomFilterConfiguration / ParameterName` on all Sheet 2 and Sheet 3 FilterGroups | This is the confirmed blocker. Until this is fixed, the dashboard cannot be used for any filtered view. Every other improvement is irrelevant until filtering works. | Medium — ~2 hrs (code change in `build_kpi_dashboard.py`, rebuild, redeploy) |
| 2 | **Remove POD and Individual controls from Sheet 2** — `kpi_practice` has no `pod_assignment` or `user_name` columns; these controls will always be no-ops on Sheet 2 | Prevents user confusion after fix #1. A Practice Lead selecting a POD on Sheet 2 and seeing no change will think filtering is still broken. | Low — ~15 min (remove two control entries from `build_sheet2()`) |
| 3 | **Fix Compliance % display on Sheet 3** — `AVG(is_compliant)` returns 0.0–1.0; apply ×100 in calculated field or percent format | The KPI tile currently shows "0.72" which is unreadable as a business metric. Users will not trust the data. | Low — ~30 min (add calculated field or column format) |
| 4 | **Fix Projects in Red % tile on Sheet 1** — connect `projects_red_pct` calculated field to the KPI tile instead of raw `total_projects_red` count | KR2.4 target is percentage-based (<10%). Showing a raw count of 3 vs. a target of 10% is not comparable. The calculated field already exists in the code. | Low — ~30 min (change the Values field reference in the KPI tile visual) |
| 5 | **Set parameter defaults to empty string, not `'All'`** — validate that after fix #1, the default state shows all data rather than filtering for rows where the column equals the literal string "All" | After the filter wiring fix, the default `'All'` string may match nothing (if no rows have `line_of_business = 'All'`) and the dashboard will appear empty. Must be tested and fixed in the same deployment. | Low — ~15 min (change `DefaultValues: StaticValues: ['All']` to `DefaultValues: StaticValues: ['']` or use `ValueWhenUnset` only) |
| 6 | **Add MC On-Time Delivery to Sheet 1** — add a `mc_on_time_pct` KPI tile or combine PS + MC into a single company-level on-time rate using available columns | The COO's KR2.1 is a company-level target, not PS-only. The current Sheet 1 only shows PS performance. MC accounts for a significant share of delivery. | Medium — ~1 hr (add KPI tile and/or modify trend chart to include MC series) |
| 7 | **Add project health stacked bar to Sheet 1** — use `total_projects_green`, `total_projects_amber`, `total_projects_red` columns from `kpi_snapshots` for a 12-week bar chart | KR2.4 requires tracking project health trend. The data exists; it just isn't on the dashboard. | Medium — ~1 hr (add BarChartVisual to `build_sheet1()`) |
| 8 | **Replace headcount bar with cross-practice utilization comparison on Sheet 2** — horizontal bar chart of current-week billable util % by practice alignment, with 75% reference line | This is the highest-value view for Practice Leads. Makes Sheet 2 distinctly useful vs. Sheet 3 instead of a subset of it. | Medium — ~1.5 hrs (replace existing visual, verify data) |
| 9 | **Add quarterly step-function targets to on-time delivery trend chart** — requires the `okr_quarterly_targets` reference table (proposed in data gap §6) | Gives the COO milestone-aware visibility instead of just "how far from the Q4 goal." Currently the trend chart shows a flat 90% target whether it's Q1 or Q4. | High — ~3–4 hrs (requires data work: create `okr_quarterly_targets` table, seed Q1–Q4 targets, create SPICE dataset, add calculated reference lines to chart) |
| 10 | **Remove staff detail table or gate it behind row-level security** | Privacy: individual utilization and compliance data should not be visible to all staff in a broadly shared dashboard. | High (if doing RLS properly) / Low (if simply removing the table for now) — removing the table takes ~15 min; RLS setup takes 3–4 hrs |

---

## Summary of Assessment Findings

| Area | Status | Blocking? |
|------|--------|-----------|
| Filter controls functional | ❌ Broken | Yes — primary defect |
| Default state (company-wide) | ✅ Correct (by accident) | No |
| KPI tile selection (Sheet 1) | ✅ Correct | No |
| KPI tile formulas | ⚠️ Two errors (Projects in Red %, Compliance % format) | No — readable but inaccurate |
| Time grain aggregation | ❌ Cosmetic only, not functional | Partial — trend charts still useful |
| Sheet 2 persona coverage | ⚠️ Thin — missing project delivery KPIs | No |
| Sheet 3 privacy | ❌ Staff table is ungated | Yes (if deployed broadly) |
| OKR KR coverage | ⚠️ MC excluded; quarterly step targets missing | No |
| MC visibility | ❌ Absent from all sheets | No |
| Data layer (SPICE datasets) | ✅ Ingested and loading | No |
| CE brand theme | ✅ Applied | No |
| Reference lines at OKR targets | ✅ Correct | No |

**The dashboard is not production-ready today. Fixes #1 through #5 in the Priority Fix List above are the minimum required before sharing with any stakeholder. Fixes #6 through #8 should follow in the same sprint. Fixes #9 and #10 can be planned for the next sprint.**

---

*Assessment prepared: 2026-07-08 | KPI Tracking Dashboard v1 (built 2026-07-08)*
