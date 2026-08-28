-- Migration 077: Fix compliance view exclusions
-- Fixes 4 gaps identified in compliance reporting review:
--   1. vw_time_compliance_history missing daily_capacity, exempt pod, time_submission filters
--   2. vw_time_compliance_history missing new-user cutoff
--   3. vw_weekly_compliance_report missing reporting_excluded filter
--   4. vw_time_submission_weekly missing reporting_excluded filter

-- ============================================================
-- Fix 1 & 2: vw_time_compliance_history
-- Add daily_capacity > 0, exempt pod, time_submission != 'NO',
-- and new-user cutoff to active_users CTE
-- ============================================================
DROP VIEW IF EXISTS vw_time_compliance_history;

CREATE VIEW vw_time_compliance_history AS
WITH
weeks AS (
    SELECT DISTINCT week_start
    FROM clockify_detailed_time_entries
    WHERE week_start IS NOT NULL
      AND week_start >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')::DATE
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
    WHERE u.user_created_date <= w.week_start + 6  -- Fix 2: new-user cutoff
),
actuals AS (
    SELECT clockify_user_id,
           week_start,
           SUM(duration_hours) AS hours_submitted
    FROM clockify_detailed_time_entries
    GROUP BY clockify_user_id, week_start
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

-- ============================================================
-- Fix 3: vw_weekly_compliance_report — add reporting_excluded
-- ============================================================
CREATE OR REPLACE VIEW vw_weekly_compliance_report AS
WITH reporting_week AS (
    SELECT (DATE_TRUNC('week', CURRENT_DATE)::DATE - 7)::DATE AS week_start_date
),
last_clockify_import AS (
    SELECT
        (completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago')::DATE AS last_updated_date,
        TO_CHAR(completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago', 'HH:MI AM') AS last_updated_time
    FROM import_logs
    WHERE import_category = 'time_entries'
      AND status = 'success'
    ORDER BY completed_at DESC
    LIMIT 1
),
user_hours AS (
    SELECT
        te.clockify_user_id,
        SUM(te.duration_hours) AS hours_submitted,
        COUNT(*)               AS entry_count
    FROM clockify_detailed_time_entries te
    WHERE te.week_start = (SELECT week_start_date FROM reporting_week)
    GROUP BY te.clockify_user_id
)
SELECT
    u.name                                                                                     AS employee_name,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.pod_assignment,     '{',''),'}',''),'"',''),'\','')) AS pod_assignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.practice_alignment, '{',''),'}',''),'"',''),'\','')) AS practice_alignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.skill_area,         '{',''),'}',''),'"',''),'\','')) AS skill_area,
    u.cloudelligent_title,
    u.location,
    u.employment_designation,
    u.daily_capacity * 5                                                                       AS weekly_expected_hours,
    COALESCE(h.hours_submitted, 0)                                                             AS hours_submitted,
    COALESCE(h.entry_count, 0)                                                                 AS entry_count,
    CASE
        WHEN COALESCE(h.hours_submitted, 0) > 0 THEN 'Complete'
        ELSE                                         'No Time Submitted'
    END                                                                                        AS submission_status,
    CASE
        WHEN COALESCE(h.hours_submitted, 0) > 0 THEN 1
        ELSE 0
    END                                                                                        AS is_compliant,
    (SELECT week_start_date  FROM reporting_week)                                              AS week_start_date,
    (SELECT last_updated_date FROM last_clockify_import)                                       AS last_updated_date,
    (SELECT last_updated_time FROM last_clockify_import)                                       AS last_updated_time
FROM clockify_users u
LEFT JOIN user_hours h ON u.clockify_user_id = h.clockify_user_id
WHERE u.status = 'active'
  AND u.daily_capacity > 0
  AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
  AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
  AND NOT COALESCE(u.reporting_excluded, FALSE)
  AND u.created_at::DATE <= (SELECT week_start_date FROM reporting_week) + INTERVAL '6 days'
ORDER BY is_compliant, pod_assignment, employee_name;

-- ============================================================
-- Fix 4: vw_time_submission_weekly — add reporting_excluded
-- ============================================================
CREATE OR REPLACE VIEW vw_time_submission_weekly AS
WITH week_spine AS (
    SELECT DISTINCT week_start
    FROM clockify_detailed_time_entries
    WHERE week_start IS NOT NULL
      AND week_start < DATE_TRUNC('week', CURRENT_DATE)::DATE
),
active_users AS (
    SELECT
        u.clockify_user_id,
        u.name,
        TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.pod_assignment,     '{',''),'}',''),'"',''),'\','')) AS pod_assignment,
        TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.practice_alignment, '{',''),'}',''),'"',''),'\','')) AS practice_alignment,
        u.cloudelligent_title,
        u.location,
        u.employment_designation,
        u.daily_capacity,
        u.daily_capacity * 5 AS weekly_expected_hours,
        u.created_at::DATE   AS user_created_date
    FROM clockify_users u
    WHERE u.status = 'active'
      AND u.daily_capacity > 0
      AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
      AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
      AND NOT COALESCE(u.reporting_excluded, FALSE)
),
user_weeks AS (
    SELECT u.*, w.week_start
    FROM active_users u
    CROSS JOIN week_spine w
    WHERE u.user_created_date <= w.week_start + 6
),
user_hours AS (
    SELECT
        te.clockify_user_id,
        te.week_start,
        SUM(te.duration_hours) AS hours_submitted,
        COUNT(*)               AS entry_count
    FROM clockify_detailed_time_entries te
    WHERE te.week_start IS NOT NULL
    GROUP BY te.clockify_user_id, te.week_start
)
SELECT
    uw.name                                                                               AS employee_name,
    uw.pod_assignment,
    uw.cloudelligent_title,
    uw.practice_alignment,
    uw.location,
    uw.employment_designation,
    uw.week_start,
    uw.weekly_expected_hours,
    COALESCE(h.hours_submitted, 0)                                                        AS hours_submitted,
    COALESCE(h.entry_count, 0)                                                            AS entry_count,
    CASE
        WHEN COALESCE(h.hours_submitted, 0) >= uw.weekly_expected_hours * 0.9            THEN 'Complete'
        WHEN COALESCE(h.hours_submitted, 0) >= uw.weekly_expected_hours * 0.5            THEN 'Less Than 90%'
        WHEN COALESCE(h.hours_submitted, 0) >  0                                         THEN 'Less Than 50%'
        ELSE                                                                                   'No Time Submitted'
    END                                                                                   AS submission_status,
    CASE
        WHEN COALESCE(h.hours_submitted, 0) >= uw.weekly_expected_hours * 0.9            THEN 1
        ELSE 0
    END                                                                                   AS is_compliant
FROM user_weeks uw
LEFT JOIN user_hours h
       ON h.clockify_user_id = uw.clockify_user_id
      AND h.week_start       = uw.week_start;
