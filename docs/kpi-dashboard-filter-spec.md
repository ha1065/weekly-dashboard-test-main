# KPI Tracking Dashboard — Filter Control Specification

**Date:** 2026-07-09
**Version:** 1.0
**Author:** Product Analyst
**Status:** Specification — Analysis Only

---

## 1. COO Operational Dashboard — Filter Pattern Inventory

The COO Operational Dashboard (`coo-operational-analysis-prod`) has 8 sheets. Four of the eight sheets carry filter controls; the remaining four (Escalations, Compliance History, Utilization History, Resource Capacity) have no exposed filter controls.

### 1.1 Control Inventory by Sheet

| Sheet | Control Type | Title | Source | Notes |
|-------|-------------|-------|--------|-------|
| Weekly Pulse | `ParameterControl.DateTimePicker` | **"Reporting Week"** | `pWeekStart` | Date-only picker |
| PS Delivery | `ParameterControl.DateTimePicker` | **"Reporting Week"** | `pWeekStart` | — |
| PS Delivery | `FilterControl.Dropdown` | **"Health"** | `fg-ps-health` | Select All enabled |
| MC Service Delivery | `ParameterControl.DateTimePicker` | **"Reporting Week"** | `pWeekStart` | — |
| Time & Utilization | `ParameterControl.DateTimePicker` | **"Reporting Week"** | `pWeekStart` | — |
| Time & Utilization | `FilterControl.Dropdown` | **"Submission Status"** | `fg-compliance-status` | Select All enabled |

### 1.2 Underlying Parameter & Filter Configuration

**`pWeekStart` Parameter:**
- Type: `DateTimeParameterDeclaration`
- Default: `2026-06-22T20:00:00Z` (a specific Monday, UTC)
- Drives a `ParameterControl.DateTimePicker` on each sheet that needs it

**Category Filter Dropdowns (Health, Submission Status):**
- Filter type: `CategoryFilter`
- Match operator: `CONTAINS`
- `SelectAllOptions`: `FILTER_ALL_VALUES` — meaning the default state passes all values through
- `NullOption`: `ALL_VALUES` — nulls are shown
- DisplayOptions: `SelectAllOptions.Visibility = VISIBLE`, `TitleOptions.Visibility = VISIBLE`, font size `MEDIUM`

### 1.3 Established Patterns

**Pattern P-1 — Date Picker on Every Active Sheet.**
Every sheet that contains data visualizations driven by a reporting week has exactly one `ParameterControl.DateTimePicker` titled **"Reporting Week"**, bound to the shared parameter `pWeekStart`. Sheets that are purely historical or static (Escalations, Compliance History, Utilization History, Resource Capacity) omit it.

**Pattern P-2 — Category Dropdowns Are Sheet-Specific.**
The two category dropdowns (Health, Submission Status) appear only on the sheets where they are meaningful. They do not appear on every sheet.

**Pattern P-3 — Dropdown Display Options Are Identical.**
Both category dropdowns use the exact same `DisplayOptions` block: `SelectAllOptions.Visibility = VISIBLE`, `TitleOptions.Visibility = VISIBLE`, font size `MEDIUM`. This must be replicated on any new dropdown added to any dashboard.

**Pattern P-4 — No Dimension Dropdowns on the COO Dashboard.**
The COO dashboard does not expose `Practice Alignment`, `POD`, `Line of Business`, or `Individual` as filter controls. Those filters are implicit (the COO sees aggregate data). The KPI Tracking Dashboard targets a different audience (practice leads, staff) and therefore needs dimensional filters — this is an intentional divergence, not an inconsistency.

---

## 2. Streamlit App — Filter Pattern Inventory

The Streamlit app (`src/app.py`) has 6 top-level pages accessed via the sidebar radio: **Governance, Resource Forecast, Project Config, Data Management, AI Analysis, Settings.**

### 2.1 Date / Week Filter

- **Label:** "Quick Select" (inline selectbox, column-positioned)
- **Options:** `["Last Week", "Current Week", "Last 4 Weeks", "Custom Range"]`
- **Default:** "Last Week"
- **Pattern:** Appears once per page that shows time-series data; positioned in a column layout (`col1` of 3 columns); accompanied by a date-range "Custom Range" fallback
- **AI Analysis page:** Uses a separate `selectbox` labeled differently (week start options presented as formatted date labels), defaulting to the most recent available week

### 2.2 Dimensional Filters (Time Entry Detail expander, Governance page)

Displayed in a 5-column row inside the "Time Entry Detail" expander:

| Column | Label | Type | Options Source |
|--------|-------|------|---------------|
| col1 | **"Practice Alignment"** | `multiselect` | Hardcoded: `["Professional Services", "Managed Cloud", "IT Service Delivery", "Service Desk"]` |
| col2 | **"Location"** | `multiselect` | Hardcoded: `["Onshore", "Offshore", "Unknown"]` |
| col3 | **"POD Assignment"** | `multiselect` | Dynamic: `pod_assignment` distinct values from DB |
| col4 | **"Skill Area"** | `multiselect` | Dynamic: distinct values from DB |
| col5 | **"Show entries"** | `number_input` | N/A |

### 2.3 Resource Forecast Page Filters

- **"Filter by Resource"** — `multiselect`, dynamic from active users
- **"Filter by Client"** — `multiselect`, dynamic from DB
- **"Filter by PM"** — `multiselect`, dynamic from DB
- **"Filter by Type"** — `multiselect`, dynamic from DB
- **"Filter by Stage"** — `multiselect`, dynamic from DB
- **"Time Range"** — `selectbox`: `["All Weeks", "Next 4 Weeks", "Next 8 Weeks", "Next 12 Weeks", "All Future"]`

### 2.4 Streamlit Label Conventions

| Concept | Streamlit Label |
|---------|----------------|
| Practice/service line | **"Practice Alignment"** |
| Team grouping | **"POD Assignment"** |
| Line of business / service category | not consistently labeled; closest is the hardcoded practice options |
| Week/date range | **"Quick Select"** (with "Reporting Week" not used in Streamlit) |

The Streamlit app does not use the label "Line of Business" — that concept is captured by the `practice_alignment` field. "Line of Business" is a KPI dashboard construct that maps to the broader PS/MC/ITSD/SD categorization.

---

## 3. Gap Analysis — KPI Dashboard vs Established Patterns

### 3.1 Current KPI Dashboard Control Inventory

| Sheet | Control Type | Title | Source Filter | Underlying Column |
|-------|-------------|-------|--------------|------------------|
| OKR Scorecard (s1) | `FilterControl.RelativeDateTime` | "Reporting Week" | `f-s1-date` | `kpi_snapshots.week_start_date` |
| Practice Scorecard (s2) | `FilterControl.RelativeDateTime` | "Reporting Week" | `f-s2-date` | `kpi_practice.week_start` |
| Practice Scorecard (s2) | `FilterControl.Dropdown` | "Line of Business" | `fg-s2-lob` | `kpi_practice.line_of_business` |
| Practice Scorecard (s2) | `FilterControl.Dropdown` | "Practice Alignment" | `fg-s2-practice` | `kpi_practice.practice_alignment` |
| Staff Detail (s3) | `FilterControl.RelativeDateTime` | "Reporting Week" | `f-s3-date` | `kpi_staff.week_start` |
| Staff Detail (s3) | `FilterControl.Dropdown` | "Line of Business" | `fg-s3-lob` | `kpi_staff.line_of_business` |
| Staff Detail (s3) | `FilterControl.Dropdown` | "Practice Alignment" | `fg-s3-practice` | `kpi_staff.practice_alignment` |
| Staff Detail (s3) | `FilterControl.Dropdown` | "POD" | `fg-s3-pod` | `kpi_staff.pod_assignment` |
| Staff Detail (s3) | `FilterControl.Dropdown` | "Individual" | `fg-s3-staff` | `kpi_staff.user_name` |

### 3.2 Gap Analysis per Sheet

---

#### Sheet: OKR Scorecard (`sheet-kpi-s1`)

| Item | Finding | Severity |
|------|---------|---------|
| "Reporting Week" uses `FilterControl.RelativeDateTime` | **Wrong control type.** COO dashboard uses `ParameterControl.DateTimePicker` bound to a `DateTimeParameterDeclaration`. `RelativeDateTime` presents a relative-range picker (e.g., "last 7 days"), which is unsuitable for selecting a specific reporting week. The COO pattern selects a precise week-start date. | **High** |
| No parameter `pWeekStart` declared | The KPI dashboard has no `ParameterDeclarations` at all. `ParameterControl.DateTimePicker` requires a parameter declaration to bind to. This is a prerequisite for the fix above. | **High** |
| "Reporting Week" `DisplayOptions` | Current: `TitleOptions.Visibility = VISIBLE`, font `MEDIUM` — matches COO. `SelectAllOptions` not applicable to DateTimePicker. This is correct once the control type is fixed. | Info |
| No category dropdowns on s1 | Correct — the OKR Scorecard is a summary/executive view. No dimensional drilling is needed at this level. This is intentional, matching the COO pattern of omitting filters from summary sheets. | ✅ Correct |

---

#### Sheet: Practice Scorecard (`sheet-kpi-s2`)

| Item | Finding | Severity |
|------|---------|---------|
| "Reporting Week" uses `FilterControl.RelativeDateTime` | **Wrong control type.** Same issue as s1 — must be `ParameterControl.DateTimePicker` binding to `pWeekStart`. | **High** |
| "Line of Business" Dropdown | Control type and title are correct. `SelectAllOptions.Visibility = VISIBLE` and font `MEDIUM` — matches COO Dropdown pattern. No gap in structure. | ✅ Correct |
| "Practice Alignment" Dropdown | Control type and title are correct. DisplayOptions match. Label matches Streamlit convention. | ✅ Correct |
| Control order | Current order: Reporting Week → Line of Business → Practice Alignment. This is a logical top-down hierarchy (date → broad category → specific practice). Acceptable. | ✅ Correct |
| Missing "POD Assignment" filter | The Practice Scorecard shows practice-level aggregates, not individual POD breakdowns. Omitting POD here is appropriate — it belongs on Staff Detail only. | ✅ Correct |

---

#### Sheet: Staff Detail (`sheet-kpi-s3`)

| Item | Finding | Severity |
|------|---------|---------|
| "Reporting Week" uses `FilterControl.RelativeDateTime` | **Wrong control type.** Same issue as s1 and s2. | **High** |
| "Line of Business" Dropdown | Correct. | ✅ Correct |
| "Practice Alignment" Dropdown | Correct. | ✅ Correct |
| "POD" Dropdown — label too short | The label **"POD"** does not match the Streamlit convention of **"POD Assignment"**. The COO dashboard does not have a POD filter for reference, but Streamlit consistently uses "POD Assignment". The label should be expanded for clarity. | **Medium** |
| "Individual" Dropdown — label inconsistent | The label **"Individual"** does not match any established convention. Streamlit uses resource/staff names but has no single label. The COO dashboard equivalent does not exist. Recommend renaming to **"Staff Member"** to be self-descriptive and unambiguous. | **Low** |
| Control count | 5 controls (date + 4 dropdowns) is appropriate for a staff-level detail sheet. No missing controls. | ✅ Correct |

---

### 3.3 Summary of Gaps

| # | Sheet(s) | Control | Issue | Priority |
|---|---------|---------|-------|---------|
| G-1 | s1, s2, s3 | "Reporting Week" | Wrong type: `RelativeDateTime` → must be `DateTimePicker` bound to `pWeekStart` parameter | **High** |
| G-2 | All | — | No `pWeekStart` `DateTimeParameterDeclaration` exists in KPI dashboard | **High** (prerequisite for G-1) |
| G-3 | s3 | "POD" | Label should be "POD Assignment" to match Streamlit convention | **Medium** |
| G-4 | s3 | "Individual" | Label should be "Staff Member" for clarity | **Low** |

---

## 4. Recommended Filter Control Specification

### Prerequisites (apply to the analysis definition before any sheet changes)

**Add `pWeekStart` Parameter Declaration:**
```
Type: DateTimeParameterDeclaration
Name: pWeekStart
DefaultValues.StaticValues: [most recent completed Monday, e.g. 2026-07-06T20:00:00Z]
```

This mirrors the COO dashboard parameter exactly, enabling cross-dashboard consistency if the two are ever combined into a single view or compared by users.

---

### Sheet: OKR Scorecard (`sheet-kpi-s1`)

| # | Attribute | Value |
|---|-----------|-------|
| 1 | Control type | `ParameterControl.DateTimePicker` |
| 2 | Title | **"Reporting Week"** |
| 3 | Source parameter | `pWeekStart` |
| 4 | Position | Top-left of sheet filter bar |
| 5 | Default value | Inherited from `pWeekStart` parameter default (most recent completed Monday) |
| 6 | Select All option | N/A — not applicable to DateTimePicker |
| 7 | DisplayOptions | `TitleOptions.Visibility = VISIBLE`, `FontSize.Relative = MEDIUM` |
| 8 | Underlying filter | Remove `FilterControl.RelativeDateTime` (f-s1-date). Replace with a `TimeRangeFilter` or `ParameterFilter` binding `week_start_date = pWeekStart` on dataset `kpi_snapshots` |

**No additional controls needed on OKR Scorecard.** This sheet is an executive summary; dimensional drilling is not appropriate.

---

### Sheet: Practice Scorecard (`sheet-kpi-s2`)

| # | Control | Type | Title | Source | Position | Default | Select All |
|---|---------|------|-------|--------|----------|---------|-----------|
| 1 | Date filter | `ParameterControl.DateTimePicker` | **"Reporting Week"** | `pWeekStart` | Top-left (first) | Most recent Monday | N/A |
| 2 | LOB filter | `FilterControl.Dropdown` | **"Line of Business"** | `fg-s2-lob` | Second | All (Select All enabled) | Yes — visible |
| 3 | Practice filter | `FilterControl.Dropdown` | **"Practice Alignment"** | `fg-s2-practice` | Third | All (Select All enabled) | Yes — visible |

**Control order rationale:** Date → LOB → Practice follows the hierarchy from broad to specific, matching how a user would drill down (first select the period, then narrow to a service line, then to a practice within it).

**DisplayOptions for all Dropdowns:**
```
SelectAllOptions.Visibility: VISIBLE
TitleOptions.Visibility: VISIBLE
TitleOptions.FontConfiguration.FontSize.Relative: MEDIUM
```

**Replace** the existing `FilterControl.RelativeDateTime` (f-s2-date) with the `ParameterControl.DateTimePicker` described above. The underlying filter binding for the date field should use a `ParameterFilter` tying `kpi_practice.week_start` to `pWeekStart`.

---

### Sheet: Staff Detail (`sheet-kpi-s3`)

| # | Control | Type | Title | Source | Position | Default | Select All |
|---|---------|------|-------|--------|----------|---------|-----------|
| 1 | Date filter | `ParameterControl.DateTimePicker` | **"Reporting Week"** | `pWeekStart` | Top-left (first) | Most recent Monday | N/A |
| 2 | LOB filter | `FilterControl.Dropdown` | **"Line of Business"** | `fg-s3-lob` | Second | All | Yes — visible |
| 3 | Practice filter | `FilterControl.Dropdown` | **"Practice Alignment"** | `fg-s3-practice` | Third | All | Yes — visible |
| 4 | POD filter | `FilterControl.Dropdown` | **"POD Assignment"** *(rename from "POD")* | `fg-s3-pod` | Fourth | All | Yes — visible |
| 5 | Staff filter | `FilterControl.Dropdown` | **"Staff Member"** *(rename from "Individual")* | `fg-s3-staff` | Fifth | All | Yes — visible |

**Control order rationale:** Date → LOB → Practice → POD → Staff Member follows a strict top-down hierarchy. Each subsequent filter narrows the population visible in the prior filter. This also matches the data model dependency: LOB contains practices, practices contain PODs, PODs contain staff members.

**Replace** the existing `FilterControl.RelativeDateTime` (f-s3-date) with the `ParameterControl.DateTimePicker` described above. Bind `kpi_staff.week_start` to `pWeekStart` via a `ParameterFilter`.

**DisplayOptions for all Dropdowns:** same as s2 — `SelectAllOptions.Visibility: VISIBLE`, `TitleOptions.Visibility: VISIBLE`, font size `MEDIUM`.

---

## 5. Consistency Rules to Enforce Across All Dashboards

The following rules must govern filter controls on the COO Operational Dashboard, the KPI Tracking Dashboard, and any future QuickSight dashboards built from this data.

---

**Rule 1 — One Control Type for the Reporting Week: `ParameterControl.DateTimePicker` only.**

The reporting-week filter must always be a `ParameterControl.DateTimePicker` bound to a `DateTimeParameterDeclaration` named `pWeekStart`. `FilterControl.RelativeDateTime` is prohibited for this purpose because it presents a relative-range concept (e.g., "last 7 days") rather than a precise week-start date selection. All three KPI sheets currently violate this rule.

---

**Rule 2 — "Reporting Week" is the canonical label for the date filter; it must appear on every data sheet.**

Every sheet that displays metrics driven by a specific reporting week must carry exactly one `ParameterControl.DateTimePicker` titled **"Reporting Week"**. Sheets that display purely static reference data or all-time aggregates (e.g., a team directory) are exempt.

---

**Rule 3 — All category `FilterControl.Dropdown` controls must have `SelectAllOptions.Visibility = VISIBLE`.**

This ensures users can reset a filter to "all values" with one click. Both COO dashboard dropdowns (Health, Submission Status) already follow this rule. All KPI dashboard dropdowns currently follow it. Any new dropdown must include this setting.

---

**Rule 4 — Dimensional filter labels must match Streamlit conventions.**

When a filter corresponds to a dimension that also appears in the Streamlit app, use the same label:

| Dimension | Required QuickSight Label | Streamlit Label |
|-----------|--------------------------|----------------|
| `practice_alignment` | "Practice Alignment" | "Practice Alignment" ✅ |
| `pod_assignment` | "POD Assignment" | "POD Assignment" ✅ |
| `line_of_business` | "Line of Business" | (not in Streamlit, unique to QS) |
| `user_name` / staff | "Staff Member" | "Filter by Resource" (closest) |

The KPI dashboard currently uses "POD" (too short) and "Individual" (ambiguous) — both should be renamed.

---

**Rule 5 — Filter controls must follow the hierarchy order: Date → Category → Sub-category → Group → Individual.**

The left-to-right (or top-to-bottom) control order must reflect the logical drill-down hierarchy so filters compose predictably. The mandatory sequence for any sheet that uses multiple filters:

1. **Reporting Week** (always first)
2. **Line of Business** (broadest dimension)
3. **Practice Alignment** (within a LOB)
4. **POD Assignment** (within a practice)
5. **Staff Member** (within a POD)

A sheet may omit lower levels (e.g., OKR Scorecard has only the date picker) but must not reorder the levels it does use.

---

## 6. Implementation Checklist

This is a specification document. The following items require implementation by the dashboard developer:

- [ ] Add `DateTimeParameterDeclaration` named `pWeekStart` to the KPI analysis definition
- [ ] On `sheet-kpi-s1`: replace `FilterControl.RelativeDateTime` with `ParameterControl.DateTimePicker` titled "Reporting Week"; update underlying filter binding
- [ ] On `sheet-kpi-s2`: replace `FilterControl.RelativeDateTime` with `ParameterControl.DateTimePicker` titled "Reporting Week"; update underlying filter binding
- [ ] On `sheet-kpi-s3`: replace `FilterControl.RelativeDateTime` with `ParameterControl.DateTimePicker` titled "Reporting Week"; update underlying filter binding
- [ ] On `sheet-kpi-s3`: rename "POD" dropdown title to **"POD Assignment"**
- [ ] On `sheet-kpi-s3`: rename "Individual" dropdown title to **"Staff Member"**
- [ ] Verify default value of `pWeekStart` is set to the most recent completed Monday at time of deployment
- [ ] Confirm all `FilterControl.Dropdown` controls retain `SelectAllOptions.Visibility = VISIBLE` after any updates
