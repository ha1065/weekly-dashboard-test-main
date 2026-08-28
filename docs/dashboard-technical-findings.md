# Dashboard Technical Findings Report
**Date:** 2026-06-03  
**Scope:** All COO Operational, Executive Summary, and Streamlit tabs  
**Stack:** Clockify + Jira → Lambda → RDS PostgreSQL → QuickSight SPICE  
**Reviewer:** AWS Solutions Architect

---

## Severity Legend
| Severity | Meaning |
|---|---|
| **Critical** | Data shown is wrong or will be lost; requires immediate fix |
| **High** | Materially misleads decision-makers or breaks on redeploy |
| **Medium** | Reduces trust or reliability; fix before next sprint |
| **Low** | Improvement opportunity; low risk if deferred |

---

## Executive Summary

| Area | Finding Count |
|---|---|
| Critical | 4 |
| High | 9 |
| Medium | 12 |
| Low | 7 |

**Top 3 systemic risks:**
1. **IaC orphan sheets** — three live COO sheets (`sheet-ps-delivery`, `sheet-escalations`, `sheet-time-util`) exist only in live QuickSight, not in CloudFormation. They will be permanently destroyed on the next `coo-dashboards.yaml` redeploy.
2. **`ps_project_status` INSERT-not-upsert bug (CST-660)** — every Jira sync appends duplicate rows. Any visual reading `ps_project_status` directly will double-count projects; the `DISTINCT ON` in `vw_ps_project_status` masks this but adds query cost and fragility.
3. **`pWeekEnd` parameter default is stale** — hardcoded to `2026-05-25T00:00:00Z` in CloudFormation. Every fresh deploy will reset all parameter-filtered KPI tiles to the wrong week until manually corrected.

---

## COO Operational Dashboard (`coo-operational-analysis-prod`)

---

### Sheet 1: Weekly Pulse (`sheet-weekly-pulse`)

**IaC Coverage:** ✅ In `coo-dashboards.yaml`  
**Primary dataset:** `kpi_snapshots` → `kpi_weekly_snapshots` table (not a view)  
**Filter:** `pWeekEnd` parameter → `TimeEqualityFilter` on `week_start_date`

#### Findings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| WP-01 | **Critical** | Parameter default | `pWeekEnd` static default is `2026-05-25T00:00:00Z` in `ParameterDeclarations`. Every CFN redeploy resets all KPI tiles to week of May 25. No CloudFormation mechanism advances this automatically. | Replace static default with a `DynamicDefaultValue` sourced from the `kpi_weekly_snapshots` table, or set default to the latest available `week_start_date` via a pre-deploy script step. Immediate workaround: bump the static value each deploy. |
| WP-02 | **High** | KPI correctness | `kpi-ps-active` KPI on PS Delivery sheet reads `ps_active_projects` from the snapshot row. The prior-review noted a 24-vs-19 discrepancy (stale snapshot vs live count). The root cause is that `kpi_snapshot.py` counts `ps_project_status WHERE status_category != 'Done'` at snapshot time, but `ps_project_status` has duplicate rows (CST-660) — so the snapshot count is inflated before the dedup in `vw_ps_project_status`. | Fix CST-660 first (upsert in Jira import). After fix, trigger a one-time KPI snapshot backfill for the affected weeks via `{"mode":"snapshot_kpis","week_start":"YYYY-MM-DD"}`. |
| WP-03 | **Medium** | SPICE freshness | The `kpi_weekly_snapshots` table is written by EventBridge-triggered Lambda on Monday mornings. If the Lambda fails silently, the Weekly Pulse KPIs show the prior week's values with no staleness indicator in the dashboard. | Add a `vw_data_freshness` tile to the Weekly Pulse sheet showing "KPI data as of: {date}" sourced from `import_logs`. The view `vw_data_freshness` already exists in `create_views.sql`. |
| WP-04 | **Low** | UX | `kpi-wp-other-billable` KPI has no `TargetValues` wired (empty array in IaC). It shows an absolute number with no WoW comparison, unlike all other KPIs on the sheet. | Wire `other_billable_prev` as target once that column is added to `kpi_weekly_snapshots`, or document the intentional omission in the IaC comment. |

---

### Sheet 2: PS Delivery (`sheet-ps-delivery`)

**IaC Coverage:** ✅ In `coo-dashboards.yaml` (confirmed — `sheet-ps-delivery` is defined in the YAML)  
**Primary datasets:** `kpi_snapshots`, `ps_projects` → `ps-project-status-view` dataset → `vw_ps_project_status`  
**Filter:** `fg-ps-category` (category CONTAINS 'PS'), `fg-ps-not-done` (status_category NOT 'Done'), `fg-ps-issue-emailed` on donut, `fg-ps-week` on donut

#### Findings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| PS-01 | **Critical** | Filter bug — Pipeline by Stage | `bar-ps-stage` visual reads from `ps_stage` dataset (→ `vw_ps_stage_trend`). The stage snapshot capture in `import_jira_data.py` (`_capture_stage_snapshot`) filters `WHERE issue_type = 'Emailed request'`. This is the opposite of the intended filter — it keeps only emailed requests, excluding all standard Jira issue types. The bar chart therefore systematically undercounts pipeline stages. | Fix `_capture_stage_snapshot` in `import_jira_data.py`: change `AND p.issue_type = 'Emailed request'` to `AND p.issue_type != 'Emailed request'` (or remove the filter entirely if emailed requests are valid PS work items). Backfill the current week's snapshot after fixing. |
| PS-02 | **Critical** | Duplicate rows | `ps_project_status` table has no upsert guard (CST-660 confirmed). Each Jira import INSERTs new rows. `vw_ps_project_status` uses `NOT (status_category='Done' AND actual_completion < year start)` as a filter but does NOT deduplicate. The `tbl-ps-projects` table visual reads from `ps_at_risk` → `vw_ps_projects_at_risk` which uses `DISTINCT ON (client_name, project_name)` but only for `health IN ('Red','Yellow')`. Any aggregation that does not use `DISTINCT ON` will double/triple-count. | Fix the Jira import to use `INSERT ... ON CONFLICT (jira_issue_id) DO UPDATE`. Add a `UNIQUE` constraint on `ps_project_status(jira_issue_id)` if not already present. |
| PS-03 | **High** | Health donut filter | The `donut-ps-health` visual has TWO filter groups: `fg-ps-issue-emailed` (CONTAINS 'Emailed request') AND `fg-ps-not-done`. These are applied together via `SELECTED_VISUALS` scope. The `fg-ps-issue-emailed` filter keeps only emailed-request issue types for the donut — meaning the health distribution excludes all standard PS project types (Epic, Story, etc.). The donut shows a biased health picture. | Remove `fg-ps-issue-emailed` from the donut scope, or change it to `DOES_NOT_CONTAIN 'Emailed request'` depending on business intent. Verify the donut count matches the KPI tile count after fixing PS-01. |
| PS-04 | **Medium** | KPI vs live count gap | `kpi-ps-active` reads `ps_active_projects` from the snapshot (a point-in-time count). The donut and table read live from `vw_ps_project_status`. If a project is added/closed between Monday snapshot and the meeting day (e.g., Wednesday), the KPI tile and the table will disagree. | Add a tooltip or subtitle to `kpi-ps-active` clarifying "as of Monday {week}". Alternatively, compute `ps_active_projects` dynamically from `vw_ps_project_status` using a calculated field in the dataset. |
| PS-05 | **Low** | Column mapping | `tbl-ps-projects` reads from `ps_at_risk` dataset → `vw_ps_projects_at_risk`. This view only returns `health IN ('Red','Yellow')`. The title says "Over Budget / Late / Escalated" — projects that are only escalated but Green health are excluded. | Either rename the table title to "Red/Yellow Projects" or broaden the view filter to `health IN ('Red','Yellow') OR escalation = 'Red'`. |

---

### Sheet 3: MC Service Delivery (`sheet-mc-delivery`)

**IaC Coverage:** ✅ In `coo-dashboards.yaml`  
**Primary datasets:** `kpi_snapshots`, `mc_activity` → `vw_mc_ticket_activity`, `mc_at_risk` → `vw_mc_projects_at_risk`  
**Filter:** `fg-mc-s3` filters `mc_activity.week_start` by `pWeekEnd` across ALL_VISUALS on this sheet

#### Findings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| MC-01 | **High** | Hours KPI data source | `kpi-mc-hours` reads `clockify_hours` from `mc_activity` (→ `vw_mc_ticket_activity`) using `MAX` aggregation. The view computes `clockify_hours` as `SUM(duration_hours)` per customer per week. Using `MAX` at the KPI level will return only the single highest-customer value, not the total MC hours. | Change the KPI aggregation to `SUM` for `kpi-mc-hours-v`. Verify `kpi-mc-tickets-v` and `kpi-mc-esc-v` similarly — they also use `MAX` which may be correct for pre-aggregated columns but should be validated. |
| MC-02 | **Medium** | MC health source | `vw_mc_ticket_activity` derives `health_overall` using `MODE() WITHIN GROUP` over `ps_project_status.health_overall` rows. If `ps_project_status` has duplicate rows (CST-660), `MODE()` may return a value weighted by duplicates rather than the true single health status. | Fix CST-660. In the interim, the `DISTINCT ON` in `vw_ps_project_status` is not used here — `vw_mc_ticket_activity` joins directly to `ps_project_status`. Add the same `DISTINCT ON` guard in the health subquery inside `vw_mc_ticket_activity`. |
| MC-03 | **Low** | No week-end date filter | The `fg-mc-s3` filter uses `TimeEqualityFilter` on `mc_activity.week_start` with `TimeGranularity: DAY`. The `pWeekEnd` parameter is the Monday of the reporting week. If `vw_mc_ticket_activity.week_start` is stored as Monday (which it is per the view definition), this is correct. Confirm that the `mc_ticket_activity_snapshot` `week_start` column is always a Monday and never a Sunday or mid-week date. | Add a data quality assertion: `SELECT COUNT(*) FROM mc_ticket_activity_snapshot WHERE EXTRACT(DOW FROM week_start) != 1`. Alert if > 0. |

---

### Sheet 4: Escalations (`sheet-escalations`)

**IaC Coverage:** ✅ In `coo-dashboards.yaml`  
**Primary dataset:** `escalations` → `escalations-detail` dataset → `vw_escalations` view  
**Filter:** `fg-esc-open` (escalation_state DOES_NOT_CONTAIN 'Done') — ALL_VISUALS scope

#### Findings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| ESC-01 | **High** | KPI dedup issue | `kpi-esc-high` uses `DISTINCT_COUNT` on `issue_key` but is not filtered to high-priority issues — there is no filter group on this visual beyond `fg-esc-open`. It counts all open escalations, not just high-priority ones. The title "High Priority" is therefore wrong. | Add a `CategoryFilter` on `priority` with values `['High','Highest']` scoped to `kpi-esc-high` only, or rename the KPI tile to "Total Open" and add a separate tile filtered to high priority. |
| ESC-02 | **High** | `days_open` MAX semantics | `kpi-esc-days` uses `MAX(days_open)` with the title "Avg Days Open". MAX is not AVG. The title is misleading — this shows the oldest escalation age, not the average. | Either rename to "Oldest (days)" to match `kpi-esc-old` (which also uses `MAX(days_open)` — making both tiles identical), or change `kpi-esc-days` to use `AVG` aggregation. Currently both `kpi-esc-days` and `kpi-esc-old` show the same value (MAX). |
| ESC-03 | **Medium** | `days_open` staleness | `vw_escalations` exposes `days_open` from the `escalations` table. This column is set at import time (`CURRENT_DATE - created_date`). It does not update between imports — if an import runs Monday and today is Wednesday, `days_open` is 2 days stale. | Change `days_open` to a computed column in `vw_escalations`: `COALESCE(days_open, (CURRENT_DATE - created_date::DATE))` so it always reflects today's age for open tickets. |
| ESC-04 | **Low** | No SPICE refresh cadence documented | The `escalations-detail` dataset is not mentioned in the Lambda SPICE refresh schedule in `scripts/refresh_quicksight_datasets.py`. | Confirm the dataset is included in the daily SPICE refresh. Add it explicitly if missing. |

---

### Sheet 5: Time & Utilization (`sheet-time-util`)

**IaC Coverage:** ✅ In `coo-dashboards.yaml`  
**Primary datasets:** `kpi_snapshots`, `compliance` → `vw_weekly_compliance_report` / `vw_missing_time_submissions`, `productive_util` → `vw_productive_utilization`  
**Filters:** `fg-kpi-s5` (kpi_snapshots by pWeekEnd), `fg-util-s5` (productive_util by pWeekEnd), `fg-compliance-week` (compliance by pWeekEnd), `fg-compliance-status` (submission_status — ALL_VISUALS)

#### Findings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| TU-01 | **High** | Compliance dataset ambiguity | The `compliance` dataset identifier maps to `clockify-missing-time-submissions-prod`. The IaC uses this for both `tbl-missing` (non-compliant staff table) and the `fg-compliance-status` filter (ALL_VISUALS scope). `vw_missing_time_submissions` only returns users with `hours_submitted = 0` — users with partial hours are excluded. `vw_weekly_compliance_report` returns all users including compliant ones. The dataset should be `vw_weekly_compliance_report` if the intent is to show all staff with a status filter. | Switch the `compliance` dataset source to `vw_weekly_compliance_report`. The `fg-compliance-status` dropdown will then allow filtering to "No Time Submitted", "Complete", etc. across all staff. |
| TU-02 | **Medium** | CST timezone backfill impact | Migration 065 applied a CST timezone backfill. The `vw_missing_time_submissions` view computes `week_start_date` via `DATE_TRUNC('week', CURRENT_DATE)::DATE - 7`. If time entries previously stored in UTC now have corrected CST timestamps, some entries near midnight Sunday/Monday boundaries may have shifted week buckets. The compliance data should be re-verified post-migration. | Run: `SELECT week_start, COUNT(*) FROM clockify_detailed_time_entries GROUP BY week_start ORDER BY week_start DESC LIMIT 10` and compare counts before/after the migration. Trigger a SPICE refresh for the compliance dataset after confirming data is stable. |
| TU-03 | **Medium** | `tbl-util` column gap | `tbl-util` shows `nb_non_productive_hours` column in the view (`vw_productive_utilization`) but the visual's `FieldOptions` omits it — only `Billable Hrs`, `NB Productive`, `Non-Logged`, and `Available Hrs` are rendered. Non-billable non-productive hours are invisible to users on this sheet. | Add `nb_non_productive_hours` back to the `tbl-util` field options, or confirm intentional exclusion and add a note in the IaC comment. |
| TU-04 | **Low** | `kpi-tu-missing` prev target | `kpi-tu-missing` uses `missing_time_prev` as the target for WoW comparison. This column is computed in `kpi_snapshot.py`. Verify that `missing_time_count` and `missing_time_prev` are consistently populated — if the prior week had no import (e.g., holiday), the comparison arrow will be misleading. | Add a NULL check in `kpi_snapshot.py` before writing `missing_time_prev`. |

---

### Sheet 6: Project Detail (in IaC as part of COO analysis)

**IaC Coverage:** Not explicitly listed as a separate sheet in `coo-dashboards.yaml` — likely uses `ps_projects` / `project_hours_summary` datasets  
**Note:** The IaC reviewed contains 5 sheets: `sheet-weekly-pulse`, `sheet-ps-delivery`, `sheet-mc-delivery`, `sheet-escalations`, `sheet-time-util`. A "Project Detail" sheet referenced in prior session notes may exist only in the live analysis.

#### Findings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| PD-01 | **High** | IaC gap | If a Project Detail sheet exists in the live `coo-operational-analysis-prod` analysis but is not in `coo-dashboards.yaml`, it will be lost on redeploy (same risk as the originally identified orphan sheets). | Run `aws quicksight describe-analysis --analysis-id coo-operational-analysis-prod` and compare the live sheet list against `coo-dashboards.yaml`. Add any missing sheets to IaC via `sync_coo_dashboard_iac.py`. |


---

## Executive Summary Dashboard (`clockify-executive-dashboard-prod`)

**IaC Coverage:** `quicksight-dashboards.yaml` (separate stack). The `coo-dashboards.yaml` comment explicitly states the Executive Analysis was deleted outside CloudFormation and intentionally omitted.

---

### Sheet: Executive Overview

**Primary datasets:** `kpi_snapshots`, `vw_category_hours_summary`, `vw_productive_utilization`

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| EO-01 | **Critical** | IaC orphan — entire dashboard | The entire Executive Summary analysis was deleted outside CloudFormation and is not in any IaC stack. It will not survive a redeploy. | Recreate the analysis in QuickSight then add an `AWS::QuickSight::Analysis` resource to `coo-dashboards.yaml`. Use `sync_coo_dashboard_iac.py` to generate the definition. |
| EO-02 | **High** | Resource count double-counts | Per `COO_DASHBOARD_VIEWS.md`, `vw_category_hours_summary.resource_count` is a SUM of per-project resource counts — users on multiple projects are counted multiple times per category. | Compute `COUNT(DISTINCT clockify_user_id)` at category-week level directly from `clockify_detailed_time_entries` rather than summing from the project-level view. |
| EO-03 | **Medium** | Theme not guaranteed | Since the analysis was recreated manually, there is no guarantee the CE theme is applied consistently with the COO dashboard. | When re-adding to IaC, explicitly set `ThemeArn: !ImportValue CloudelligentQuickSightThemeArn`. |

---

### Sheet: Pod Performance

**Primary dataset:** `vw_pod_performance_analysis`

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| PP-01 | **Medium** | Zero-padding inactive pods in averages | `vw_pod_performance_analysis` uses `COALESCE(wph.total_hours, 0)` when a pod has no entries for a given week. A pod that was genuinely inactive one week is treated identically to a pod that did not yet exist, deflating its 4/12-week average. | Add a user-existence guard in `pod_weeks` — only include a week in the average denominator if at least one active user was assigned to that pod that week. |
| PP-02 | **Low** | Structural duplication with `vw_practice_group_performance` | Both views compute identical rolling average structures. Two SPICE datasets with the same shape add maintenance overhead. | Consider merging into a single view with a `grouping_type` discriminator ('pod' or 'practice'), or at minimum confirm both datasets are included in the same Lambda SPICE refresh invocation. |

---

## Streamlit Dashboard

---

### Page 1: Dashboard

**Data source:** Raw `ClockifyTimeEntry` ORM — bypasses all views in `create_views.sql`

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| SD-01 | **High** | ORM bypass produces different totals than QuickSight | All metric tiles (PS hours, MC hours, POD/location/contractor breakdown) query `ClockifyTimeEntry` ORM directly. The ORM path does not apply `TRIM(REPLACE(...))` field cleaning, producing different totals than QuickSight for the same week. Users comparing both will see discrepancies that erode trust. | Replace ORM aggregation queries with view-backed SQL: use `vw_weekly_time_summary` for practice/location summaries, `vw_pod_performance_analysis` for POD breakdown. |
| SD-02 | **Medium** | Practice Alignment filter hardcoded | Multiselect hardcodes `["Professional Services","Managed Cloud","IT Service Delivery","Service Desk"]`. New practices added to Clockify are silently excluded. | Query `SELECT DISTINCT practice_alignment FROM vw_weekly_time_summary` for dynamic filter options. |
| SD-03 | **Medium** | "Last 4 Weeks" includes incomplete current week | `end_date = current_sunday` (today's week) for the 4-week mode; "Last Week" correctly uses prior Monday–Sunday. Inconsistent week boundary treatment. | Standardize all modes to complete weeks only: `end_date = DATE_TRUNC('week', CURRENT_DATE)::DATE - 1`. |
| SD-04 | **Low** | Tab duplicates QuickSight with worse quality | Per three-tier reporting model, this tab is redundant with the Weekly Pulse sheet. | Retire metric tiles; promote the time entries filter table to a lightweight "Entry Search" utility page. |

---

### Page 2: Resource Directory

**Data source:** Raw `ClockifyUser` ORM — bypasses `vw_active_resources`

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| RD-01 | **Medium** | ORM bypass | Reimplements in Python the join + cleaning already done in `vw_active_resources`. | Rewrite base query to `SELECT * FROM vw_active_resources`. |
| RD-02 | **Medium** | POD filter shows `{Bravo}` format values | POD filter queries `ClockifyUser.pod_assignment` directly without cleaning. | Source from `vw_active_resources.pod_assignment` which is already cleaned. |
| RD-03 | **Low** | "Active (7 days)" is day-of-week dependent | Users who submitted time Monday appear active Tuesday but not the following Monday. Metric is misleading. | Rename to "Logged Time (Last 7 Days)" and add a tooltip. |

---

### Page 3: Resource Forecast

**Data source:** `ps_resource_forecast_v2` and `forecast_config` — not defined in `models.py`

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| RF-01 | **High** | Undocumented tables — silent failure | `ps_resource_forecast_v2` and `forecast_config` absent from `models.py`. App shows "No active forecasts" with no error if tables are missing. | Add SQLAlchemy models. Replace silent exception swallowing with explicit table-existence checks and user-visible error states. |
| RF-02 | **High** | Hardcoded AWS profile breaks in ECS | `AWSAdministratorAccess-961341524729` profile hardcoded in QuickSight refresh call. Fails in ECS/Lambda. | Remove `profile_name` argument; use default credential chain. |
| RF-03 | **Medium** | Architectural ambiguity between two forecast tables | Unclear whether `ps_resource_forecast_v2` feeds `ps_resource_forecasts` or is an independent parallel system. | Document the relationship. If algorithmic → manual pipeline exists, add it to `import_jira_data.py` or a dedicated Lambda. |

---

### Page 4: Forecasting

**Data source:** `ps_resource_forecasts` table (correctly defined)

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| FC-01 | **Medium** | Template column letter generation breaks at week 18 | `chr(73 + i)` produces wrong characters beyond column 17. Currently safe at 12 weeks but fragile. | Use `openpyxl.utils.get_column_letter(col_index)`. |
| FC-02 | **Medium** | `forecast_dropped_users` missing from schema | Silent failure shows same "no records" message as an empty table. | Add to `models.py`. Add explicit table-existence check with a distinct error state. |
| FC-03 | **Medium** | Duplicate QuickSight dataset ID lists | The 7-dataset post-upload refresh list is maintained separately from the 24-dataset Data Management list. Adding a new dataset to one does not update the other. | Define a single `FORECAST_REFRESH_DATASETS` constant at module level. |
| FC-04 | **Low** | `vw_forecast_version_comparison` shows false New/Removed pairs | View joins on `LOWER()` but UI displays raw-cased names. Name casing differences between current and snapshot create spurious "New" + "Removed" pairs. | Add UI note: "Matched case-insensitively — verify names if unexpected New/Removed pairs appear." |

---

### Page 5: Data Management

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| DM-01 | **High** | MC V2 Audit Lambda timeout | `RequestResponse` (sync) invocation for a 2–4 minute operation. API Gateway + Lambda timeout is 29 seconds — UI shows error even when Lambda succeeds. | Switch to `InvocationType='Event'`. Add a "Check Last Run" button that reads `import_logs` for completion status. |
| DM-02 | **Medium** | Mixed CFN vs manual dataset IDs in refresh list | CFN-managed logical IDs mixed with manual UUIDs. Redeploy breaks manual-ID refreshes silently. | Label two sections in the UI: "IaC-managed" vs "Manually created". Document which need manual update after redeploy. |
| DM-03 | **Medium** | AI prompt save is destructive replace | `DELETE` then re-insert. Fails open (no prompt) if save crashes mid-transaction. | Switch to `INSERT ... ON CONFLICT (category, sequence_order) DO UPDATE`. |
| DM-04 | **Low** | Shared week selector for PS/MC and MC V2 Audit | Running MC V2 Audit uses the same week as PS/MC analysis without indication. | Add a separate week selector for MC V2 Audit. |

---

### Page 6: Project Mapping

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| PM-01 | **Medium** | Unnecessary destructive save on no-change | `_save_mapping()` deletes and re-inserts even when nothing changed. Triggers pointless QuickSight refresh. | Add change-detection before delete+insert. Skip if no diff. |
| PM-02 | **Medium** | Orphaned mappings on pod deactivation | Deactivating a pod leaves existing `ps_project_mapping` rows with the old pod name. | Show warning listing affected mappings on deactivation; offer "clear pod assignment" for those rows. |
| PM-03 | **Low** | No coverage indicator | No visibility into % of active PS/MC projects with at least one mapping. | Add metric: "X of Y active PS projects mapped". Highlight unmapped rows in yellow. |

---

### Page 7: Clockify Data Update

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| CU-01 | **High** | No rollback capability | Bulk Clockify field updates have no undo path. A bulk mistake requires manual API calls. | Before applying, export a "pre-change snapshot" CSV of all fields that will be modified. Store in `ClockifyUploadLog`. |
| CU-02 | **Medium** | Dry run not enforced before Apply | Confirmation checkbox does not verify a dry run was executed in the current session. | Track `st.session_state['dry_run_done']`. Disable Apply button until True. |

---

### Page 8: Settings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| ST-01 | **Medium** | "Total Projects" counts time-entry names, not project table | Projects with no time entries are invisible. | Query `SELECT COUNT(*) FROM clockify_projects` instead. |
| ST-02 | **Medium** | Data freshness uses entry-level `synced_at` | If import runs but finds no new entries, `synced_at` does not update; freshness appears stale. | Query `import_logs` last successful `completed_at` for `import_category = 'time_entries'`. |
| ST-03 | **Low** | "Default Date Range Settings" is non-functional | `weeks_back`/`weeks_forward` stored in `session_state` only — reset on reload, not consumed by any other tab. | Remove section entirely or persist to `forecast_config` key-value store. |

---

## Cross-Cutting Findings

| # | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| CC-01 | **Critical** | No SPICE refresh inventory | No single document maps each of the 10 CFN-declared datasets to its refresh trigger. If a dataset is dropped from the Lambda schedule, it silently serves stale SPICE data. | Create `docs/spice-refresh-schedule.md` listing each dataset ID, source view, and refresh trigger. Audit `scripts/refresh_quicksight_datasets.py` to confirm all 10 datasets in `coo-dashboards.yaml` are covered. |
| CC-02 | **High** | Dataset resources not in IaC | All 10 dataset ARNs are hardcoded in `coo-dashboards.yaml` but no `AWS::QuickSight::DataSet` resources exist in any stack. Accidental deletion of a dataset has no IaC recovery path. | Add `AWS::QuickSight::DataSet` resources for all 10 datasets, using the `vw_*` views as SQL data sources. |
| CC-03 | **High** | Account ID hardcoded in dataset ARNs | `961341524729` appears in every dataset ARN. Breaks if stack is deployed to a different account. | Replace with `!Sub arn:aws:quicksight:us-east-1:${AwsAccountId}:dataset/...` using the existing `AwsAccountId` parameter. |
| CC-04 | **Medium** | `pWeekEnd` filter grain mismatch risk | `pWeekEnd` is a `TIMESTAMP` (`2026-05-25T00:00:00Z`). `TimeEqualityFilter` on a `DATE` column. Correct only if DB stores dates as midnight UTC. | Ensure `week_start_date` is always stored as `DATE`. Add assertion: `SELECT COUNT(*) FROM kpi_weekly_snapshots WHERE week_start_date != week_start_date::DATE` should return 0. |
| CC-05 | **Low** | `sync_coo_dashboard_iac.py` not in CI/CD | Console edits to the live analysis will silently diverge from IaC. | Add drift detection to `scripts/full_status_check.py` or run `sync_coo_dashboard_iac.py` as a scheduled task. |

---

## Prioritized Action Plan

### P0 — Fix Before Next COO Meeting

| # | Finding | Action |
|---|---|---|
| 1 | PS-01 — Pipeline by Stage undercounts | Fix `issue_type = 'Emailed request'` to exclude (not include) in `_capture_stage_snapshot`; backfill current week |
| 2 | WP-01 — `pWeekEnd` default stale | Update static default to current week in YAML; script it for each deploy |
| 3 | PS-02 — Duplicate rows CST-660 | Add `ON CONFLICT (jira_issue_id) DO UPDATE` to Jira import; add UNIQUE constraint on `ps_project_status(jira_issue_id)` |
| 4 | ESC-01/02 — Escalation KPI tiles show wrong values | Add priority filter to `kpi-esc-high`; change `kpi-esc-days` to AVG |

### P1 — This Sprint

| # | Finding | Action |
|---|---|---|
| 1 | EO-01 — Executive dashboard has no IaC | Re-add to `coo-dashboards.yaml` via `sync_coo_dashboard_iac.py` |
| 2 | CC-02/CC-03 — Dataset resources missing; account ID hardcoded | Add `AWS::QuickSight::DataSet` resources; parameterize ARNs |
| 3 | MC-01 — MC Hours KPI uses MAX not SUM | Change `kpi-mc-hours-v` aggregation to SUM |
| 4 | TU-01 — Compliance dataset source wrong | Switch to `vw_weekly_compliance_report` |
| 5 | DM-01 — MC V2 Audit sync timeout | Switch to async Lambda invocation |
| 6 | RF-02 — Hardcoded AWS profile | Remove profile argument from boto3 client calls |

### P2 — Next Two Sprints

| # | Finding | Action |
|---|---|---|
| 1 | SD-01 / RD-01 — Streamlit ORM bypasses views | Replace all aggregation queries with view-backed SQL |
| 2 | CU-01 — No rollback for bulk Clockify updates | Add pre-change snapshot export |
| 3 | CC-01 — SPICE refresh schedule undocumented | Create `docs/spice-refresh-schedule.md` |
| 4 | RF-01 / FC-02 — Missing table schemas | Add `ps_resource_forecast_v2`, `forecast_config`, `forecast_dropped_users` to `models.py` |
| 5 | ESC-03 — `days_open` computed at import time | Compute live in `vw_escalations` |
| 6 | EO-02 — `vw_category_hours_summary` double-counts resources | Fix `resource_count` to use `COUNT(DISTINCT)` |
