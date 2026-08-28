-- Migration 080: Fix vw_time_compliance_history week_start join (entry_date range)
--
-- ROOT CAUSE:
--   The Python importer sets week_start via UTC→CST conversion. For entries
--   with entry_date 2026-06-16 (Mon CST), the UTC timestamp may fall on
--   2026-06-15 (Sun UTC), so week_start is stored as 2026-06-15 — a Sunday.
--
--   vw_time_compliance_history's weeks CTE uses DISTINCT week_start from the
--   entries table, so the spine correctly contains 2026-06-15.
--   The actuals CTE also groups by week_start, so the join works in PostgreSQL.
--
--   HOWEVER: QuickSight SPICE receives week_start = 2026-06-15 (Sunday).
--   When QuickSight's date engine or a calculated field applies
--   truncDate('WK', week_start), it maps Sunday 2026-06-15 → the week of
--   2026-06-09 (previous Monday under ISO week rules). This causes Urwa's
--   31 hours to appear in the WRONG week in QuickSight visuals, making her
--   appear non-compliant for the week of 2026-06-16.
--
--   vw_missing_time_submissions (fixed in migration 079) already uses
--   DATE_TRUNC('week', entry_date)::DATE to anchor to the calendar date of
--   the entry, which always returns a Monday. This view must do the same.
--
-- FIX:
--   Replace the weeks CTE (DISTINCT week_start) and actuals CTE (GROUP BY
--   week_start) with entry_date-based logic that mirrors migration 079:
--     - weeks spine: DISTINCT DATE_TRUNC('week', entry_date)::DATE
--     - actuals:     GROUP BY DATE_TRUNC('week', entry_date)::DATE
--   This guarantees week_start is always a Monday, so QuickSight date
--   bucketing is correct.
--
-- VIEWS AFFECTED:
--   vw_time_compliance_history — powers the "Compliance History" QuickSight
--   dataset (missing-time-history). This is the visual showing Urwa as
--   non-compliant despite her having 31 hours for Jun 16-19.
--
-- VIEWS NOT AFFECTED (already correct):
--   vw_missing_time_submissions  — fixed in migration 079 (entry_date range)
--   vw_weekly_compliance_report  — uses te.week_start; anchored to prior week
--                                   via DATE_TRUNC subtraction (same value)
--   vw_time_submission_weekly    — uses te.week_start; spine from DISTINCT
--                                   week_start (consistent both sides)

DROP VIEW IF EXISTS vw_time_compliance_history;

CREATE VIEW vw_time_compliance_history AS
WITH
weeks AS (
    -- Anchor to entry_date so week boundaries are always Monday,
    -- regardless of how week_start was stored during import.
    SELECT DISTINCT DATE_TRUNC('week', entry_date)::DATE AS week_start
    FROM clockify_detailed_time_entries
    WHERE entry_date IS NOT NULL
      AND DATE_TRUNC('week', entry_date)::DATE >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')::DATE
),
active_users AS (
    SELECT clockify_user_id, name AS user_name, practice_alignment, status,
           created_at::DATE AS user_created_date
    FROM clockify_users
    WHERE status = 'active'
      AND daily_capacity > 0
      AND (pod_assignment IS NULL OR pod_assignment NOT ILIKE '%exempt%')
      AND (time_submission IS NULL OR UPPER(TRIM(time_submission)) != 'NO')
      AND NOT COALESCE(reporting_excluded, FALSE)
),
spine AS (
    SELECT u.clockify_user_id, u.user_name, u.practice_alignment, w.week_start
    FROM active_users u
    CROSS JOIN weeks w
    WHERE u.user_created_date <= w.week_start + 6
),
actuals AS (
    -- Group by calendar week of entry_date (always Monday) to match the spine.
    SELECT clockify_user_id,
           DATE_TRUNC('week', entry_date)::DATE AS week_start,
           SUM(duration_hours) AS hours_submitted
    FROM clockify_detailed_time_entries
    GROUP BY clockify_user_id, DATE_TRUNC('week', entry_date)::DATE
)
SELECT
    s.week_start,
    TO_CHAR(s.week_start, 'Mon YYYY')                           AS month_label,
    EXTRACT(YEAR FROM s.week_start)::INTEGER                    AS year_num,
    EXTRACT(MONTH FROM s.week_start)::INTEGER                   AS month_num,
    EXTRACT(QUARTER FROM s.week_start)::INTEGER                 AS quarter_num,
    CONCAT('Q', EXTRACT(QUARTER FROM s.week_start)::INTEGER,
           ' ', EXTRACT(YEAR FROM s.week_start)::INTEGER)       AS quarter_label,
    s.clockify_user_id,
    s.user_name,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
        COALESCE(s.practice_alignment, ''),
        '{',''),'}',''),'"',''),chr(39),''))                     AS practice_alignment,
    COALESCE(a.hours_submitted, 0)                              AS hours_submitted,
    CASE WHEN COALESCE(a.hours_submitted, 0) > 0 THEN 1 ELSE 0 END AS is_compliant,
    r.reason                                                    AS missing_time_reason
FROM spine s
LEFT JOIN actuals a
       ON s.clockify_user_id = a.clockify_user_id
      AND s.week_start = a.week_start
LEFT JOIN missing_time_reasons r
       ON s.clockify_user_id = r.clockify_user_id
      AND s.week_start = r.week_start
ORDER BY s.week_start DESC, s.user_name;
