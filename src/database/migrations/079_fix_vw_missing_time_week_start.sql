-- Migration 079: Fix vw_missing_time_submissions week_start matching
--
-- ROOT CAUSE:
--   The Python import computes week_start by converting UTC timestamps → CST,
--   then finding that Monday's date in CST. This means entries stored for the
--   business week Jun 16–22 have week_start = 2026-06-15 (one week earlier in CST).
--   The view's DATE_TRUNC('week', CURRENT_DATE)::date - 7 on Monday 2026-06-22
--   also returns 2026-06-15, so it correctly matches the stored data — the view
--   math was never broken (it returned 10 truly non-compliant users out of 70
--   eligible, with 59 having submitted time for that week).
--
--   The "69 non-compliant" diagnostic figure came from a query hardcoding
--   week_start = '2026-06-16', which has 0 entries in the DB, causing every
--   user to appear non-compliant. That count was spurious.
--
-- ACTUAL FIX:
--   Replace te.week_start comparison with DATE_TRUNC('week', te.entry_date)::DATE
--   so the aggregation anchors to the calendar date of the entry rather than
--   the stored week_start column. This eliminates the 3 known cross-week entries
--   caused by the UTC→CST shift and makes the view robust to future timezone edge cases.

CREATE OR REPLACE VIEW vw_missing_time_submissions AS
WITH last_complete_week AS (
    SELECT (DATE_TRUNC('week', CURRENT_DATE)::DATE - 7)::DATE AS week_start_date
),
user_hours_last_week AS (
    SELECT te.clockify_user_id,
           SUM(te.duration_hours) AS total_hours,
           COUNT(*) AS entry_count
    FROM clockify_detailed_time_entries te
    WHERE DATE_TRUNC('week', te.entry_date)::DATE = (SELECT week_start_date FROM last_complete_week)
    GROUP BY te.clockify_user_id
),
last_clockify_import AS (
    SELECT (completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago')::DATE AS last_updated_date,
           TO_CHAR(completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago', 'HH:MI AM') AS last_updated_time
    FROM import_logs
    WHERE import_category = 'time_entries' AND status = 'success'
    ORDER BY completed_at DESC LIMIT 1
)
SELECT
    u.clockify_user_id, u.name, u.email,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.pod_assignment,     chr(123),''),chr(125),''),chr(34),''),chr(92),'')) AS pod_assignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.practice_alignment, chr(123),''),chr(125),''),chr(34),''),chr(92),'')) AS practice_alignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.skill_area,         chr(123),''),chr(125),''),chr(34),''),chr(92),'')) AS skill_area,
    u.location, u.daily_capacity, u.daily_capacity * 5 AS weekly_expected_hours,
    COALESCE(h.total_hours, 0) AS hours_submitted,
    COALESCE(h.entry_count, 0) AS entries_submitted,
    CASE WHEN COALESCE(h.total_hours, 0) = 0 THEN 'No Time Submitted' ELSE 'Complete' END AS submission_status,
    CASE
        WHEN COALESCE(h.total_hours, 0) = 0  THEN '0 Hours'
        WHEN COALESCE(h.total_hours, 0) < 20 THEN '1-19 Hours'
        WHEN COALESCE(h.total_hours, 0) < 30 THEN '20-29 Hours'
        ELSE '30+ Hours'
    END AS hours_bucket,
    (SELECT week_start_date   FROM last_complete_week)   AS week_start_date,
    (SELECT last_updated_date FROM last_clockify_import) AS last_updated_date,
    (SELECT last_updated_time FROM last_clockify_import) AS last_updated_time
FROM clockify_users u
LEFT JOIN user_hours_last_week h ON u.clockify_user_id = h.clockify_user_id
WHERE u.status = 'active'
  AND u.daily_capacity > 0
  AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
  AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
  AND NOT COALESCE(u.reporting_excluded, FALSE)
  AND u.created_at::DATE <= (SELECT week_start_date FROM last_complete_week) + INTERVAL '6 days'
  AND COALESCE(h.total_hours, 0) = 0
ORDER BY u.pod_assignment, u.name;
