# Missing Time Report — How It Works

## How Missing Time Is Determined

- **Condition:** `COALESCE(SUM(duration_hours), 0) = 0` for the prior complete Monday–Sunday week
- **Based on:** Entered time only (time entries exist in Clockify DB). No submission or approval concept — the system has no `approval_status`, `submitted_at`, or `approved_at` fields.
- **View:** `vw_missing_time_submissions` in `src/database/create_views.sql` — fully dynamic, uses `DATE_TRUNC('week', CURRENT_DATE)` at query time against live `clockify_detailed_time_entries` table.

## Exclusions (users NOT checked)

- `status = 'inactive'`
- `daily_capacity = 0`
- Pod assignment containing "exempt" (case-insensitive)
- Clockify custom field `Time Submission = 'NO'`
- Users created after the end of the evaluated week
- Contractors are NOT excluded — same check as FTEs

## Monday Import Schedule (production-clockify-import)

| Time (CT) | EventBridge Rule | What it does |
|---|---|---|
| 9 AM | `production-weekly-import-9am-ct` | Full weekly Clockify pull (weeks_back=2) + SPICE refresh |
| 12 PM | `production-weekly-import-noon-ct` | Incremental import + KPI snapshot + SPICE refresh (14 datasets incl. missing time) |
| 5 AM daily | `production-jira-daily-refresh` | Jira only — does NOT pull Clockify time entries |

## When Users Appear/Disappear from the Report

- **Deadline to avoid appearing at all:** Enter time before Monday 9 AM CT
- **Grace window:** Enter time between 9 AM–12 PM CT Monday → disappears from report after noon run
- **After noon Monday:** Stays on report until following Monday 9 AM regardless of when time is entered
- **Lag:** Two-step — (1) Lambda import pulls from Clockify into RDS, (2) SPICE refresh updates QuickSight. Both happen in the same Lambda invocation so no additional SPICE lag.

## Common User Confusion

- Users conflating Clockify "submit for approval" button with entering time — system only sees whether entries exist, not approval state
- Time entered in the current week doesn't count toward the prior week check
- Report reflects DB state at last import — not live Clockify data
