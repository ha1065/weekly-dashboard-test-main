-- Migration 076: Rebuild vw_time_compliance_history with reporting_excluded filter
-- Supersedes migration 068 view definition (which failed to apply the filter because
-- reporting_excluded column did not exist at migration 068 run time).
-- Must run after migration 074 (reporting_excluded column).

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
    SELECT clockify_user_id, name AS user_name, practice_alignment, status
    FROM clockify_users
    WHERE status = 'active'
      AND NOT COALESCE(reporting_excluded, FALSE)
),
spine AS (
    SELECT u.clockify_user_id, u.user_name, u.practice_alignment, w.week_start
    FROM active_users u
    CROSS JOIN weeks w
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
