# Weekly Reporting Dashboard — Software Requirement Specification

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v1.1 | 2026-06-08 | Product Analyst | Added Tab 17 — Organizational KPI Scorecard (FR-17-001, FR-17-002). Source: COO decision — KPI definitions confirmed 2026-06-08. |
| v1.0 | 2026-06-05 | Product Analyst | Initial specification |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Proposed Solution Overview](#3-proposed-solution-overview)
4. [Design Principles](#4-design-principles)
5. [Scope](#5-scope)
6. [Tab Functional Requirements](#6-tab-functional-requirements)
   - [Tab 1 — Weekly Operations Summary](#tab-1--weekly-operations-summary)
   - [Tab 2 — PS Project Status](#tab-2--ps-project-status)
   - [Tab 3 — PS Profitability](#tab-3--ps-profitability)
   - [Tab 4 — MC Service Delivery](#tab-4--mc-service-delivery)
   - [Tab 5 — Missing Time Report](#tab-5--missing-time-report)
   - [Tab 6 — Resource Forecast](#tab-6--resource-forecast)
   - [Tab 7 — Resource Capacity](#tab-7--resource-capacity)
   - [Tab 8 — PS Delivery Analysis](#tab-8--ps-delivery-analysis)
   - [Tab 9 — Non-Billable Analysis](#tab-9--non-billable-analysis)
   - [Tab 10 — MC V2 Audit](#tab-10--mc-v2-audit)
   - [Tab 11 — Project Hours Trend](#tab-11--project-hours-trend)
   - [Tab 12 — Escalations](#tab-12--escalations)
   - [Tab 13 — Productive Utilization](#tab-13--productive-utilization)
   - [Tab 14 — Project Time Detail](#tab-14--project-time-detail)
   - [Tab 15 — Customer Status Assignments](#tab-15--customer-status-assignments)
   - [Tab 16 — Project Runway](#tab-16--project-runway)
   - [Tab 17 — Organizational KPI Scorecard](#tab-17--organizational-kpi-scorecard)
7. [Retired Tabs](#7-retired-tabs)
8. [Cross-Cutting Requirements](#8-cross-cutting-requirements)
9. [Data Source Mapping](#9-data-source-mapping)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Edge Cases & Failure Scenarios](#11-edge-cases--failure-scenarios)
12. [Assumptions](#12-assumptions)
13. [Open Questions](#13-open-questions)

---

## 1. Executive Summary

**Product:** Weekly Reporting Dashboard (Streamlit + QuickSight)
**Business Goal:** Provide the COO and operations team with a tactical, high-granularity operations tool that sits one level below the COO Operational Analysis dashboard in a three-tier reporting model.
**Target Users:** COO, delivery managers, POD leads, practice leads, operations analysts
**Expected Impact:**
- Single source of truth for weekly operational decision-making across PS, MC, and non-billable activity
- Eliminates dependency on PM-uploaded forecasts for capacity decisions (capacity model is authoritative)
- Enables proactive identification of compliance gaps, resource conflicts, and profitability risks before they escalate to the COO dashboard
- Directly supports OKR KR5.1 (95%+ data hygiene, real-time COO decision visibility)

---

## 2. Problem Statement

The current Weekly Reporting dashboard has accumulated inconsistencies over time:

- **Employee-attribute-based classification** (relying on user fields) instead of project-based classification, causing misalignment with the COO dashboard's `ps_project_mapping`-driven data
- **PS resource definition is undefined** — no consistent field distinguishes PS vs MC vs Internal staff, leading to incorrect headcount and utilization denominators
- **PM forecast is treated as authoritative** for capacity planning, despite known data quality issues; the capacity model (`ps_resource_forecast_v2`) is ignored or used inconsistently
- **Missing time compliance** has no historical view — only current-week data is visible, preventing trend analysis or quarterly accountability
- **Profitability data is absent** — onshore/offshore mix, contractor vs FTE cost, and SOW burn are not tracked in a unified view
- **MC V2 methodology compliance** (Confluence artifact verification) is not automated or tracked
- **Several tabs are duplicated or misaligned** with the COO dashboard's data model (e.g., Resource Conflicts, Forecast vs Actuals as separate tabs)

---

## 3. Proposed Solution Overview

Redesign the Weekly Reporting Dashboard as a 16-tab tactical operations tool that:

1. Uses **identical data sources and classification logic** as the COO Operational Analysis dashboard (project-based via `ps_project_mapping`, not employee-attribute-based)
2. Defines PS resources via a new `practice_area` field on `clockify_users` (`PS` / `MC` / `Both` / `Internal` / `Exempt`)
3. Makes the **capacity model (`ps_resource_forecast_v2`) authoritative** for all forward-looking capacity and forecast views; PM forecasts shown as a comparison signal only
4. Adds missing operational capabilities: profitability tracking, historical compliance trends, MC V2 audit, project runway, and productive utilization history
5. Consolidates redundant tabs (Resource Conflicts → Resource Capacity, Forecast vs Actuals → Resource Forecast)

---

## 4. Design Principles

| Principle | Definition |
|-----------|------------|
| Project-based classification | All hours categorization uses `ps_project_mapping.category` (or `ps_project_status.category` as fallback), not employee attributes |
| PS resource definition | A user is a PS resource if `clockify_users.practice_area IN ('PS', 'Both')` |
| Time compliance | A user is compliant for a week if their total logged hours for that week > 0 |
| Utilization compliance | A user meets the billable utilization target if billable hours ≥ 75% of their weekly capacity |
| Capacity model authority | `ps_resource_forecast_v2` is the authoritative source for all forward capacity and forecast calculations; PM forecast data from `ps_resource_forecasts` is displayed as a secondary comparison only |
| COO alignment | Every tab is either a deeper cut of a COO dashboard tab or a net-new operational capability not present at the COO level |

---

## 5. Scope

### ✅ In Scope

- 16-tab Streamlit dashboard redesign
- New `practice_area` column on `clockify_users`
- New `ps_profitability_rates` configuration table
- New `vw_time_compliance_history` and `vw_utilization_history` PostgreSQL views
- `vw_project_time_detail` enhancement (add `user_name`)
- Jira import upsert fix (`ps_project_status`)
- MC V2 Audit Lambda step (Confluence artifact verification)
- Capacity model enhancements (seasonal correction, dynamic lookback, PM forecast accuracy scoring)
- QuickSight ML Insights overlay on macro utilization trend
- Streamlit settings editor for `practice_area` and `ps_profitability_rates`

### ❌ Out of Scope

- COO Operational Analysis dashboard changes
- DeliverPro integration (not yet available)
- Finance system integration (cost actuals from accounting systems)
- Real-time data streaming (Lambda batch import cadence unchanged)
- Mobile / responsive design

### ⚠️ Assumptions

- See [Section 12](#12-assumptions)

---

## 6. Tab Functional Requirements

---

### Tab 1 — Weekly Operations Summary

**COO Alignment:** Deeper cut of COO Weekly Pulse tab
**Primary Users:** COO, delivery managers, POD leads

#### FR-01-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief — COO dashboard alignment requirement

**Description:**
The tab shall display a KPI strip of exactly 6 tiles matching the COO Weekly Pulse KPIs.

**Acceptance Criteria:**
- Tile 1 — Billable Utilization %: `SUM(billable_hours) / SUM(capacity_hours) * 100` for the selected reporting week, rounded to 1 decimal place; sourced from `vw_project_hours_by_assignment` joined to `clockify_users.weekly_capacity_hours`
- Tile 2 — Productive Utilization %: `SUM(billable_hours + nb_productive_hours) / SUM(capacity_hours) * 100`, rounded to 1 decimal place
- Tile 3 — Time Compliance: `COUNT(users with hours > 0 for week) / COUNT(active users) * 100`, rounded to 1 decimal place; active users defined as `clockify_users` where `is_active = TRUE`
- Tile 4 — Headcount: `COUNT(DISTINCT clockify_user_id)` with hours > 0 in the selected reporting week
- Tile 5 — Open Escalations: `COUNT(*)` from `escalations` where `resolved_date IS NULL`
- Tile 6 — Presales Hours: `SUM(duration_hours)` from `clockify_detailed_time_entries` where project category resolves to `'Presales'` via `ps_project_mapping` for the selected week
- Each tile displays the current week value and a delta indicator (▲/▼) vs the prior week value
- Tiles are non-interactive (display only)

#### FR-01-002: Hours by Category Bar Chart

**Priority:** Must Have
**Source:** Design brief — project-based classification requirement

**Description:**
The tab shall display a stacked bar chart of hours broken down by category (PS / MC / Other) and billing type (Billable / NB Productive / NB Non-Productive) for the selected reporting week.

**Acceptance Criteria:**
- Source: `vw_project_hours_by_assignment` — categories derived from `ps_project_mapping.category`, not from employee attributes
- X-axis: category labels (`PS`, `MC`, `Other`)
- Each bar is stacked into three segments: Billable (green), NB Productive (amber), NB Non-Productive (red)
- Chart is filterable by POD; when a POD filter is active, only hours from projects assigned to that POD (via `clockify_projects.pod_assignment`) are shown
- Hovering a bar segment shows: category, billing type, total hours, % of category total

#### FR-01-003: Hours Breakdown Filter Controls

**Priority:** Must Have
**Source:** Design brief

**Description:**
The tab shall provide three filter controls: Reporting Week, Category, POD.

**Acceptance Criteria:**
- Reporting Week: date picker defaulting to the most recently completed Monday (i.e., `DATE_TRUNC('week', CURRENT_DATE - INTERVAL '7 days')`)
- Category: multi-select of `['PS', 'MC', 'Other']`; default = all selected
- POD: multi-select populated from distinct `pod_assignment` values in `clockify_projects`; default = all selected
- All three filters apply simultaneously to FR-01-002 and FR-01-004

#### FR-01-004: Project Hours Drill-Down Table

**Priority:** Must Have
**Source:** Design brief

**Description:**
The tab shall display a tabular drill-down of hours at the project level for the selected reporting week.

**Acceptance Criteria:**
- Columns (in order): Customer, Project, Category, POD, Resources, Total Hrs, Billable Hrs, NB Hrs, Trend vs 4w Avg
- Customer: canonical client name from `ps_project_mapping`; fallback to `clockify_detailed_time_entries.client_name`
- Resources: `COUNT(DISTINCT clockify_user_id)` for the project in the selected week
- Trend vs 4w Avg: `(total_hours - avg_hours_4w) / avg_hours_4w * 100` from `vw_project_hours_summary`; displayed as `+X%` or `-X%`; shown as `—` if no 4-week baseline exists
- Table is sortable by any column
- Table respects the Reporting Week, Category, and POD filters
- Table supports client-side search/filter by Customer or Project name

---

### Tab 2 — PS Project Status

**COO Alignment:** Deeper cut of COO PS Delivery sheet
**Primary Users:** COO, PS delivery managers, PMs

#### FR-02-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Description:**
The tab shall display a 4-tile KPI strip for PS project health.

**Acceptance Criteria:**
- Tile 1 — Avg Duration: `AVG(CURRENT_DATE - actual_kickoff)` in weeks (rounded to 1 decimal) for projects where `actual_kickoff IS NOT NULL` and `status != 'Done'`; sourced from `ps_project_status`
- Tile 2 — On-Time Rate: `COUNT(*) FILTER (WHERE actual_completion <= planned_end OR status != 'Done') / COUNT(*) * 100` for projects with `actual_completion IS NOT NULL`; rounded to 1 decimal place
- Tile 3 — PS Billable Hours: `SUM(billable_hours)` for the selected reporting week for projects where `category = 'PS'`; sourced from `vw_project_hours_by_assignment`
- Tile 4 — Last Week Hours: `SUM(total_hours)` for the selected reporting week for PS projects
- Each tile shows current value only (no delta required for this tab)

#### FR-02-002: Activity Tiles

**Priority:** Must Have
**Source:** Design brief

**Description:**
The tab shall display four activity count tiles comparing this week to last week.

**Acceptance Criteria:**
- Tile A — Closings This Week: `COUNT(*)` from `ps_project_status` where `DATE_TRUNC('week', actual_completion) = selected_week`
- Tile B — Closings Last Week: `COUNT(*)` where `DATE_TRUNC('week', actual_completion) = selected_week - INTERVAL '7 days'`
- Tile C — Kickoffs This Week: `COUNT(*)` where `DATE_TRUNC('week', actual_kickoff) = selected_week`
- Tile D — Kickoffs Last Week: `COUNT(*)` where `DATE_TRUNC('week', actual_kickoff) = selected_week - INTERVAL '7 days'`
- All four tiles are displayed in a 2×2 grid, labeled clearly

#### FR-02-003: Health Donut Chart

**Priority:** Must Have
**Source:** Design brief — COO alignment

**Description:**
The tab shall display a donut chart of active PS project health distribution.

**Acceptance Criteria:**
- Segments: Green, Amber, Red, Unknown (for null/missing health)
- Colors: Green = `#2ecc71`, Amber = `#f39c12`, Red = `#e74c3c`, Unknown = `#95a5a6`
- Count and % shown in each segment label
- Source: `ps_project_status` where `status != 'Done'` and `category = 'PS'`
- Clicking a segment filters the FR-02-005 project table to that health value

#### FR-02-004: Pipeline by Stage Bar Chart

**Priority:** Must Have
**Source:** Design brief — COO alignment

**Description:**
The tab shall display a horizontal bar chart showing count of active PS projects by Jira stage.

**Acceptance Criteria:**
- Source: `ps_project_status` where `status != 'Done'` and `category = 'PS'`
- X-axis: count of projects; Y-axis: stage labels (values from `ps_project_status.stage`)
- Bars sorted descending by count
- Clicking a bar filters the FR-02-005 project table to that stage

#### FR-02-005: All Active Projects Table

**Priority:** Must Have
**Source:** Design brief

**Description:**
The tab shall display a table of all active PS projects (not limited to at-risk projects).

**Acceptance Criteria:**
- Active projects: `ps_project_status` where `status != 'Done'` and `category = 'PS'`
- Columns (in order): Client, Project, PM, SA, Engineer, Stage, Health, Budget Health, Schedule Health, Escalation, Planned End, Expected Completion, Days to Go, Last Week Hours, YTD Hours, Budget Burn %
- Engineer: `ps_project_status.engineer` field
- Days to Go: `planned_end - CURRENT_DATE`; displayed as `—` if `planned_end IS NULL`
- Last Week Hours: from `vw_project_hours_summary` for the most recently completed week
- YTD Hours: `SUM(total_hours)` from `vw_project_hours_summary` for weeks in the current calendar year
- Budget Burn %: `(YTD Hours / ps_project_status.budget_hours) * 100`, rounded to 1 decimal; shown as `—` if `budget_hours IS NULL` or 0
- Budget Burn % cell background: green if < 80%, amber if 80–100%, red if > 100%
- Health cell background matches health color (Green/Amber/Red)
- Escalation: `'Yes'` / `'No'` based on open escalation match; `'Yes'` displayed in red text
- Table is sortable by any column; default sort: Health (Red first), then Days to Go ascending

#### FR-02-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Health: multi-select of `['Green', 'Amber', 'Red', 'Unknown']`; default = all
- Stage: multi-select populated from distinct `stage` values; default = all
- PM: multi-select populated from distinct `project_manager` values; default = all
- Escalation: single-select `['All', 'Yes', 'No']`; default = All
- Status Category: single-select `['Active', 'Done', 'All']`; default = Active
- All filters apply to FR-02-005 table; Health and Stage filters also apply to donut and pipeline charts

---

### Tab 3 — PS Profitability

**COO Alignment:** Net-new operational capability (no COO equivalent)
**Primary Users:** COO, delivery managers, finance operations

#### FR-03-001: Rate Configuration Table (`ps_profitability_rates`)

**Priority:** Must Have
**Source:** Design brief

**Description:**
A new PostgreSQL table `ps_profitability_rates` shall store four configurable rate values. A Streamlit form shall allow editing these values.

**Acceptance Criteria:**
- Table schema:
  ```sql
  CREATE TABLE ps_profitability_rates (
      id SERIAL PRIMARY KEY,
      rate_name VARCHAR(50) NOT NULL UNIQUE,  -- 'onshore_rate', 'offshore_rate', 'contractor_rate', 'billable_rate'
      rate_usd_per_hour NUMERIC(10,2) NOT NULL,
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      updated_by VARCHAR(100)
  );
  ```
- Streamlit form displays all four rates in a single editable form with labeled numeric inputs ($/hr)
- On save: `UPDATE ps_profitability_rates SET rate_usd_per_hour = $1, updated_at = NOW(), updated_by = $2 WHERE rate_name = $3`
- Validation: rate values must be > 0 and ≤ 9999.99; submission rejected with inline error message `"Rate must be between $0.01 and $9,999.99"` if violated
- Form is accessible from the PS Profitability tab via a "⚙ Configure Rates" expander

#### FR-03-002: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Tile 1 — PS Billable Hrs: `SUM(billable_hours)` for the selected reporting week, PS projects only
- Tile 2 — Budget Burn % Avg: `AVG(budget_burn_pct)` across all active PS projects with defined `budget_hours`
- Tile 3 — Onshore % of PS Hours: `SUM(hours where user is onshore) / SUM(total PS hours) * 100`; "onshore" = `clockify_users.location = 'onshore'` (see OQ-001)
- Tile 4 — Contractor % of PS Hours: `SUM(hours where user is contractor) / SUM(total PS hours) * 100`; "contractor" = `clockify_users.employment_type = 'contractor'` (see OQ-001)
- All tiles for selected reporting week

#### FR-03-003: Onshore vs Offshore Donut

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Two segments: Onshore hours, Offshore hours for selected reporting week, PS projects only
- Hours and % shown per segment
- Source: `clockify_detailed_time_entries` joined to `clockify_users` on `clockify_user_id`; classification by `clockify_users.location` field

#### FR-03-004: FTE vs Contractor Donut

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Two segments: FTE hours, Contractor hours for selected reporting week, PS projects only
- Source: `clockify_users.employment_type`
- Hours and % shown per segment

#### FR-03-005: SOW Budget vs Actuals Horizontal Bar Chart

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- One bar per active PS project
- Bar represents: Actual YTD hours as % of SOW budget hours (`actual_ytd / budget_hours * 100`)
- Bar color: green if < 80%, amber if 80–100%, red if > 100%
- SOW budget hours sourced from `ps_project_status.budget_hours`
- Actual YTD hours sourced from `vw_project_hours_summary` (SUM for current calendar year)
- Projects with null `budget_hours` are excluded from this chart
- Bars sorted by burn % descending
- X-axis label: "% of SOW Budget"

#### FR-03-006: 12-Week Forward Capacity Forecast Stacked Bar

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `ps_resource_forecast_v2` (capacity model) — not `ps_resource_forecasts` (PM uploads)
- X-axis: 12 consecutive weeks starting from the current week
- Each bar is stacked by project; each project gets a distinct color
- Y-axis: forecasted hours
- Legend identifies each project by `client_name + ' — ' + project_name`

#### FR-03-007: Per-Project Profitability Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- One row per active PS project
- Columns: Client, Project, SOW Hrs, Actual Hrs, Remaining Hrs, Est Completion, Onshore %, Contractor %, Burn %, Cost, Revenue, Margin, Margin %
- SOW Hrs: `ps_project_status.budget_hours`
- Actual Hrs: SUM from `vw_project_hours_summary` YTD
- Remaining Hrs: `SOW Hrs - Actual Hrs`; shown as `0` if negative
- Est Completion: derived from burn rate — `CURRENT_DATE + (Remaining Hrs / weekly_burn_rate * 7 days)`; shown as `—` if burn rate = 0
- Cost: `(onshore_hours * onshore_rate) + (offshore_hours * offshore_rate) + (contractor_hours * contractor_rate)` using rates from `ps_profitability_rates`
- Revenue: `billable_hours * billable_rate` using `billable_rate` from `ps_profitability_rates`
- Margin: `Revenue - Cost`
- Margin %: `Margin / Revenue * 100`, rounded to 1 decimal; shown as `—` if Revenue = 0
- Margin % cell: green if ≥ 40%, amber if 20–39%, red if < 20%

#### FR-03-008: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- POD: multi-select; default = all
- Practice: multi-select of `['PS', 'Both']`; default = all
- Onshore/Offshore: single-select `['All', 'Onshore', 'Offshore']`; default = All
- FTE/Contractor: single-select `['All', 'FTE', 'Contractor']`; default = All
- Reporting Week: date picker; default = most recently completed week

---

### Tab 4 — MC Service Delivery

**COO Alignment:** Deeper cut of COO MC Service Delivery sheet
**Primary Users:** COO, MC delivery managers, POD leads

#### FR-04-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief — COO alignment

**Acceptance Criteria:**
- Tile 1 — Active Customers: `COUNT(DISTINCT customer_name)` from `mc_ticket_activity` (or equivalent MC customer source) where status = active
- Tile 2 — Green: `COUNT(DISTINCT customer_name)` where customer health = `'Green'`
- Tile 3 — Red: `COUNT(DISTINCT customer_name)` where customer health = `'Red'`
- Tile 4 — MC Hours: `SUM(total_hours)` for MC-category projects for the selected week (SUM, not MAX)
- Tile 5 — Tickets Updated: `COUNT(*)` of Jira tickets updated in the selected week for MC customers
- Tile 6 — Open Escalations: `COUNT(*)` from `escalations` where `resolved_date IS NULL` and customer is an MC customer
- All tiles reflect the selected Reporting Week filter

#### FR-04-002: Hours by Customer Bar Chart

**Priority:** Must Have
**Source:** Design brief — COO alignment

**Acceptance Criteria:**
- One bar per MC customer, showing total hours for the selected week
- Source: `vw_project_hours_by_assignment` filtered to MC category projects
- Sorted descending by hours
- Clicking a customer bar filters the FR-04-004 detail table to that customer

#### FR-04-003: Tickets by Customer Bar Chart

**Priority:** Must Have
**Source:** Design brief — COO alignment

**Acceptance Criteria:**
- One bar per MC customer, showing ticket count for the selected week
- Source: MC Jira ticket data (same source as COO MC sheet)
- Sorted descending by count

#### FR-04-004: Full Customer Detail Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- One row per MC customer
- Columns: Customer, Health, POD, Total Hrs, Billable Hrs, Last Week Hrs, 4-Week Avg Hrs, Trend, Total Tickets, In Progress Tickets, Done Tickets, Updated This Week, Open Escalations
- Total Hrs: SUM for selected week from `vw_project_hours_by_assignment`
- 4-Week Avg Hrs: from `vw_project_hours_summary.avg_hours_4w`
- Trend: `▲` if last week > 4w avg, `▼` if below, `—` if equal or no baseline
- Health cell background: Green = `#2ecc71`, Amber = `#f39c12`, Red = `#e74c3c`
- Open Escalations value > 0 displayed in red text
- Table sortable by any column

#### FR-04-005: 8-Week MC Billable Hours Trend

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Line chart: one line per MC customer showing billable hours over the last 8 completed weeks
- Source: `vw_project_hours_summary` filtered to MC category
- X-axis: week labels (e.g., `"May 26"`, `"Jun 2"`)
- Y-axis: billable hours
- Customers with 0 hours across all 8 weeks are excluded from the chart by default

#### FR-04-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Health: multi-select `['Green', 'Amber', 'Red', 'Unknown']`; default = all
- POD: multi-select; default = all
- Escalation: single-select `['All', 'Yes', 'No']`; default = All
- Reporting Week: date picker; default = most recently completed week

---

### Tab 5 — Missing Time Report

**COO Alignment:** Deeper cut of COO Non-Compliant Staff visual
**Primary Users:** COO, delivery managers, POD leads, practice leads
**Compliance Definition:** A user is time-compliant for a week if `SUM(duration_hours) > 0` for that week in `clockify_detailed_time_entries`

#### FR-05-001: Section 1 — Current Week Non-Compliant Staff Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_time_compliance_history` filtered to the selected Reporting Week where `is_compliant = FALSE`
- Columns: Name, POD, Practice, Weekly Capacity Hrs, Hours Logged, Status
- Status: `'Non-Compliant'` displayed in red for all rows in this section
- Practice: from `clockify_users.practice_area`
- Users with `practice_area = 'Exempt'` are excluded from this table
- Table sorted by POD, then Name
- Row count shown as: `"X staff missing time this week"`

#### FR-05-002: Section 2 — Monthly Compliance Heatmap

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_time_compliance_history`
- One row per active user; columns: Name, POD, Practice, [one column per ISO week in the selected month], Month %, Reason
- Each week cell: green (`#2ecc71`) if compliant, red (`#e74c3c`) if non-compliant, grey (`#bdc3c7`) if user was not active that week
- Month %: `COUNT(compliant weeks) / COUNT(active weeks) * 100` for the selected month, rounded to 0 decimal places
- Reason: value from `missing_time_reasons.reason` for the selected user + month; `'—'` if none recorded
- Users with `practice_area = 'Exempt'` are excluded
- Rows sorted by Month % ascending (worst compliance first)

#### FR-05-003: Section 3 — Quarterly Compliance Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_time_compliance_history`
- One row per active user
- Columns: Name, POD, Practice, Weeks Compliant, Weeks Required, Compliance %, vs 95% Target
- Weeks Required: count of ISO weeks in the selected quarter where the user was active
- Compliance %: `Weeks Compliant / Weeks Required * 100`, rounded to 1 decimal
- vs 95% Target: `Compliance % - 95`; displayed as `+X.X%` (green) or `-X.X%` (red)
- Row background: green if Compliance % ≥ 95%, amber if 85–94%, red if < 85%
- Users with `practice_area = 'Exempt'` excluded

#### FR-05-004: `missing_time_reasons` Table

**Priority:** Must Have
**Source:** Design brief

**Description:**
A new table to store manager-entered reasons for non-compliance.

**Acceptance Criteria:**
- Schema:
  ```sql
  CREATE TABLE missing_time_reasons (
      id SERIAL PRIMARY KEY,
      clockify_user_id VARCHAR(50) NOT NULL,
      month_year VARCHAR(7) NOT NULL,  -- format: 'YYYY-MM'
      reason TEXT,
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      updated_by VARCHAR(100),
      UNIQUE(clockify_user_id, month_year)
  );
  ```
- Streamlit inline edit: clicking a Reason cell in Section 2 opens a text input; saving executes `INSERT ... ON CONFLICT DO UPDATE`

#### FR-05-005: `vw_time_compliance_history` View

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- One row per `(clockify_user_id, week_start_date)`
- Columns: `clockify_user_id`, `user_name`, `pod`, `practice_area`, `week_start_date`, `month_year` (YYYY-MM), `quarter` (Q1/Q2/Q3/Q4), `year`, `total_hours_logged`, `is_compliant` (BOOLEAN: `total_hours_logged > 0`), `weekly_capacity_hours`
- Covers all weeks with time entry data plus all weeks where the user was active per `clockify_users`
- Users not in `clockify_users` or with `is_active = FALSE` are excluded

#### FR-05-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Section 1: Reporting Week (date picker; default = most recently completed week), POD (multi-select), Practice (multi-select of distinct `practice_area` values excluding `'Exempt'`)
- Section 2: Month picker (YYYY-MM; default = current month), POD, Practice
- Section 3: Quarter (single-select `['Q1', 'Q2', 'Q3', 'Q4']`) + Year (single-select of available years); default = current quarter/year, POD, Practice

---

### Tab 6 — Resource Forecast

**COO Alignment:** Net-new depth (no direct COO equivalent at this granularity)
**Primary Users:** COO, delivery managers, PMs
**Forecast Authority:** `ps_resource_forecast_v2` is the capacity model; `ps_resource_forecasts` is PM-uploaded forecast shown for comparison only

#### FR-06-001: Section 1 — 12-Week Forward View (Dual Chart)

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Two stacked bar charts rendered side-by-side with identical X-axis (same 12 weeks, same scale)
- Chart A — PM Forecast: data from `ps_resource_forecasts`, stacked by project
- Chart B — Capacity Model: data from `ps_resource_forecast_v2`, stacked by project
- X-axis: weeks 0 through +11 from current week (ISO Monday labels)
- Y-axis: forecasted hours; both charts share the same Y-axis scale
- Legend: each project as `client_name + ' — ' + project_name`; same color per project in both charts
- Chart title labels: "PM Forecast" and "Capacity Model"

#### FR-06-002: Section 2 — Forecast vs Actuals Accuracy Chart

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `ps_resource_forecasts` (PM forecast, historical), `ps_resource_forecast_v2` (capacity model, historical snapshots), `clockify_detailed_time_entries` (actuals)
- Line chart: one line per project, X-axis = past weeks, Y-axis = hours
- Three lines per project (toggleable): PM Forecast (dashed blue), Capacity Model (solid blue), Actuals (solid green)
- Covers weeks within the selected Week Range filter
- Hovering a point shows: week, project, PM forecast hours, capacity model hours, actual hours, variance (PM − Actual)

#### FR-06-003: Section 3 — PM Forecast Accuracy Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `ai_pm_forecast_accuracy`
- Columns: PM Name, Projects, Avg Forecast Error %, Last 4 Weeks Error %, Trend (▲ improving / ▼ worsening / — stable)
- Trend defined as: improving if last 4-week avg error < prior 4-week avg error by > 2pp; worsening if > 2pp worse; stable otherwise
- Table sorted by Avg Forecast Error % ascending (most accurate first)

#### FR-06-004: Section 4 — Detail Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Columns: User, Project, Client, Week, PM Forecast Hrs, Capacity Model Hrs, Actual Hrs, Variance
- Variance: `Actual Hrs - Capacity Model Hrs`; displayed as `+X.X` (green) or `-X.X` (red)
- One row per (user, project, week) combination within selected filters
- Table supports client-side search by User, Project, or Client name
- Table is sortable by any column

#### FR-06-005: QuickSight ML Insights Overlay

**Priority:** Should Have
**Source:** Design brief

**Acceptance Criteria:**
- On the macro utilization trend chart (rolling 12-week actual billable utilization %), render ML forecast confidence bands sourced from QuickSight ML Insights
- Confidence band displayed as a shaded region (upper/lower bounds) in light blue
- Forecasted central line rendered as a dashed line extending 4 weeks past the last actual data point
- A legend label reads: "QuickSight ML Forecast (±1 std dev)"

#### FR-06-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- PM: multi-select of distinct PM names from `ps_resource_forecasts`; default = all
- Project: multi-select; default = all
- Week Range: date range picker; default = 8 weeks back to 12 weeks forward
- User: multi-select of distinct users in `ps_resource_forecasts`; default = all
- All filters apply to Sections 1–4

---

### Tab 7 — Resource Capacity

**COO Alignment:** Net-new operational capability
**Primary Users:** Delivery managers, POD leads, PMs
**PS Resource Definition:** `clockify_users.practice_area IN ('PS', 'Both')`

#### FR-07-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Tile 1 — Total PS Capacity: `SUM(weekly_capacity_hours)` for PS resources across the next 12 weeks (annualized per week = same value per week unless capacity changes)
- Tile 2 — Allocated: `SUM(forecasted_hours)` from `ps_resource_forecast_v2` for PS resources in weeks 0–11
- Tile 3 — Available: `Total PS Capacity - Allocated`
- Tile 4 — Over-Allocated Count: `COUNT(DISTINCT user_id)` where `SUM(forecasted_hours) > weekly_capacity_hours` in any week within weeks 0–11
- Tile 5 — Unassigned Count: `COUNT(DISTINCT user_id)` where `SUM(forecasted_hours) = 0` for weeks 0–3 (first 4 weeks)
- All values from `ps_resource_forecast_v2` (capacity model only)

#### FR-07-002: Availability Heatmap

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Grid: rows = PS resource names (sorted by POD, then name); columns = 12 weeks (ISO Monday labels)
- Each cell value: `SUM(forecasted_hours) / weekly_capacity_hours * 100` (allocation %)
- Cell color: green if < 80%, amber if 80–100%, red if > 100%
- Cell text: allocation % rounded to 0 decimal (e.g., `"72%"`)
- Hovering a cell shows: Person, Week, Forecasted Hrs, Capacity Hrs, Allocation %
- Source: `ps_resource_forecast_v2` joined to `clockify_users`

#### FR-07-003: Available for Assignment Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Rows: PS resources where allocation % < 80% in week 0 (current week)
- Columns: Person, POD, Title, Skill Area, Available Hrs/Wk, First Available Week
- Available Hrs/Wk: `weekly_capacity_hours - SUM(forecasted_hours for week 0)` from `ps_resource_forecast_v2`
- First Available Week: earliest week where allocation % < 80%; uses `ps_resource_forecast_v2` look-ahead
- Title and Skill Area: from `clockify_users` (see OQ-002 for field availability)
- Table sorted by Available Hrs/Wk descending

#### FR-07-004: Over-Allocated Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Rows: PS resources where `SUM(forecasted_hours) > weekly_capacity_hours` in any week within weeks 0–11
- Columns: Person, POD, Projects, Total Forecast Hrs, Capacity, Over By
- Projects: comma-separated list of `project_name` values from `ps_resource_forecast_v2` for the peak allocation week
- Total Forecast Hrs: max weekly total across weeks 0–11
- Over By: `Total Forecast Hrs - weekly_capacity_hours`; displayed in red text

#### FR-07-005: PM Forecast Conflicts Section

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `ps_resource_forecasts` (PM uploads) compared against `clockify_users.weekly_capacity_hours`
- Displays only rows where PM forecast exceeds capacity: `pm_forecast_hours > weekly_capacity_hours` for a given (user, week)
- Columns: Person, Week, PM Forecast Hrs, Capacity Hrs, Excess Hrs
- Section header labeled: "⚠ PM Forecast Conflicts (PM-sourced data — may not reflect final allocation)"
- Displayed as a distinct table, clearly separated from capacity model tables

#### FR-07-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- POD: multi-select; default = all
- Practice: multi-select of `['PS', 'Both']`; default = all
- Skill Area: multi-select (see OQ-002); default = all
- Week Range: date range picker for 12-week window; default = current week + 11

---

### Tab 8 — PS Delivery Analysis

**COO Alignment:** Net-new AI-driven operational capability (previously "PS Productivity AI")
**Primary Users:** Delivery managers, practice leads
**Data Sources:** `ai_analysis_by_project`, `ai_analysis_by_user`

#### FR-08-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Tile 1 — Projects On Track: `COUNT(DISTINCT project_id)` where `verdict = 'On Track'` for selected week
- Tile 2 — Over-Logged: `COUNT(DISTINCT project_id)` where `verdict = 'Over-Logged'`
- Tile 3 — Under-Logged: `COUNT(DISTINCT project_id)` where `verdict = 'Under-Logged'`
- Tile 4 — No Jira Activity: `COUNT(DISTINCT project_id)` where `verdict = 'No Jira Activity'`
- Tile 5 — Avg Hours Variance %: `AVG(variance_pct)` across all projects for selected week, rounded to 1 decimal
- Source: `ai_analysis_by_project` for the selected week

#### FR-08-002: Verdict Distribution Chart

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Horizontal stacked bar chart: one bar per project
- Each bar stacked by verdict category: On Track (green), Over-Logged (amber), Under-Logged (red), No Jira Activity (grey)
- Segment width proportional to count of people in that verdict for the project
- Y-axis: project names; X-axis: count of people
- Source: `ai_analysis_by_user` grouped by project and verdict

#### FR-08-003: By Project Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `ai_analysis_by_project`
- Columns: Project, Team Size, Jira Est Hrs, Clockify Actual Hrs, Delta, Variance %, Verdict, AI Notes
- Delta: `Clockify Actual Hrs - Jira Est Hrs`; displayed as `+X.X` or `-X.X`
- Variance %: `Delta / Jira Est Hrs * 100`, rounded to 1 decimal; shown as `—` if `Jira Est Hrs = 0`
- Verdict cell color: On Track = green, Over-Logged = amber, Under-Logged = red, No Jira Activity = grey
- AI Notes: truncated to 120 characters with expand-on-click

#### FR-08-004: By Person Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `ai_analysis_by_user`
- Columns: Person, Project, Role, Jira Issues, Jira Est Hrs, Clockify Actual Hrs, Delta, Verdict, AI Notes
- Delta: `Clockify Actual Hrs - Jira Est Hrs`
- Verdict cell color: same scheme as FR-08-003

#### FR-08-005: 8-Week Variance Trend

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Line chart: one line showing `AVG(variance_pct)` per week across the last 8 completed weeks
- Source: `ai_analysis_by_project` for weeks −7 to 0 relative to selected week
- X-axis: week labels; Y-axis: avg variance %
- A reference line at 0% labeled `"Target: 0% Variance"`

#### FR-08-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Week: date picker; default = most recently completed week
- Project: multi-select; default = all
- Verdict: multi-select of `['On Track', 'Over-Logged', 'Under-Logged', 'No Jira Activity']`; default = all
- Person: multi-select; default = all

---

### Tab 9 — Non-Billable Analysis

**COO Alignment:** Net-new operational depth
**Primary Users:** COO, delivery managers, practice leads

#### FR-09-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Tile 1 — Total NB Hours: `SUM(duration_hours)` where `billable = FALSE` for selected week
- Tile 2 — NB as % of Total: `SUM(NB hours) / SUM(total hours) * 100` for selected week, rounded to 1 decimal
- Tile 3 — NB Productive Hrs: `SUM(duration_hours)` where NB category is `'NB Productive'` (Presales, Training, Internal Initiatives)
- Tile 4 — NB Non-Productive Hrs: `SUM(duration_hours)` where NB category is `'NB Non-Productive'` (Overhead, Admin)
- Tile 5 — Presales Hrs: `SUM(duration_hours)` where project maps to `'Presales'` via `ps_project_mapping`; delta vs prior week shown as `(▲ +X.X)` or `(▼ -X.X)`
- Source: `vw_project_hours_by_assignment` for the selected week

#### FR-09-002: 12-Week NB Category Stacked Bar

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- X-axis: 12 weeks ending on the selected week
- Each bar stacked by NB category: Presales (navy), Training (blue), Internal Initiatives (teal), Overhead (grey), NB Productive (green), NB Non-Productive (red)
- Y-axis: total hours
- Source: `vw_project_hours_by_assignment` (or `vw_project_hours_summary`) over the 12-week window, filtered to non-billable entries via `ps_project_mapping.category`

#### FR-09-003: Top 15 People by NB Hours

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Horizontal bar chart: top 15 users by total NB hours for the selected week
- Each bar colored by the user's primary NB type (the category with the most hours for that user that week)
- X-axis: NB hours; Y-axis: user name
- Source: `clockify_detailed_time_entries` joined to `ps_project_mapping` for category, filtered to `billable = FALSE`

#### FR-09-004: NB Hours by POD and by Practice

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Two charts displayed side-by-side:
  - Chart A — By POD: NB hours as % of total hours per POD (bar chart, sorted descending)
  - Chart B — By Practice: NB hours as % of total hours per practice area (bar chart)
- % of total hours used (not raw hours) to enable fair comparison across PODs/practices of different sizes
- Source: `vw_project_hours_by_assignment` joined to `clockify_users` for `practice_area` and `pod_assignment`

#### FR-09-005: Pattern Detection Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- One row per active user
- Columns: Person, POD, Practice, NB Hrs This Wk, NB % This Wk, 4-Wk Avg NB %, Trend, Primary NB Type
- NB % This Wk: `NB hours this week / total hours this week * 100`
- 4-Wk Avg NB %: average NB % over the 4 completed weeks prior to selected week
- Trend: `▲` if NB % this week > 4-wk avg + 5pp, `▼` if < 4-wk avg - 5pp, `—` otherwise
- Primary NB Type: the NB category with the highest hours for this user in the selected week
- Table sorted by NB % This Wk descending

#### FR-09-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Week Range: date range picker; default = last 12 weeks
- POD: multi-select; default = all
- Practice: multi-select; default = all
- NB Type: multi-select of NB categories from `ps_project_mapping`; default = all
- Person: multi-select; default = all

---

### Tab 10 — MC V2 Audit

**COO Alignment:** Net-new operational capability
**Primary Users:** MC delivery managers, practice leads, COO

#### FR-10-001: Confluence Artifact Verification Lambda Step

**Priority:** Must Have
**Source:** Design brief

**Description:**
The Lambda import pipeline shall be extended with a step that verifies Confluence artifact links for Done Jira issues in MC V2 projects.

**Acceptance Criteria:**
- For each Jira issue where `status = 'Done'` and the project is classified as MC V2:
  1. Call Jira REST API `GET /rest/api/3/issue/{issue_key}/remotelink` to retrieve remote links
  2. Filter links where `object.url` contains the Confluence base URL
  3. For each Confluence link found, call Confluence REST API `GET /wiki/rest/api/content?spaceKey=...` (or equivalent by URL) to verify the page exists and is not archived
  4. Write results to `mc_v2_audit_artifacts` table
- Schema:
  ```sql
  CREATE TABLE mc_v2_audit_artifacts (
      id SERIAL PRIMARY KEY,
      jira_issue_id VARCHAR(50) NOT NULL,
      jira_issue_key VARCHAR(20) NOT NULL,
      customer_name VARCHAR(200),
      phase VARCHAR(100),
      artifact_present BOOLEAN NOT NULL DEFAULT FALSE,
      artifact_url TEXT,
      artifact_verified_at TIMESTAMPTZ,
      confluence_page_exists BOOLEAN,
      error_message TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      UNIQUE(jira_issue_id)
  );
  ```
- On re-run, `ON CONFLICT (jira_issue_id) DO UPDATE` with latest verification result
- Lambda step must complete within 5 minutes for up to 500 issues; implement batch processing with max 10 concurrent Confluence API calls

#### FR-10-002: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Tile 1 — Customers Audited: `COUNT(DISTINCT customer_name)` in `mc_v2_audit_by_customer`
- Tile 2 — Avg Methodology Completion %: `AVG(completion_pct)` from `mc_v2_audit_by_customer`
- Tile 3 — Fully Compliant: `COUNT(DISTINCT customer_name)` where all Done issues have `artifact_present = TRUE` and `confluence_page_exists = TRUE`
- Tile 4 — Missing Artifacts: `COUNT(*)` from `mc_v2_audit_artifacts` where `artifact_present = FALSE` or `confluence_page_exists = FALSE`
- Tile 5 — External Boards: count of MC customers whose Jira boards are external (see OQ-003)

#### FR-10-003: Customer × Phase Heatmap

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Grid: rows = customers, columns = MC V2 phases (derived from Jira issue labels or components)
- Cell value: `COUNT(Done issues with artifact) / COUNT(Done issues) * 100` per (customer, phase)
- Cell color: green if ≥ 80%, amber if 50–79%, red if < 50%, grey if no Done issues
- Cell text: `"X%"` plus an artifact indicator: `✓` if all artifacts verified, `⚠` if some missing
- Hovering shows: customer, phase, done count, artifact-verified count, completion %

#### FR-10-004: Missing Artifacts Drill-Down Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `mc_v2_audit_artifacts` where `artifact_present = FALSE` or `confluence_page_exists = FALSE`
- Columns: Customer, Phase, Jira Issue (hyperlinked to Jira), Status, Confluence Link Present, Page Verified
- Confluence Link Present: `'Yes'` / `'No'` from `artifact_present`
- Page Verified: `'Yes'` / `'No'` / `'Error'` from `confluence_page_exists` / `error_message IS NOT NULL`
- Table sorted by Customer, then Phase

#### FR-10-005: AI Narrative per Customer

**Priority:** Should Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `mc_v2_audit_by_customer.executive_summary`
- Displayed as an expandable text block per customer, labeled: `"AI Summary — {customer_name}"`
- If `executive_summary IS NULL`, display: `"No AI summary available for this customer."`

#### FR-10-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Customer: multi-select; default = all
- Phase: multi-select; default = all
- POD: multi-select; default = all
- Artifact Status: single-select `['All', 'Compliant', 'Missing Artifact', 'Unverified']`; default = All

---

### Tab 11 — Project Hours Trend

**COO Alignment:** Operational depth version of COO Project Hours sheet
**Primary Users:** Delivery managers, POD leads

#### FR-11-001: 12-Week Hours Trend Chart

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_project_hours_summary`
- Line chart: one line per project (client + project name), showing `total_hours` per week over the last 12 completed weeks
- Projects with zero hours across all 12 weeks excluded from chart by default
- X-axis: week labels (ISO Monday); Y-axis: hours
- Maximum 20 projects rendered simultaneously; if more match filters, top 20 by total hours shown with a notice: `"Showing top 20 projects by total hours. Refine filters to see others."`
- Chart uses project-based classification from `vw_project_hours_summary` (not employee attributes)

#### FR-11-002: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Client: multi-select; default = all
- Project: multi-select; default = all
- Category: multi-select of `['PS', 'MC', 'Other']`; default = all
- POD: multi-select; default = all
- Week Range: date range picker; default = last 12 completed weeks

---

### Tab 12 — Escalations

**COO Alignment:** Deeper cut of COO Escalations sheet
**Primary Users:** COO, delivery managers, POD leads

#### FR-12-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Tile 1 — Total Open: `COUNT(*)` from `escalations` where `resolved_date IS NULL`
- Tile 2 — High Priority: `COUNT(*)` where `resolved_date IS NULL` AND `priority IN ('High', 'Critical')` (not all non-Low priorities — must filter to explicitly High/Critical)
- Tile 3 — Avg Days Open: `AVG(CURRENT_DATE - created_date)` for open escalations, rounded to 1 decimal (AVG, not MAX)
- Tile 4 — Oldest (Days): `MAX(CURRENT_DATE - created_date)` for open escalations
- Tile 5 — Resolved This Month: `COUNT(*)` where `DATE_TRUNC('month', resolved_date) = DATE_TRUNC('month', CURRENT_DATE)`
- Tiles reflect active filter state

#### FR-12-002: Bar Charts

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Three bar charts displayed in a row: By Customer, By Assignee, By Priority
- Each chart: count of open escalations per dimension
- By Priority sorted: Critical → High → Medium → Low
- By Customer and By Assignee sorted descending by count
- Source: `escalations` where `resolved_date IS NULL`

#### FR-12-003: 12-Week Open Escalation Trend

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Line chart: `COUNT(open escalations)` per ISO week for the last 12 completed weeks
- An escalation is "open" in a week if `created_date <= week_end` AND (`resolved_date IS NULL` OR `resolved_date > week_end`)
- X-axis: week labels; Y-axis: count

#### FR-12-004: Full Detail Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `escalations`
- Columns: Customer, Issue Key, Summary, Priority, Assignee, Status, Days Open, Last Status Change, Days Since Last Update, Previous Status, PM/SA
- Issue Key: rendered as a hyperlink to Jira (`https://{jira_base_url}/browse/{issue_key}`)
- Days Open: `CURRENT_DATE - created_date`
- Days Since Last Update: `CURRENT_DATE - updated_date`
- Priority cell background: Critical = dark red, High = red, Medium = amber, Low = default
- Table default sort: Priority (Critical first), then Days Open descending
- Table sortable by any column

#### FR-12-005: New/Changed This Week Tables

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Two small tables below the main table:
  - Table A — Opened This Week: escalations where `DATE_TRUNC('week', created_date) = selected_week`; columns: Customer, Issue Key, Summary, Priority, Assignee
  - Table B — Status Changed This Week: escalations where `DATE_TRUNC('week', last_status_change_date) = selected_week`; columns: Customer, Issue Key, Summary, Previous Status, Current Status, Assignee
- Both tables labeled with counts: `"X new this week"`, `"X status changes this week"`

#### FR-12-006: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Priority: multi-select of `['Critical', 'High', 'Medium', 'Low']`; default = all
- Assignee: multi-select; default = all
- Customer: multi-select; default = all
- Status: multi-select; default = open only (`resolved_date IS NULL`)
- Date Opened Range: date range picker; default = no constraint
- Is New: toggle `['All', 'New This Week']`; default = All

---

### Tab 13 — Productive Utilization

**COO Alignment:** Deeper cut of COO Time & Utilization sheet
**Primary Users:** COO, delivery managers, POD leads
**Utilization Target:** Billable hours ≥ 75% of `clockify_users.weekly_capacity_hours`

#### FR-13-001: Section 1 — Current Week All-Staff Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_utilization_history` for the selected Reporting Week
- One row per active user
- Columns: Name, POD, Practice, Billable Hrs, Total Hrs, Billable %, vs 75% Target
- Billable %: `billable_hours / total_hours * 100`, rounded to 1 decimal; shown as `—` if `total_hours = 0`
- vs 75% Target: `Billable % - 75`; displayed as `+X.X%` (green text) or `-X.X%` (red text)
- Users with `practice_area = 'Exempt'` excluded
- Sorted by Billable % ascending (worst first)

#### FR-13-002: Section 2 — Monthly Billable % Heatmap

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_utilization_history`
- One row per user; columns: Name, POD, Practice, [one column per ISO week in selected month], Avg Billable %, NB Productive %, NB Non-Productive %, Unlogged %
- Week cell: shows billable % as `"X%"`; background green if ≥ 75%, red if < 75%, grey if user not active that week
- Avg Billable %: mean of week cells across the month
- NB Productive %: `SUM(nb_productive_hours) / SUM(capacity_hours) * 100` for the month
- NB Non-Productive %: `SUM(nb_non_productive_hours) / SUM(capacity_hours) * 100` for the month
- Unlogged %: `(SUM(capacity_hours) - SUM(total_logged_hours)) / SUM(capacity_hours) * 100`; shown as 0 if negative
- Users with `practice_area = 'Exempt'` excluded

#### FR-13-003: `vw_utilization_history` View

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- One row per `(clockify_user_id, week_start_date)`
- Columns: `clockify_user_id`, `user_name`, `pod`, `practice_area`, `week_start_date`, `month_year`, `quarter`, `year`, `billable_hours`, `nb_productive_hours`, `nb_non_productive_hours`, `total_logged_hours`, `capacity_hours` (from `clockify_users.weekly_capacity_hours`), `billable_pct`, `nb_productive_pct`, `nb_non_productive_pct`, `unlogged_pct`
- `billable_pct`: `billable_hours / NULLIF(total_logged_hours, 0) * 100`
- NB categorization uses `ps_project_mapping.category` for classification (project-based, not employee-attribute)
- Covers all weeks with any time entry data

#### FR-13-004: Section 3 — Quarterly Compliance Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_utilization_history` aggregated to quarter
- One row per active user
- Columns: Name, POD, Practice, Avg Billable %, Weeks ≥ 75%, Compliance %, vs 75% Target
- Compliance %: `COUNT(weeks where billable_pct >= 75) / COUNT(active weeks) * 100`
- vs 75% Target: `Compliance % - 75`
- Row background: green if Compliance % ≥ 75%, amber if 65–74%, red if < 65%

#### FR-13-005: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Section 1: Reporting Week (date picker), POD, Practice, Person
- Section 2: Month picker (default = current month), POD, Practice, Person
- Section 3: Quarter + Year, POD, Practice, Person

---

### Tab 14 — Project Time Detail

**COO Alignment:** Standalone detailed time ledger
**Primary Users:** Delivery managers, billing analysts

#### FR-14-001: Full Time Entry Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `vw_project_time_detail` (enhanced to include `user_name`)
- Columns: Date, User, Client, Project, Task, Description, Hours, Billable
- Date: formatted as `YYYY-MM-DD`
- User: `clockify_users.full_name` (currently missing from this view — see FR-CCR-006)
- Billable: `'Yes'` / `'No'`
- Table supports client-side search across all text columns
- Table is sortable by any column; default sort: Date descending
- Table is paginated at 500 rows per page

#### FR-14-002: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Client: multi-select; default = all
- Project: multi-select (cascades from Client selection); default = all
- User: multi-select populated from distinct users in dataset; default = all
- Week: date picker (ISO week); default = most recently completed week
- Task: multi-select of distinct task names; default = all
- Billable/Non-Billable: single-select `['All', 'Billable', 'Non-Billable']`; default = All

---

### Tab 15 — Customer Status Assignments

**COO Alignment:** Operational resource-visibility view
**Primary Users:** COO, delivery managers, PMs

#### FR-15-001: Customer Status Assignments Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Source: `ps_project_status` filtered to active projects (`status != 'Done'`) and `category = 'PS'`
- Engineers split: if `ps_project_status.engineer` contains comma-separated names, each engineer occupies its own row (Client, Project, Stage, Health repeated per row); engineer-split rows are visually grouped
- Columns: Client, Project, Stage, Health, PM, SA, Engineer, POD, Start, Expected End
- Start: `ps_project_status.planned_start` or `actual_kickoff`
- Expected End: `ps_project_status.planned_end` or `expected_completion`
- Health cell background: Green = `#2ecc71`, Amber = `#f39c12`, Red = `#e74c3c`
- Table sorted by Health (Red first), then Client

#### FR-15-002: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- POD: multi-select; default = all
- Stage: multi-select; default = all
- Health: multi-select; default = all
- Person: multi-select of all PM/SA/Engineer names; default = all

---

### Tab 16 — Project Runway

**COO Alignment:** Net-new operational capability (velocity-based forecast)
**Primary Users:** COO, delivery managers, PMs

#### FR-16-001: KPI Strip

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Tile 1 — Projects On Track: `COUNT(*)` where `model_est_completion <= planned_end` (or `planned_end IS NULL`)
- Tile 2 — At Risk: `COUNT(*)` where `model_est_completion > planned_end`
- Tile 3 — Avg Weeks to Completion: `AVG((model_est_completion - CURRENT_DATE) / 7.0)`, rounded to 1 decimal
- Tile 4 — SOW Hours Exhausted Before Completion: `COUNT(*)` where projected total hours at current burn rate exceeds `budget_hours` before `model_est_completion`
- Model est. completion derived from burn rate calculation (see FR-16-003)

#### FR-16-002: Runway Chart

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Horizontal bar chart: one bar per active PS project
- Each bar composed of two segments: Actuals Burned (solid blue) + Remaining Forecast (lighter blue)
- A vertical line per project represents the SOW hours cap (`budget_hours`)
- A marker per project represents the PM planned end date
- X-axis: hours
- Y-axis: project names (Client — Project)
- Color logic: bar segment color changes to red when remaining forecast extends beyond SOW cap

#### FR-16-003: Project Runway Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- One row per active PS project
- Columns: Client, Project, SOW Hrs, Actual Hrs YTD, Remaining SOW, Burn Rate (hrs/wk), Model Est. Completion, PM Planned End, Variance (weeks), Status
- Burn Rate: `SUM(total_hours for last 4 weeks) / 4` from `vw_project_hours_summary`; shown as `—` if no data for last 4 weeks
- Remaining SOW: `MAX(0, budget_hours - actual_hrs_ytd)`
- Model Est. Completion: `CURRENT_DATE + (Remaining SOW / burn_rate_per_day)`; shown as `—` if `burn_rate = 0`; shown as `'SOW Exhausted'` if `actual_hrs_ytd >= budget_hours`
- PM Planned End: `ps_project_status.planned_end`
- Variance (weeks): `(model_est_completion - planned_end) / 7.0`, rounded to 1 decimal; positive = at risk; displayed in red if > 0, green if ≤ 0
- Status: `'On Track'` if `model_est_completion <= planned_end`, `'At Risk'` if `model_est_completion > planned_end`, `'No Baseline'` if `planned_end IS NULL`

#### FR-16-004: 8-Week Burn Rate Trend

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Line chart: one line per project, showing `total_hours` per week for the last 8 completed weeks
- Source: `vw_project_hours_summary`
- X-axis: week labels; Y-axis: hours/week

#### FR-16-005: Filters

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- POD: multi-select; default = all
- Health: multi-select; default = all
- At Risk Only: boolean toggle; default = off; when on, shows only projects where `model_est_completion > planned_end`
- PM: multi-select; default = all

---

### Tab 17 — Organizational KPI Scorecard

**COO Alignment:** QTD accountability view of the 4 org-level KPIs
**Primary Users:** COO
**Data Source:** `kpi_weekly_snapshots` table via `kpi-weekly-snapshots-prod` SPICE dataset

#### FR-17-001: QTD KPI Tiles

**Priority:** Must Have
**Source:** COO decision — KPI definitions confirmed 2026-06-08

**Description:**
The tab shall display 4 KPI tiles showing the current QTD value for each org-level KPI, with a delta vs the same point in the prior quarter.

**Acceptance Criteria:**

| # | KPI | Source Column | QTD Value | Delta Baseline |
|---|-----|---------------|-----------|----------------|
| 1 | On-Time Delivery (PS only) | `ps_on_time_pct` | Latest week's value in the current quarter (point-in-time) | Same ISO week number in the prior quarter |
| 2 | Timesheet Compliance | `time_compliance_pct` | Latest week's value in the current quarter (point-in-time) | Same ISO week number in the prior quarter |
| 3 | Utilization | `billable_util_pct` | Latest week's value in the current quarter (point-in-time) | Same ISO week number in the prior quarter |
| 4 | Open Escalations | `open_escalations` | Latest week's value in the current quarter (point-in-time) | Same ISO week number in the prior quarter |

- "Latest week in the current quarter" = the row in `kpi_weekly_snapshots` with the maximum `week_start_date` where `quarter_label` matches the current quarter (derived via QuickSight calculated field `quarter_label`)
- Delta displayed as `▲ +X.X` (green) or `▼ -X.X` (red) for percentage KPIs; for `open_escalations`, a lower value is positive (delta display inverted: decrease = green ▼, increase = red ▲)
- Tiles are non-interactive (display only)
- Source: `kpi-weekly-snapshots-prod` SPICE dataset

#### FR-17-002: Monthly Trend Line Charts

**Priority:** Must Have
**Source:** COO decision — KPI definitions confirmed 2026-06-08

**Description:**
The tab shall display 4 trend line charts, one per KPI, showing monthly averages over the last 6 months (current quarter months + prior 3 months).

**Acceptance Criteria:**

| # | KPI | Source Column |
|---|-----|---------------|
| 1 | On-Time Delivery | `ps_on_time_pct` |
| 2 | Timesheet Compliance | `time_compliance_pct` |
| 3 | Utilization | `billable_util_pct` |
| 4 | Open Escalations | `open_escalations` |

- X-axis: month labels (e.g., `Jan`, `Feb`, `Mar`); derived via QuickSight calculated field `month_label` (YYYYMM-based sort key with display label)
- Y-axis: monthly average of weekly values = `AVG(column)` grouped by `month_label` from `kpi_weekly_snapshots`
- Time window: 6 months — current quarter months plus prior 3 months; controlled via `is_current_quarter` calculated field filter
- Each chart is a single line (no breakdown by sub-dimension)
- Charts are non-interactive (display only)
- Source: `kpi-weekly-snapshots-prod` SPICE dataset

#### Notes (Architect Reference)

- Zero new migrations, zero new views, zero new SPICE datasets required
- All data available in `kpi_weekly_snapshots` / `vw_kpi_ytd` (migration 065, applied 2026-06-08)
- QuickSight calculated fields required: `month_label` (month display string + YYYYMM sort key), `quarter_label` (e.g., `Q2 2026`), `is_current_quarter` (boolean filter field)
- Reuses existing `kpi-weekly-snapshots-prod` SPICE dataset — no new dataset registration
- Effort estimate: Small (~8–12 hours, QuickSight configuration only)

---

## 7. Retired Tabs

| Tab | Disposition |
|-----|-------------|
| Resource Conflicts | Merged into Tab 7 — Resource Capacity (FR-07-004, FR-07-005) |
| Forecast vs Actuals | Merged into Tab 6 — Resource Forecast (FR-06-002) |
| Project Directory | Retired — redundant with Tab 15 and existing project tables |

---

## 8. Cross-Cutting Requirements

#### FR-CCR-001: `practice_area` Column on `clockify_users`

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- DDL: `ALTER TABLE clockify_users ADD COLUMN practice_area VARCHAR(20);`
- Valid values: `'PS'`, `'MC'`, `'Both'`, `'MIT'`, `'Internal'`, `'Exempt'`
- `NULL` treated as `'Internal'` in all dashboard queries (assumption; see OQ-004)
- Streamlit settings editor: table view of all active users with inline `practice_area` dropdown editor; save executes `UPDATE clockify_users SET practice_area = $1 WHERE clockify_user_id = $2`
- Accessible from a "⚙ Settings" page in the Streamlit app (not embedded in a tab)

#### FR-CCR-002: `ps_profitability_rates` Table

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- See FR-03-001 for full schema and Streamlit form specification

#### FR-CCR-003: `vw_time_compliance_history` View

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- See FR-05-005 for full column specification
- View must be recreatable via a numbered migration file (`migration_0XX_vw_time_compliance_history.sql`)

#### FR-CCR-004: `vw_utilization_history` View

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- See FR-13-003 for full column specification
- View must be recreatable via a numbered migration file

#### FR-CCR-005: Jira Import Upsert Fix (`ps_project_status`)

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- The Lambda Jira import function currently performs INSERT on `ps_project_status`
- Change to: `INSERT INTO ps_project_status (...) VALUES (...) ON CONFLICT (jira_issue_id) DO UPDATE SET <all non-key columns> = EXCLUDED.<column>, updated_at = NOW()`
- Requires a UNIQUE constraint: `ALTER TABLE ps_project_status ADD CONSTRAINT uq_ps_project_status_jira_issue_id UNIQUE (jira_issue_id);` (idempotent — skip if exists)
- After fix: re-importing the same Jira issue must update the existing row, not create a duplicate

#### FR-CCR-006: `vw_project_time_detail` — Add `user_name`

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Current view is missing `user_name`
- Add: `cu.full_name AS user_name` via `LEFT JOIN clockify_users cu ON te.clockify_user_id = cu.clockify_user_id`
- Existing column order preserved; `user_name` inserted after `clockify_user_id` (or as the second column per Tab 14 display order)

#### FR-CCR-007: Capacity Model Enhancements (`ps_resource_forecast_v2`)

**Priority:** Must Have
**Source:** Design brief

**Acceptance Criteria:**
- Seasonal Correction Factor: the model shall apply a weekly correction factor `seasonal_factor` stored in a new `capacity_model_config` table (keyed by ISO week number); default = 1.0 for all weeks; applied as `forecasted_hours * seasonal_factor`
- Dynamic Lookback Window: for project assignments with a running history ≥ 8 weeks, use an 8-week lookback (instead of the current fixed window); for assignments with < 8 weeks of history, use all available weeks
- PM Forecast Accuracy Scoring: after each Lambda run, compute and upsert into `ai_pm_forecast_accuracy`: `pm_name`, `project_id`, `week_start_date`, `pm_forecast_hrs`, `actual_hrs`, `abs_error_pct` = `ABS(pm_forecast_hrs - actual_hrs) / NULLIF(actual_hrs, 0) * 100`
- QuickSight ML Insights Overlay: export macro utilization trend data to a QuickSight dataset; enable ML Insights anomaly detection on the utilization % series; embed confidence band data in a new `qs_ml_forecast` table for Streamlit overlay rendering

#### FR-CCR-008: `vw_project_hours_by_assignment` — Confirm Project-Based Classification

**Priority:** Must Have
**Source:** Design brief — alignment requirement

**Acceptance Criteria:**
- Verify (and document in view DDL comments) that `vw_project_hours_by_assignment` derives `category` exclusively from `ps_project_mapping.category` (with `ps_project_status.category` fallback), never from employee attributes
- If any employee-attribute-based classification logic exists in the view, remove it and replace with project-mapping lookup

---

## 9. Data Source Mapping

| Tab | Primary Source(s) | Secondary Source(s) |
|-----|-------------------|---------------------|
| Tab 1 — Weekly Operations Summary | `vw_project_hours_by_assignment`, `kpi_weekly_snapshots` | `clockify_projects`, `escalations` |
| Tab 2 — PS Project Status | `ps_project_status`, `vw_project_hours_summary` | `escalations`, `ps_project_mapping` |
| Tab 3 — PS Profitability | `vw_project_hours_summary`, `ps_resource_forecast_v2`, `ps_profitability_rates` | `ps_project_status`, `clockify_users` |
| Tab 4 — MC Service Delivery | `vw_project_hours_by_assignment`, `vw_project_hours_summary` | `escalations`, Jira MC tickets |
| Tab 5 — Missing Time Report | `vw_time_compliance_history` | `missing_time_reasons`, `clockify_users` |
| Tab 6 — Resource Forecast | `ps_resource_forecast_v2`, `ps_resource_forecasts`, `ai_pm_forecast_accuracy` | `clockify_detailed_time_entries` |
| Tab 7 — Resource Capacity | `ps_resource_forecast_v2`, `clockify_users` | `ps_resource_forecasts` |
| Tab 8 — PS Delivery Analysis | `ai_analysis_by_project`, `ai_analysis_by_user` | — |
| Tab 9 — Non-Billable Analysis | `vw_project_hours_by_assignment`, `vw_project_hours_summary` | `clockify_users`, `ps_project_mapping` |
| Tab 10 — MC V2 Audit | `mc_v2_audit_artifacts`, `mc_v2_audit_by_customer` | Jira API, Confluence API |
| Tab 11 — Project Hours Trend | `vw_project_hours_summary` | — |
| Tab 12 — Escalations | `escalations` | `ps_project_status` |
| Tab 13 — Productive Utilization | `vw_utilization_history` | `clockify_users` |
| Tab 14 — Project Time Detail | `vw_project_time_detail` (enhanced) | — |
| Tab 15 — Customer Status Assignments | `ps_project_status` | — |
| Tab 16 — Project Runway | `vw_project_hours_summary`, `ps_project_status` | `ps_resource_forecast_v2` |
| Tab 17 — Organizational KPI Scorecard | `kpi_weekly_snapshots` via `kpi-weekly-snapshots-prod` SPICE dataset | — |

---

## 10. Non-Functional Requirements

#### NFR-001: Page Load Performance

**Source:** Cloudelligent recommended best practice — pending client confirmation [PENDING: performance target confirmation — OQ-005]

Each tab shall render its initial view within 5 seconds under normal load, assuming SPICE/RDS data is pre-loaded for the default filter state.

#### NFR-002: Data Freshness

**Source:** Cloudelligent recommended best practice — pending client confirmation [PENDING: data refresh cadence confirmation — OQ-006]

Dashboard data shall reflect Clockify and Jira data imported within the last 24 hours. Data freshness timestamp displayed in the Streamlit sidebar: `"Data last updated: {timestamp} UTC"`.

#### NFR-003: Access Control

**Source:** Assumption — consistent with existing dashboard access model

Dashboard access governed by existing Streamlit authentication layer. No new roles introduced in this redesign.

#### NFR-004: Browser Compatibility

**Source:** Cloudelligent recommended best practice

Dashboard shall render correctly in Chrome (latest), Firefox (latest), and Safari (latest) at 1440px minimum viewport width.

#### NFR-005: PostgreSQL View Performance

**Source:** Assumption

New views (`vw_time_compliance_history`, `vw_utilization_history`) shall execute within 10 seconds on the current RDS instance for a 52-week lookback. Appropriate indexes on `(clockify_user_id, week_start_date)` shall be created as part of the migration.

---

## 11. Edge Cases & Failure Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| User has `practice_area = NULL` | Treated as `'Internal'` in all queries; excluded from PS-specific tabs (Tabs 3, 7, 13) |
| Project has no entry in `ps_project_mapping` | Category falls back to `ps_project_status.category`; falls back to `'Other'` if also absent |
| `budget_hours = NULL` or 0 on `ps_project_status` | Budget Burn % shown as `'—'`; project excluded from SOW budget chart (Tab 3) and runway chart (Tab 16) |
| Burn rate = 0 (no hours in last 4 weeks) | Model Est. Completion shown as `'—'`; project excluded from At Risk count |
| Confluence API unavailable during Lambda run | `error_message` populated with error; `artifact_verified_at` not updated; previous result preserved; Lambda logs error and continues to next issue |
| PM forecast hours exceed capacity by > 200% | Flag in FR-07-005 table; no cap applied — raw data displayed |
| User has 0 capacity hours (`weekly_capacity_hours = 0 or NULL`) | Excluded from utilization % calculations; shown in headcount |
| Week with no time entries for any user | All hourly KPIs show `0`; compliance counts reflect active headcount with 0 compliant |
| `ai_analysis_by_project` has no data for selected week | Section shows: `"No AI analysis available for the selected week."` |
| `mc_v2_audit_by_customer.executive_summary` is NULL | Displays: `"No AI summary available for this customer."` (per FR-10-005) |
| `ps_resource_forecast_v2` returns no data for future weeks | Capacity heatmap cells shown as grey with `"No forecast"` tooltip |

---

## 12. Assumptions

| ID | Assumption |
|----|------------|
| A-001 | `clockify_users` has an `is_active` boolean column; inactive users are excluded from compliance and utilization denominators |
| A-002 | `clockify_users` has `full_name`, `pod_assignment`, and `weekly_capacity_hours` columns — already in use by existing views |
| A-003 | `ps_project_status.engineer` is a single VARCHAR field; engineer-splitting logic in Tab 15 handles comma-separated values |
| A-004 | The `category` field in `ps_project_mapping` uses values `'PS'`, `'MC'`, `'FinOps'`, and `'Other'`; NB sub-categories (Presales, Training, etc.) are encoded in project names or a separate mapping field |
| A-005 | `clockify_users.practice_area` will be backfilled for all active users before any tab relying on it goes live |
| A-006 | `ps_resource_forecast_v2` schema includes at minimum: `clockify_user_id`, `project_id`, `week_start_date`, `forecasted_hours` |
| A-007 | `ai_analysis_by_project` and `ai_analysis_by_user` are already populated by the existing AI analysis Lambda step |
| A-008 | The Confluence and Jira base URLs are available as Lambda environment variables |
| A-009 | `NULL` `practice_area` treated as `'Internal'` pending backfill completion |

---

## 13. Open Questions

| ID | Question | Impact | Options | Recommendation |
|----|----------|--------|---------|----------------|
| OQ-001 | What fields on `clockify_users` distinguish onshore vs offshore and FTE vs contractor? The spec assumes `location` and `employment_type` columns exist. | High — blocks Tab 3 KPI tiles, donuts, and profitability table | (a) Add `location` and `employment_type` columns; (b) derive from user name convention; (c) new mapping table | Add `location VARCHAR(20)` and `employment_type VARCHAR(20)` columns with Streamlit editor (same pattern as `practice_area`) |
| OQ-002 | Does `clockify_users` have `title` and `skill_area` fields for Tab 7's Available for Assignment table? | Medium — affects Tab 7 column completeness | (a) Add columns; (b) source from Jira user metadata; (c) omit columns until available | Add `title` and `skill_area` columns to `clockify_users` via migration |
| OQ-003 | How are "External Boards" defined for the MC V2 Audit KPI (Tile 5)? | Low — single KPI tile | (a) Jira boards not owned by Cloudelligent org; (b) boards where customer has direct Jira access | Confirm with MC lead before implementing |
| OQ-004 | Should users with `practice_area = NULL` be shown in compliance/utilization tabs as `'Internal'` or excluded entirely? | Medium — affects denominator accuracy | (a) Show as Internal; (b) Exclude until backfilled; (c) Show as 'Unknown' category | Show as `'Internal'` until backfill is complete; add a banner warning if > 5% of active users have null `practice_area` |
| OQ-005 | What is the acceptable page load time target for tabs with heavy aggregations (Tabs 5, 9, 13)? | Medium — affects view indexing decisions | 3s / 5s / 10s | 5 seconds at p95 recommended |
| OQ-006 | Is the current Lambda import cadence (assumed nightly) acceptable for the redesigned tabs, or does any tab require intraday refresh? | Medium — affects Lambda scheduling | Nightly / hourly / on-demand | Nightly is sufficient for weekly operational tabs; confirm |
| OQ-007 | For Tab 9 NB categorization: does `ps_project_mapping` include NB sub-category labels (Presales, Training, Internal Initiatives, Overhead), or is this derived from project name patterns? | High — blocks 12-week stacked bar (FR-09-002) | (a) Add `nb_subcategory` field to `ps_project_mapping`; (b) pattern match on project name | Add explicit `nb_subcategory` field to `ps_project_mapping` migration |
| OQ-008 | Who should have write access to the `ps_profitability_rates` form and the `practice_area` editor — any authenticated user or a specific admin role? | Medium — security consideration | (a) All authenticated users; (b) admin role only | Restrict to admin role; implement via `clockify_users.is_admin` boolean or equivalent |
