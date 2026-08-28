# COO Dashboard Views — Derivation Reference

This document describes every PostgreSQL view created for the COO dashboards
(`coo-dashboards-prod`) and explains exactly how each column is derived.

---

## Source Tables

| Table | Description |
|-------|-------------|
| `clockify_detailed_time_entries` | Raw time entries imported from Clockify (one row per entry) |
| `clockify_projects` | Clockify project metadata, including `pod_assignment` |
| `clockify_users` | Clockify user roster with `weekly_capacity_hours` per user |
| `ps_project_mapping` | Maps Clockify client/project names to canonical PS client names and category |
| `ps_project_status` | Jira-sourced project health records (one row per Jira project, latest sync) |
| `escalations` | Jira-sourced escalation issues |
| `kpi_weekly_snapshots` | One row per Monday — KPI values written by `kpi_snapshot.py` |

---

## Migration 050 — Project Hours Views

### `vw_project_hours_summary`

**Purpose:** Weekly hours per (client, project, week) for the last 30 weeks,
enriched with rolling averages, trend, performance band, delivery health from
Jira, and escalation flag. Powers the Project Hours and Project Detail sheets.

**Internal CTEs:**

| CTE | What it does |
|-----|-------------|
| `tier1` | Pulls explicit Clockify→PS client name mappings from `ps_project_mapping` (active rows only). `DISTINCT ON` picks the highest-priority mapping when multiple rows match the same clockify client+project. |
| `tier2` | Fallback for PS clients that have no entry in `ps_project_mapping` — uses `ps_project_status.client_name` directly as both the canonical and Clockify name. |
| `mapping` | UNION of tier1 and tier2, used for the LEFT JOIN on time entries. |
| `weekly_hours` | Aggregates `clockify_detailed_time_entries` by `(week_start_date, client_name, project_name)`. Only looks back 30 weeks. Resolves `pod_assignment` from `clockify_projects` and strips JSON braces/quotes from the value. |
| `avg_4w` | Average weekly hours per project over the **4 complete weeks ending 2 weeks ago** (weeks −5 to −2 relative to the current Monday). Excludes the most recent complete week so the average is always a stable baseline. |
| `avg_12w` | Same window but over **12 complete weeks** (weeks −13 to −2). |
| `prior_week` | Hours for the week 2 Mondays ago — used to compute trend direction. |
| `ps` | Latest `ps_project_status` row per (client, project), used to enrich health, PM/SA, and budget columns. |
| `escalated_clients` | Distinct lowercase `customer_name` values from open (unresolved) escalations. |

**Column derivations:**

| Column | Derived from |
|--------|-------------|
| `week_start_date` | `DATE_TRUNC('week', entry_date)::DATE` — ISO Monday of the time entry |
| `client_name` | Canonical client name from `ps_project_mapping`; falls back to Clockify `client_name` |
| `clockify_client_name` | Raw `client_name` from `clockify_detailed_time_entries` |
| `project_name` | `clockify_detailed_time_entries.project_name` |
| `category` | `ps_project_mapping.category` if mapped; else `ps_project_status.category`; else `'Other'` |
| `practice_alignment` | Human-readable label: `PS` → `'Professional Services'`, `MC` → `'Managed Cloud'`, `FinOps` → `'FinOps'`, else the raw category |
| `pod_assignment` | `clockify_projects.pod_assignment` with JSON braces/quotes stripped |
| `total_hours` | `SUM(duration_hours)` for the week |
| `billable_hours` | `SUM(duration_hours)` where `te.billable = TRUE` |
| `billable_pct` | `billable_hours / total_hours × 100`, rounded to 1 dp; 0 if no hours |
| `resource_count` | `COUNT(DISTINCT clockify_user_id)` for the week |
| `entry_count` | Raw count of time entry rows for the week |
| `avg_hours_4w` | 4-week rolling average (CTE `avg_4w`); 0 if no prior data |
| `avg_hours_12w` | 12-week rolling average (CTE `avg_12w`); 0 if no prior data |
| `pct_change_vs_4w` | `(total_hours − avg_hours_4w) / avg_hours_4w × 100`; 0 if no baseline |
| `trend` | `'Up'` / `'Down'` / `'Stable'` — compares `total_hours` to `prior_hours` (2 weeks ago) |
| `performance_band` | `'New'` if no 4w baseline; `'Above Average'` if >110% of avg; `'Below Average'` if <90%; else `'Average'` |
| `jira_status` | `ps_project_status.status`; `'No Jira Project'` if no match |
| `current_health` | `COALESCE(ps.current_health, ps.health_overall)` from `ps_project_status` |
| `health_overall` | `ps_project_status.health_overall` |
| `health_budget` | `ps_project_status.health_budget` |
| `health_scope` | `ps_project_status.health_scope` |
| `health_schedule` | `ps_project_status.health_schedule` |
| `budget_hours` | `ps_project_status.budget_hours` |
| `project_manager` | `ps_project_status.project_manager` |
| `solution_architect` | `ps_project_status.solution_architect` |
| `planned_start / planned_end` | `ps_project_status` date columns |
| `actual_kickoff / actual_completion` | `ps_project_status` date columns |
| `escalation` | `'Yes'` if `LOWER(client_name)` matches any open escalation's `customer_name`; else `'No'` |

---

### `vw_project_hours_current_week`

**Purpose:** Thin filter over `vw_project_hours_summary` that returns only the
most recent complete week. Used for KPI scorecard tiles that need a single-week
snapshot without importing 30 weeks of history into SPICE.

**Derivation:**

```sql
WHERE week_start_date = DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '1 week'
```

The "current week" is always the **last completed Monday week** — i.e., the
Monday that started 7 days before the current Monday. This ensures the week's
hours are fully submitted before being surfaced.

**Columns:** Subset of `vw_project_hours_summary` — excludes less-used fields
(`clockify_client_name`, `pod_assignment`, `entry_count`, `health_*` detail,
`jira_status`, PM/SA, and date columns).

---

### `vw_category_hours_summary`

**Purpose:** Rolls up `vw_project_hours_summary` to practice level
(`category` + `practice_alignment`) per week. Powers the practice-level
bar/line charts (PS vs MC vs FinOps).

**Internal CTEs:**

| CTE | What it does |
|-----|-------------|
| `weekly_category` | Groups `vw_project_hours_summary` by `(week_start_date, category, practice_alignment)`, summing hours and counting distinct projects/clients/resources |
| `cat_avg_4w` | Same 4-week window as `vw_project_hours_summary` (weeks −5 to −2), but at category level |
| `cat_avg_12w` | 12-week window at category level |

**Column derivations:**

| Column | Derived from |
|--------|-------------|
| `week_start_date` | Passed through from `vw_project_hours_summary` |
| `category` | `PS`, `MC`, `FinOps`, or `Other` |
| `practice_alignment` | Human-readable label (same mapping as parent view) |
| `project_count` | `COUNT(DISTINCT project_name)` within the category for the week |
| `client_count` | `COUNT(DISTINCT client_name)` within the category for the week |
| `total_hours` | Sum of all project `total_hours` in the category |
| `billable_hours` | Sum of all project `billable_hours` in the category |
| `billable_pct` | `billable_hours / total_hours × 100`; 0 if no hours |
| `resource_count` | Sum of per-project `resource_count` — note this may double-count users who appear on multiple projects |
| `avg_hours_4w` | Category-level 4-week rolling average |
| `avg_hours_12w` | Category-level 12-week rolling average |

---

## Migration 051 — KPI Snapshots

### `kpi_weekly_snapshots` (table, not a view)

**Purpose:** Persistent store of weekly KPI values — one row per Monday.
Written by `kpi_snapshot.py` running as a Lambda (invoked by EventBridge on
Monday mornings). Targets are stored per-row so they can be adjusted over time
without rerunning history.

**Population:** `kpi_snapshot.py` computes each KPI from live source tables
at run time and upserts the row via `INSERT ... ON CONFLICT (week_start_date) DO UPDATE`.
Historical rows are backfilled by invoking the Lambda with `{"mode":"snapshot_kpis","week_start":"YYYY-MM-DD"}`.

**Column derivations:**

| Column | Derived from |
|--------|-------------|
| `week_start_date` | The Monday that starts the reporting week (PRIMARY KEY) |
| `week_num` | `EXTRACT(WEEK FROM week_start_date)` |
| `snapshot_taken_at` | Timestamp when `kpi_snapshot.py` last wrote the row |
| `billable_util_pct` | `total_billable_hours / total_available_hours × 100` — billable hours from `clockify_detailed_time_entries` divided by capacity (`clockify_users.weekly_capacity_hours` summed across active users) |
| `productive_util_pct` | `(billable + presales + productive_nb) / total_available_hours × 100` |
| `time_compliance_pct` | Users who logged ≥ their weekly capacity / total active users × 100 |
| `presales_hours` | Hours where Clockify project/tag is classified as presales |
| `productive_nb_hours` | Productive but non-billable hours (internal work, training, etc.) |
| `total_available_hours` | Sum of `weekly_capacity_hours` across all active Clockify users for the week |
| `total_billable_hours` | Sum of `duration_hours` where `billable = TRUE` |
| `target_billable_util_pct` | Default 75.0 — override per-row when targets change |
| `target_productive_util_pct` | Default 80.0 |
| `target_time_compliance_pct` | Default 95.0 |
| `ps_active_projects` | `COUNT(*)` from `ps_project_status` where category=PS, not Done, not excluded, has `actual_kickoff` |
| `ps_on_time_pct` | % of PS projects where `planned_end >= CURRENT_DATE` OR `actual_completion <= planned_end` |
| `ps_avg_duration_weeks` | `AVG((COALESCE(actual_completion, CURRENT_DATE) − actual_kickoff) / 7.0)` for active PS projects |
| `ps_projects_green/amber/red` | Count of PS projects by `COALESCE(current_health, health_overall)` |
| `ps_billable_hours` | Billable hours this week from `clockify_detailed_time_entries` where project maps to PS category |
| `ps_budget_hours_total` | `SUM(budget_hours)` across active PS projects |
| `ps_actual_hours_ytd` | Billable PS hours from Jan 1 of the snapshot year to `week_end` |
| `mc_*` | Same derivations as `ps_*` but filtered to `category = 'MC'` |
| `open_escalations` | `COUNT(*)` from `escalations` where `resolution_date IS NULL` and not Done/Resolved |
| `escalations_high_priority` | Count where `priority IN ('Highest', 'High')` and open |
| `escalations_med_priority` | Count where `priority = 'Medium'` and open |
| `avg_escalation_days_open` | `AVG(CURRENT_DATE − created_date::DATE)` for open escalations |
| `escalations_resolved_ytd` | Count where `resolution_date` is in the snapshot year |
| `active_resource_count` | Count of distinct active users in `clockify_users` |

---

### `vw_kpi_ytd`

**Purpose:** Thin view over `kpi_weekly_snapshots` that adds vs-target gap
columns and week-over-week delta columns. This is the primary dataset for all
KPI scorecards, trend lines, and executive summary charts.

**Filter:** Only rows from `2026-01-01` onwards.

**Added columns (not in the base table):**

| Column | Derivation |
|--------|-----------|
| `billable_util_vs_target` | `billable_util_pct − target_billable_util_pct` |
| `productive_util_vs_target` | `productive_util_pct − target_productive_util_pct` |
| `compliance_vs_target` | `time_compliance_pct − target_time_compliance_pct` |
| `billable_util_wow` | `billable_util_pct − LAG(billable_util_pct) OVER (ORDER BY week_start_date)` |
| `compliance_wow` | `time_compliance_pct − LAG(time_compliance_pct) OVER (ORDER BY week_start_date)` |
| `ps_ontime_vs_target` | `ps_on_time_pct − target_ps_on_time_pct` |
| `ps_billable_wow` | `ps_billable_hours − LAG(ps_billable_hours) OVER (ORDER BY week_start_date)` |
| `mc_ontime_vs_target` | `mc_on_time_pct − target_mc_on_time_pct` |
| `mc_billable_wow` | `mc_billable_hours − LAG(mc_billable_hours) OVER (ORDER BY week_start_date)` |
| `total_projects_red` | `COALESCE(ps_projects_red, 0) + COALESCE(mc_projects_red, 0)` |
| `total_projects_amber` | `COALESCE(ps_projects_amber, 0) + COALESCE(mc_projects_amber, 0)` |
| `total_projects_green` | `COALESCE(ps_projects_green, 0) + COALESCE(mc_projects_green, 0)` |
| `total_billable_hours_combined` | `COALESCE(ps_billable_hours, 0) + COALESCE(mc_billable_hours, 0)` |

All `LAG` deltas are `NULL` for the first week in the dataset (no prior row).
All vs-target gaps are negative when below target, positive when above.

---

## QuickSight Dataset Mapping

| QuickSight Dataset ID | Source View/Table | Used in |
|----------------------|-------------------|---------|
| `kpi-weekly-snapshots-prod` | `vw_kpi_ytd` | Both dashboards — KPI scorecards, trend lines |
| `project-hours-summary-prod` | `vw_project_hours_summary` | COO Operational — Project Hours, Project Detail sheets |
| `project-hours-current-week-prod` | `vw_project_hours_current_week` | COO Operational — current-week TreeMap |
| `category-hours-summary-prod` | `vw_category_hours_summary` | Both dashboards — practice-level bar/line charts |
| `project-delivery-health-prod` | `ps_project_status` (direct SQL) | Both dashboards — health distribution bar chart |
| `escalations-detail-prod` | `escalations` (direct SQL) | COO Operational — Escalations table |
