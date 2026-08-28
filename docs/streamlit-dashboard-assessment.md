# Streamlit Dashboard Assessment
> Assessed: 2026-05-15 | Reviewer: Senior Product Analyst

---

## Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v1.0 | 2026-05-15 | Product Analyst | Initial assessment — all tabs reviewed |

---

## Context

The Streamlit dashboard is the **operational control layer** of the weekly reporting system. It sits below the COO QuickSight dashboards in the three-tier reporting model:

| Tier | Tool | Audience |
|------|------|----------|
| Executive pulse | QuickSight Executive Summary | CEO/COO |
| Operational review | QuickSight COO Operational | Leadership team |
| **Operational control** | **Streamlit** | COO governance, ops team |

The Streamlit app should do what QuickSight cannot: data entry, data management, configuration, and granular drill-down that requires interactivity beyond QuickSight's capabilities. It should not duplicate QuickSight's read-only reporting.

---

## Tab-by-Tab Assessment

---

### 1. Dashboard

**Goal:** Provide a weekly summary of hours by practice alignment, POD, location, and contractor split. Intended as a quick operational pulse.

**Visuals:**
- 2 metric tiles: Professional Services hours/resources, Managed Cloud hours/resources
- 5 metric tiles: POD breakdown (Alpha, Bravo, A2Z, Charlie, Total)
- 3 metric tiles: Location breakdown (Onshore, Offshore, Offshore %)
- 3 metric tiles: Contractor summary (hours, %, total)
- Filterable time entries table (Date, Resource, Title, POD, Project, Client, Hours, Practice, Skill Area, Location, Billable)

**Data quality issues:**
1. **Queries raw ORM instead of views.** All aggregations run directly against `ClockifyTimeEntry` ORM model. The views in `create_views.sql` (`vw_weekly_time_summary`, `vw_pod_performance_analysis`, `vw_resource_utilization`) exist precisely for this purpose and are not used here. This means the dashboard can show dirty data that the views clean.
2. **POD name cleaning done in Python.** The `clean_pod_name()` function strips `{`, `}`, `"` from PostgreSQL array notation. This is already handled in every view via `TRIM(REPLACE(...))`. Doing it in Python means any new POD name format variation will silently produce wrong aggregations.
3. **MC resource count calculated twice.** The code first approximates `mc_total_resources` from `pod_data` (which is wrong — it uses the `resource_count` column from the aggregated tuple, not a distinct count), then immediately overwrites it with `mc_resource_query` (a correct `COUNT(DISTINCT)` query). The first calculation is dead code that adds confusion.
4. **Practice Alignment filter hardcodes options.** The multiselect for Practice Alignment hardcodes `["Professional Services", "Managed Cloud", "IT Service Delivery", "Service Desk"]`. If a new practice is added to Clockify, it will not appear in the filter and entries will be silently excluded.
5. **Skill Area filter returns tuples.** The `filter_skill_area` multiselect queries `db.query(ClockifyTimeEntry.skill_area).distinct().all()` which returns a list of 1-tuples. The `format_func` handles this but the filter comparison `ClockifyTimeEntry.skill_area.in_(skill_areas)` requires an extra extraction step — fragile.
6. **Week range logic is inconsistent.** "Last 4 Weeks" sets `start_date = current_monday - 4 weeks` but `end_date = current_sunday` (current week). This means it includes the current (incomplete) week. "Last Week" correctly uses the prior Monday–Sunday. The two modes are not consistent in their treatment of the current week.
7. **No charts.** The tab shows only metric tiles and a raw data table. There are no trend lines, bar charts, or distributions. The metric tiles show a single point in time with no context.

**Usefulness:** Partially useful. The time entries table with filters is genuinely useful for ad-hoc drill-down. The metric tiles duplicate what QuickSight's Weekly Pulse sheet shows, but with less context (no trend, no WoW comparison, no reference lines).

**Recommendations:**
1. **Remove the metric tiles section entirely.** The Practice Alignment summary, POD breakdown, Location breakdown, and Contractor summary are all covered by QuickSight with better trend context. Keeping them here creates a second source of truth with different aggregation logic.
2. **Keep the time entries table** — this is the one thing Streamlit does better than QuickSight for this use case (ad-hoc filtering of raw entries). Promote it to the top of the page.
3. **Fix the Practice Alignment filter** to query distinct values from the database rather than hardcoding.
4. **Replace raw ORM queries with view queries** for any aggregations that remain. Use `vw_weekly_time_summary` for practice/location summaries.
5. **Long-term: retire this tab** in favor of QuickSight (per S4-05 in the implementation plan). The time entries table could be preserved as a lightweight "Entry Search" utility tab.

---

### 2. Resource Directory

**Goal:** Provide a searchable roster of all Clockify users with their attributes (practice, POD, location, capacity, employment type) and recent activity hours.

**Visuals:**
- Filterable table: Name, Email, Title, Practice, Skill Area, POD, Location, Capacity, Employment, Status, Last Entry, Hours (Period)
- 4 summary metrics: Total Resources, Active (7 days), Total Hours, Avg Hours
- Excel download button

**Data quality issues:**
1. **Queries raw ORM (`ClockifyUser`) instead of `vw_active_resources`.** The view `vw_active_resources` in `create_views.sql` already joins users to their last entry date and 30-day hours, with cleaned field values. The page reimplements this join in Python using a SQLAlchemy subquery.
2. **"Active (7 days)" metric is misleading.** It counts users whose `last_entry_date >= now - 7 days`. This is not the same as "active this week" — it depends on when the page is loaded during the week. A user who submitted time on Monday will show as active on Tuesday but not the following Monday. The metric label does not communicate this ambiguity.
3. **Hours (Period) calculation uses a CASE inside a subquery.** The subquery computes `hours_in_period` using a CASE expression that filters by `rd_start_date`/`rd_end_date`. This is correct but runs a full table scan on every page load. `vw_active_resources` only covers 30 days; a parameterized query against the view would be cleaner.
4. **POD filter queries `ClockifyUser.pod_assignment` directly** — returns raw values with potential `{Bravo}` formatting. Users may see malformed POD names in the filter dropdown.
5. **No indication of data freshness.** The table shows "Last Entry" dates but there is no "data as of" timestamp. If the Clockify import ran 3 days ago, the directory is stale with no warning.

**Usefulness:** Useful as-is. The Resource Directory is a legitimate operational tool — it answers "who is on what POD, what is their capacity, when did they last log time?" in a way that QuickSight's resource utilization sheet does not. The Excel download is genuinely useful for ops.

**Recommendations:**
1. **Replace the ORM subquery with `vw_active_resources`** for the base user data. Add a separate parameterized query for period hours.
2. **Fix the POD filter** to apply the same `TRIM(REPLACE(...))` cleaning used in the views, or query from `vw_active_resources` which already cleans the field.
3. **Add a data freshness indicator** — show the last Clockify import timestamp (from `import_logs`) at the top of the page.
4. **Rename "Active (7 days)"** to "Logged Time (Last 7 Days)" to be accurate about what it measures.
5. **Keep this tab.** It is not redundant with QuickSight — it provides a filterable, downloadable roster that the QuickSight resource sheets do not replicate at this level of detail.

---

### 3. Resource Forecast

**Goal:** Allow adjustment of the algorithmic resource forecast — tune weights, extend project timelines, and re-run the forecast engine.

**Visuals:**
- Forecast Settings tab: sliders for algorithm weights (historical hours weight, Jira velocity weight, lookback weeks, decay start, capacity cap)
- Project Extensions tab: table of active forecasted projects + form to extend a project by N weeks
- Run Forecast tab: current config metrics, last run timestamp, run button, forecast preview table

**Data quality issues:**
1. **Depends on `ps_resource_forecast_v2` table** which is not defined in `models.py` or `create_views.sql`. This table is referenced in the page but has no visible schema definition in the reviewed files. If this table does not exist, the entire page fails silently (the `if not projects: st.info(...)` path hides the error).
2. **Depends on `forecast_config` table** which is also not in `models.py`. The page reads and writes to this table but it has no defined schema. The `ON CONFLICT (key)` clause in the extension save assumes a unique constraint on `key` — if the table was created without this constraint, saves will duplicate rows.
3. **QuickSight refresh hardcodes a specific AWS profile** (`AWSAdministratorAccess-961341524729`). This will fail in ECS/Lambda where profiles are not available — only IAM roles are. This is a deployment blocker.
4. **Weight validation is advisory only.** The warning "Weights sum to X — recommend summing to 1.0" does not prevent saving invalid weights. The forecast algorithm will silently produce wrong results if weights do not sum to 1.0.
5. **Project extension key truncation.** The extension key is `f'extend_{client}_{project}'[:100]`. If two different projects produce the same 100-character prefix, one will overwrite the other silently.

**Usefulness:** Partially useful, but the underlying algorithm (`ps_resource_forecast_v2`) appears to be a separate system from the main `ps_resource_forecasts` table used everywhere else. The relationship between the two is unclear. If `ps_resource_forecast_v2` is not populated, this entire page is non-functional.

**Recommendations:**
1. **Clarify the relationship between `ps_resource_forecast_v2` and `ps_resource_forecasts`.** If `ps_resource_forecast_v2` is the algorithmic forecast and `ps_resource_forecasts` is the manually-entered forecast, document this distinction and make it visible in the UI.
2. **Add `forecast_config` and `ps_resource_forecast_v2` to `models.py`** so their schemas are version-controlled.
3. **Fix the AWS profile reference** — use the default credential chain (no profile argument) so it works in both local and ECS environments.
4. **Add weight validation enforcement** — prevent saving if weights do not sum to 1.0 ± 0.01.
5. **Add a visible error state** when `ps_resource_forecast_v2` is empty or missing, rather than showing "No active forecasts."

---

### 4. Forecasting

**Goal:** Enter, upload, view, and track resource forecasts for PS projects. The primary data entry interface for the weekly forecast spreadsheet workflow.

**Sub-tabs:** Upload Excel, Manual Entry, View Forecasts, Forecast History

**Visuals:**
- Upload Excel: file uploader, preview table, summary metrics (entries, users, clients, hours), import button
- Manual Entry: client/project/staff selectors, editable grid (staff × week), total hours summary, save button
- View Forecasts: pivot table (client/project/PM/resource × week) or list view, weekly totals metrics, download button
- Forecast History: Current vs Previous comparison table, Browse Snapshot table, Dropped Users table

**Data quality issues:**
1. **Template download uses `chr(73 + i)` for column letters** — this breaks for more than 17 weeks (column Z is index 17; beyond that it produces wrong characters). The template supports 12 weeks so this is currently safe, but fragile.
2. **View Forecasts pivot uses `Date Range` string as column key** (e.g., "27-03 Apr"). If two weeks in different years produce the same date range string (e.g., "27-02 Jan" in 2026 and 2027), the pivot will merge them. This is unlikely but possible for long-running forecasts.
3. **Manual Entry does not validate that `week_end_date` is 6 days after `week_start_date`.** The `weeks` list sets `week_end = week_start + timedelta(days=6)` (Sunday), but `PSResourceForecast.week_end_date` is stored as entered. If the template parser uses a different convention, the two sources will have inconsistent week boundaries.
4. **Forecast History "Current vs Previous" comparison** uses `vw_forecast_version_comparison` which does a `FULL OUTER JOIN` on `(week_start_date, user_name, client_name, project_name)`. If client or project names differ by case or whitespace between the current forecast and the snapshot, rows will not match and will appear as "New" + "Removed" instead of "Changed". The view uses `LOWER()` for the join but the display shows the raw values — this can confuse users.
5. **Dropped Users tab queries `forecast_dropped_users` table** which is not in `models.py`. If this table does not exist, the tab silently shows "No dropped users on record" — which is the same message shown when the table exists but is empty. Users cannot distinguish between "no drops" and "table missing."
6. **QuickSight refresh after import hardcodes 7 dataset IDs** including UUIDs and logical names mixed together. If any dataset is renamed or deleted, the refresh silently fails (the Lambda returns 200 but the dataset is not refreshed).

**Usefulness:** High. This is the core operational workflow — the forecast spreadsheet import, manual entry grid, and version comparison are all genuinely useful and not replicated in QuickSight. The Forecast History tab is particularly valuable for tracking what changed between uploads.

**Recommendations:**
1. **This tab should be kept and maintained as the primary forecast data entry interface.**
2. **Fix the column letter generation** in the template download to use `openpyxl`'s `get_column_letter()` utility instead of manual `chr()` arithmetic.
3. **Add case-insensitive display normalization** in the Current vs Previous comparison — show a note when rows are matched case-insensitively so users understand why "New" + "Removed" pairs appear for the same person.
4. **Add `forecast_dropped_users` to `models.py`** and add an explicit check for table existence rather than relying on exception handling.
5. **Replace hardcoded QuickSight dataset IDs** with a centralized constant or config — the same list appears in both the Forecasting tab and the Data Management tab, creating a maintenance risk.

---

### 5. Data Management

**Goal:** Operational control panel for data refresh — trigger Clockify imports, refresh QuickSight SPICE datasets, manage database views, configure AI analysis prompts, and run AI analyses.

**Sub-sections:** Refresh Controls, Data Sources, AI Project Health Analysis, Run Analysis, Run Forecast Analysis

**Visuals:**
- 3 refresh buttons: Refresh Database Views, Refresh QuickSight Datasets, Refresh All
- QuickSight refresh: progress bar + live status table (dataset name, status, row count)
- Data Sources: table of source tables with record counts and last-updated timestamps
- AI Analysis: tabbed prompt editors (PS, MC, MC V2, Forecast, + dynamic extras)
- Run Analysis: week selector + "Run AI Analysis Now" and "Run MC V2 Audit" buttons
- Run Forecast Analysis: period selector + "Run Forecast Analysis" button

**Data quality issues:**
1. **QuickSight dataset list mixes CloudFormation-managed IDs (logical names like `clockify-time-entries-prod`) with manually-created UUIDs.** If a CloudFormation-managed dataset is redeployed with a new physical ID, the logical name will no longer resolve and the refresh will fail silently. The two naming conventions should be separated and documented.
2. **Data Sources table shows `last_updated` only for tables with a matching `import_category` in `import_logs`.** Tables like `ps_project_mapping`, `mc_v2_audit_by_customer`, and `app_users` will always show blank `Last Updated` because they are not populated via the import pipeline. This makes the table misleading — blank does not mean "never updated."
3. **AI prompt editors use `db.query(AIAnalysisPrompt).filter(...).delete()` then re-insert.** This is a destructive replace — if the save fails mid-transaction, the prompt is deleted but not replaced. The `db.rollback()` in the except block should recover this, but the pattern is fragile. An upsert would be safer.
4. **"Run AI Analysis Now" and "Run MC V2 Audit" share the same week selector** (`ai_run_weeks`). The forecast analysis uses a separate period selector. This is inconsistent — a user running the MC V2 Audit may not realize it is using the same week as the PS/MC analysis.
5. **Lambda invocation uses `InvocationType='RequestResponse'`** for all operations including the MC V2 Audit which "may take 2–4 minutes." API Gateway and Lambda have a 29-second timeout for synchronous invocations. If the audit takes longer, the Streamlit call will time out and show an error even if the Lambda completes successfully.

**Usefulness:** High. This is the most important tab in the app — it is the only interface for triggering data refreshes, managing AI prompts, and running analyses. It should be kept and improved.

**Recommendations:**
1. **Separate CloudFormation-managed datasets from manually-created datasets** in the refresh list — use two sections with clear labels so operators know which datasets are IaC-managed.
2. **Fix the Data Sources table** — add a note column explaining why some tables show blank last-updated (not import-pipeline managed), or add a separate freshness source for those tables.
3. **Switch MC V2 Audit invocation to `InvocationType='Event'` (async)** and add a polling mechanism or a "check status" button, rather than waiting synchronously for a 2–4 minute operation.
4. **Add a separate week selector for MC V2 Audit** to avoid confusion with the PS/MC analysis week.
5. **Add a "Last Run" timestamp** for each analysis type (PS/MC, MC V2, Forecast) so operators can see when each was last executed without running it again.

---

### 6. Project Mapping

**Goal:** Map Jira PS/MC projects to their corresponding Clockify clients and projects so that actual hours flow correctly into the PS Project Status view and profitability calculations.

**Sub-tabs:** Professional Services, Managed Services (with Pod management expander)

**Visuals:**
- Sync button: pulls latest Clockify projects from API
- Pre-populate button: auto-creates mappings from Clockify project_type field
- 4 metrics: PS Projects, PS Mapped, MC Projects, MC Mapped
- PS tab: table of Jira projects with Clockify client/project selectors and Save buttons
- MC tab: same as PS but with Pod selector column; Pod management expander (add/remove pods)

**Data quality issues:**
1. **Mapping lookup uses `(client.lower(), project.lower())` as key** but the display shows the original casing. If a Jira project name has inconsistent casing across rows in `ps_project_status`, it may appear multiple times in the mapping table with different cases, and only one will match the lookup key.
2. **`_save_mapping()` deletes all existing mappings for a client/project before inserting new ones.** If the user clicks Save on a row without changing anything, all existing mappings for that row are deleted and re-created. This is functionally correct but creates unnecessary churn in the database and triggers a QuickSight refresh on every Save click.
3. **The QuickSight refresh triggered by `_trigger_project_status_refresh()` uses `InvocationType='Event'` (fire-and-forget).** This is correct for a background refresh, but there is no feedback to the user that the refresh was triggered. The success message only says "Saved: ..." — users may not know the QuickSight data will update.
4. **Pod management "Remove" button deactivates the pod** (`is_active = False`) but does not remove existing mappings that reference the pod. If a pod is deactivated, its mappings remain in `ps_project_mapping` with the old pod name, and the pod will no longer appear in the dropdown for new mappings. This creates orphaned mappings.
5. **The pre-populate function** (`prepopulate_mappings_from_project_type`) is called from `src/integrations/import_jira_data.py` — a module not reviewed here. Its behavior (what it creates, what it skips) is opaque from the UI.

**Usefulness:** High. This is a critical operational tool — without correct mappings, the PS Project Status view shows wrong actual hours and the profitability calculations are incorrect. There is no equivalent in QuickSight.

**Recommendations:**
1. **Add a "mapping coverage" indicator** — show what % of active PS/MC projects have at least one mapping, and highlight unmapped projects in the table (e.g., red row background).
2. **Add a confirmation step before Save** when the user is changing an existing mapping (not just adding one), to prevent accidental overwrites.
3. **Add a note to the UI** explaining that QuickSight data will refresh in the background after saving, so users know to wait before checking the dashboard.
4. **Handle orphaned pod mappings** — when a pod is deactivated, show a warning if any active mappings reference it, and offer to reassign or clear those mappings.
5. **Keep this tab.** It is the only interface for this critical configuration.

---

### 7. Clockify Data Update

**Goal:** Allow bulk updates to Clockify custom fields (practice alignment, skill area, POD, title, location, employment designation) by uploading a CSV/Excel export from Clockify, editing it, and re-uploading.

**Sub-tabs:** Upload & Apply, Export from Clockify, Upload History, Help

**Visuals:**
- Export tab: two columns (Projects, Members) with download buttons and preview tables
- Upload tab: file uploader, auto-detection of file type (members vs projects), preview, dry-run button, apply button with confirmation checkbox
- History tab: summary table of past uploads + detail view for selected upload

**Data quality issues:**
1. **Dry run and Apply use the same `update_members()` / `update_projects()` functions** with a `dry_run` flag. If the Clockify API rate-limits between the dry run and the apply, the apply may fail on records that the dry run showed as valid. There is no indication to the user that the dry run result may be stale.
2. **Upload History stores change detail as JSON in a `Text` column** (`ClockifyUploadLog.detail`). For large uploads (100+ records), this JSON blob can be very large. There is no size limit or truncation. For very large uploads, this could cause database write failures.
3. **File type detection (`detect_file_type()`) is not reviewed here** (in `src/integrations/update_clockify.py`) but the UI shows the detection result without explaining the detection logic. If a file is misdetected, the user has no way to override the detected type.
4. **The "Apply Updates to Clockify" button is disabled until the confirmation checkbox is checked**, but the checkbox label says "I have reviewed the dry run and want to apply changes" — there is no enforcement that the dry run was actually run. A user could check the box and apply without running the dry run.
5. **No rollback capability.** Once changes are applied to Clockify, there is no undo. The upload history shows what was changed but does not provide a way to revert. For bulk updates (e.g., accidentally setting all users to the wrong practice), this is a significant operational risk.

**Usefulness:** High. This is a unique capability — bulk-updating Clockify custom fields via CSV is not possible in the Clockify UI. The dry-run workflow is well-designed.

**Recommendations:**
1. **Add a "Run Dry Run First" enforcement** — disable the Apply button until a dry run has been executed in the current session (track this in `st.session_state`).
2. **Add a rollback export** — before applying changes, export the current values of all fields that will be changed to a downloadable CSV. This gives operators a manual rollback path.
3. **Cap the JSON detail blob** in `ClockifyUploadLog` — store only the first 500 changed records in the detail column, with a note if truncated.
4. **Keep this tab.** It is a critical operational tool with no equivalent elsewhere.

---

### 8. Settings

**Goal:** System configuration — database statistics, user management (app login accounts), default date range settings, custom fields reference, practice alignment distribution, data freshness.

**Visuals:**
- 4 metrics: Total Users, Active Users, Total Projects, Time Entries
- User management: current users table, Add User form, Edit User form, Remove User form
- Date range settings: weeks_back and weeks_forward number inputs
- Custom fields reference table (static)
- Practice alignment distribution table
- Data freshness: last sync timestamp

**Data quality issues:**
1. **"Default Date Range Settings" (weeks_back, weeks_forward) are stored in `st.session_state`** — they reset on every page reload. They are not persisted to the database or used by any other tab. This section has no functional effect on the dashboard.
2. **"Total Projects" metric counts `COUNT(DISTINCT project_name)` from `ClockifyTimeEntry`** — this counts Clockify project names that appear in time entries, not the total number of projects in `clockify_projects`. A project with no time entries will not be counted. The metric label is misleading.
3. **The custom fields reference table is hardcoded** — it lists 6 fields but the actual Clockify custom fields may differ. If a field is added or renamed in Clockify, this table will be wrong.
4. **Practice alignment distribution queries `ClockifyUser` directly** — returns raw values with potential `{Professional Services}` formatting. The display shows cleaned values via `pa or "Unassigned"` but does not apply the `TRIM(REPLACE(...))` cleaning, so malformed values will appear as-is.
5. **Data freshness shows only `synced_at` from `ClockifyTimeEntry`** — this is the last time any time entry was synced, not the last time the import ran. If the import ran but found no new entries, `synced_at` will not update and the freshness indicator will appear stale.

**Usefulness:** Partially useful. User management is essential and works correctly. The database statistics and data freshness are useful for ops. The date range settings and custom fields reference are not useful in their current form.

**Recommendations:**
1. **Remove the "Default Date Range Settings" section** — it has no functional effect and adds confusion.
2. **Fix "Total Projects"** to query `clockify_projects` table directly, not time entries.
3. **Replace the hardcoded custom fields table** with a dynamic query against `clockify_projects` or `clockify_users` to show actual distinct values.
4. **Fix practice alignment distribution** to apply the same `TRIM(REPLACE(...))` cleaning used in the views.
5. **Fix data freshness** to query `import_logs` for the last successful import timestamp (same source used by `vw_data_freshness`), not `ClockifyTimeEntry.synced_at`.
6. **Keep this tab** — user management is a necessary operational function.

---

## Data Quality Findings

### DQ-01: Raw ORM vs Views — Inconsistent Aggregation Logic

**Affected tabs:** Dashboard, Resource Directory, Settings

The Dashboard and Resource Directory tabs query the `ClockifyTimeEntry` and `ClockifyUser` ORM models directly, bypassing the 30+ views in `create_views.sql`. These views apply consistent field cleaning (stripping `{`, `}`, `"` from PostgreSQL array notation), handle NULL values, and apply business logic (e.g., POD classification, practice group bucketing). The Streamlit tabs reimplement subsets of this logic in Python, creating two divergent code paths that can produce different numbers for the same metric.

**Impact:** A user comparing the Dashboard tab to the QuickSight Weekly Pulse sheet may see different hour totals for the same week. This erodes trust in both tools.

**Fix:** Replace all direct ORM queries used for aggregation with `db.execute(text("SELECT ... FROM vw_..."))` calls against the appropriate views.

---

### DQ-02: POD Name Cleaning in Python

**Affected tabs:** Dashboard

The `clean_pod_name()` function in `app.py` strips `{`, `}`, `"` from POD names. This is the same transformation applied in every view via `TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\', ''))`. Having two implementations means:
- If Clockify changes its array notation format, both places must be updated
- The Python version does not handle the backslash escape (`\'`) that the SQL version handles
- The Python aggregation (`pod_aggregated` dict) runs after the query, meaning the database index on `pod_assignment` cannot be used for grouping

**Fix:** Remove `clean_pod_name()` and use `vw_pod_performance_analysis` or a direct SQL query with the standard cleaning expression.

---

### DQ-03: Practice Alignment Filter Hardcoding

**Affected tabs:** Dashboard

The Practice Alignment multiselect hardcodes `["Professional Services", "Managed Cloud", "IT Service Delivery", "Service Desk"]`. The actual values in the database may differ (e.g., `{Professional Services}` with braces, or new practices added after the code was written). This means:
- New practices are silently excluded from filtering
- The filter options may not match what appears in the data table below

**Fix:** Query `SELECT DISTINCT practice_alignment FROM vw_weekly_time_summary` (which already cleans the values) and use the result as filter options.

---

### DQ-04: Incomplete Data Freshness Indicators

**Affected tabs:** Resource Directory, Settings

Neither tab shows when the underlying Clockify data was last imported. The Resource Directory shows "Last Entry" dates per user, but a user who submitted time 3 days ago will show a recent date even if the import has not run since then. The Settings tab shows `ClockifyTimeEntry.synced_at` which is the entry-level sync timestamp, not the import run timestamp.

**Fix:** Add a banner or caption on data-heavy tabs showing the last successful import timestamp from `import_logs WHERE import_category = 'time_entries' AND status = 'success' ORDER BY completed_at DESC LIMIT 1`.

---

### DQ-05: Missing Schema Definitions for Operational Tables

**Affected tabs:** Resource Forecast, Forecasting (Dropped Users)

The following tables are referenced in the app but not defined in `models.py`:
- `ps_resource_forecast_v2` (Resource Forecast page)
- `forecast_config` (Resource Forecast page)
- `forecast_dropped_users` (Forecasting → Forecast History → Dropped Users)

Without ORM definitions, these tables have no version-controlled schema. If they are dropped or their schema changes, the app will fail with opaque errors. The exception handling in the app (`except Exception: ... = []`) hides these failures, showing empty states instead of errors.

**Fix:** Add SQLAlchemy model classes for all three tables in `models.py`. Add explicit table existence checks with user-visible error messages.

---

### DQ-06: Duplicate QuickSight Dataset ID Lists

**Affected tabs:** Forecasting (Upload Excel), Data Management

The list of QuickSight dataset IDs to refresh after a forecast import appears in two places:
1. `app.py` Forecasting tab (7 IDs, hardcoded inline)
2. `app.py` Data Management tab (`ALL_QUICKSIGHT_DATASETS` dict, 24 entries)

The two lists are not identical — the Forecasting tab's 7 IDs are a subset of the Data Management list, but the subset is not derived from the full list. If a dataset is added to the full list, it will not automatically be included in the post-import refresh.

**Fix:** Define a single `FORECAST_QUICKSIGHT_DATASETS` constant at the top of `app.py` and reference it from both locations.

---

## Prioritized Recommendations

### Priority 1 — Fix Before Next Use (Data Accuracy)

| # | Recommendation | Affected Tab | Effort |
|---|---------------|-------------|--------|
| R-01 | Replace raw ORM aggregation queries with view-based queries in Dashboard tab | Dashboard | M |
| R-02 | Fix Practice Alignment filter to query from DB instead of hardcoding | Dashboard | S |
| R-03 | Remove `clean_pod_name()` Python function; use SQL views for POD aggregation | Dashboard | S |
| R-04 | Fix data freshness indicator in Settings to use `import_logs` | Settings | S |
| R-05 | Add `forecast_config`, `ps_resource_forecast_v2`, `forecast_dropped_users` to `models.py` | Resource Forecast, Forecasting | M |

### Priority 2 — Improve Operational Reliability

| # | Recommendation | Affected Tab | Effort |
|---|---------------|-------------|--------|
| R-06 | Add data freshness banner to Resource Directory and Dashboard | Resource Directory, Dashboard | S |
| R-07 | Fix POD filter in Resource Directory to use cleaned values | Resource Directory | S |
| R-08 | Deduplicate QuickSight dataset ID lists into a single constant | Forecasting, Data Management | S |
| R-09 | Fix AWS profile reference in Resource Forecast to use default credential chain | Resource Forecast | S |
| R-10 | Switch MC V2 Audit Lambda invocation to async (`InvocationType='Event'`) | Data Management | S |
| R-11 | Add "Run Dry Run First" enforcement before Apply in Clockify Data Update | Clockify Data Update | S |
| R-12 | Add rollback export (pre-change CSV) to Clockify Data Update | Clockify Data Update | M |

### Priority 3 — Simplification and Alignment with Three-Tier Model

| # | Recommendation | Affected Tab | Effort |
|---|---------------|-------------|--------|
| R-13 | Retire metric tiles from Dashboard tab (covered by QuickSight) | Dashboard | S |
| R-14 | Promote time entries table to top of Dashboard tab; rename tab to "Entry Search" | Dashboard | S |
| R-15 | Remove "Default Date Range Settings" from Settings (non-functional) | Settings | S |
| R-16 | Fix "Total Projects" metric in Settings to query `clockify_projects` | Settings | S |
| R-17 | Add mapping coverage indicator to Project Mapping tab | Project Mapping | M |
| R-18 | Add "Last Run" timestamps for each AI analysis type in Data Management | Data Management | S |

### Priority 4 — Long-Term (Per Implementation Plan S4-05)

| # | Recommendation | Affected Tab | Effort |
|---|---------------|-------------|--------|
| R-19 | Retire Dashboard tab entirely; replace with link to QuickSight Weekly Pulse | Dashboard | S |
| R-20 | Retire Resource Directory tab; replace with link to QuickSight Resource Utilization | Resource Directory | S |

---

## Summary Assessment

| Tab | Usefulness | Primary Issue | Recommended Action |
|-----|-----------|--------------|-------------------|
| Dashboard | Low | Duplicates QuickSight with worse data quality | Retire metric tiles; keep entry search table |
| Resource Directory | Medium | Useful roster tool; queries raw ORM | Fix ORM queries; keep tab |
| Resource Forecast | Low | Depends on undocumented tables; unclear relationship to main forecast | Clarify architecture; fix schema gaps |
| Forecasting | High | Core workflow; minor data quality issues | Keep; fix template column bug and dataset ID duplication |
| Data Management | High | Critical control panel; async invocation issue | Keep; fix MC V2 audit timeout risk |
| Project Mapping | High | Critical configuration; orphaned pod risk | Keep; add coverage indicator |
| Clockify Data Update | High | Unique capability; needs rollback protection | Keep; add dry-run enforcement |
| Settings | Medium | User management essential; other sections weak | Keep user management; remove non-functional sections |

The Streamlit app's highest value is as an **operational control panel** — data entry (forecasts), data management (imports, refreshes), configuration (mappings, prompts), and bulk updates (Clockify fields). The tabs that serve this purpose (Forecasting, Data Management, Project Mapping, Clockify Data Update) are well-designed and should be maintained. The tabs that duplicate QuickSight read-only reporting (Dashboard, Resource Directory) should be simplified or retired per the three-tier reporting model.
