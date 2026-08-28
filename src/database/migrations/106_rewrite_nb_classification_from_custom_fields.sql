-- Migration 106: Rewrite NB classification to use Clockify custom fields
--
-- BEFORE: Complex heuristic based on project_type + ps_project_mapping fallback
-- AFTER:  Direct from time entry custom fields: is_nb_productive / is_nb_non_productive
--
-- Affected views:
--   1. vw_productive_utilization (main utilization view)
--   2. vw_practice_kpi_weekly (practice scorecard)
--   3. vw_kpi_staff_weekly (staff detail)
--
-- The new logic is simple:
--   NB Productive hours   = SUM(duration_hours) WHERE is_nb_productive = TRUE
--   NB Non-Productive hrs = SUM(duration_hours) WHERE is_nb_non_productive = TRUE

-- ============================================================
-- 1. vw_productive_utilization
-- ============================================================
CREATE OR REPLACE VIEW vw_productive_utilization AS
WITH
active_users AS (
    SELECT
        u.clockify_user_id,
        u.name                                                                                                          AS employee_name,
        COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.pod_assignment,     '{',''),'}',''),'"',''),'''','')), ''), 'Not Assigned') AS pod_assignment,
        COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.practice_alignment, '{',''),'}',''),'"',''),'''','')), ''), 'Not Assigned') AS practice_alignment,
        u.cloudelligent_title,
        u.location,
        u.employment_designation,
        u.daily_capacity,
        u.daily_capacity * 5                                                                                           AS weekly_available_hours,
        u.created_at::DATE                                                                                             AS user_created_date
    FROM clockify_users u
    WHERE u.status = 'active'
      AND u.daily_capacity > 0
      AND COALESCE(u.time_submission, '') != 'No'
      AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
      AND NOT COALESCE(u.reporting_excluded, FALSE)
),
week_spine AS (
    SELECT DISTINCT week_start
    FROM clockify_detailed_time_entries
    WHERE week_start IS NOT NULL
      AND week_start < DATE_TRUNC('week', CURRENT_DATE)::DATE
),
user_weeks AS (
    SELECT u.*, w.week_start
    FROM active_users u
    CROSS JOIN week_spine w
    WHERE u.user_created_date <= w.week_start + 6
),
time_classified AS (
    SELECT
        te.clockify_user_id,
        te.week_start,
        SUM(CASE WHEN te.billable = TRUE THEN te.duration_hours ELSE 0 END)            AS billable_hours,
        SUM(CASE WHEN te.is_nb_productive = TRUE THEN te.duration_hours ELSE 0 END)    AS nb_productive_hours,
        SUM(CASE WHEN te.is_nb_non_productive = TRUE THEN te.duration_hours ELSE 0 END) AS nb_non_productive_hours,
        SUM(te.duration_hours)                                                          AS total_logged_hours
    FROM clockify_detailed_time_entries te
    WHERE te.week_start IS NOT NULL
    GROUP BY te.clockify_user_id, te.week_start
)
SELECT
    uw.employee_name,
    uw.pod_assignment,
    uw.cloudelligent_title,
    uw.practice_alignment,
    uw.location,
    uw.employment_designation,
    uw.week_start,
    uw.weekly_available_hours                                                                    AS available_hours,
    COALESCE(t.billable_hours,          0)                                                      AS billable_hours,
    COALESCE(t.nb_productive_hours,     0)                                                      AS nb_productive_hours,
    COALESCE(t.nb_non_productive_hours, 0)                                                      AS nb_non_productive_hours,
    GREATEST(uw.weekly_available_hours - COALESCE(t.total_logged_hours, 0), 0)                  AS non_logged_hours,
    COALESCE(t.total_logged_hours,      0)                                                      AS total_logged_hours
FROM user_weeks uw
LEFT JOIN time_classified t
       ON t.clockify_user_id = uw.clockify_user_id
      AND t.week_start       = uw.week_start;


-- ============================================================
-- 2. vw_practice_kpi_weekly
-- ============================================================
DROP VIEW IF EXISTS vw_practice_kpi_weekly;
CREATE OR REPLACE VIEW vw_practice_kpi_weekly AS
WITH
active_users AS (
    SELECT
        u.clockify_user_id,
        u.name,
        u.daily_capacity,
        u.daily_capacity * 5 AS weekly_capacity,
        cleaned.practice_alignment,
        COALESCE(m.line_of_business, 'Internal') AS line_of_business
    FROM clockify_users u
    CROSS JOIN LATERAL (
        SELECT TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
            COALESCE(u.practice_alignment, ''),
            '{',''),'}',''),'"',''),chr(39),'')) AS practice_alignment
    ) cleaned
    LEFT JOIN lob_practice_mapping m
        ON m.practice_alignment = cleaned.practice_alignment
    WHERE u.status = 'active'
      AND u.daily_capacity > 0
      AND NOT COALESCE(u.reporting_excluded, FALSE)
      AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
      AND cleaned.practice_alignment != ''
),
weekly_hours AS (
    SELECT
        te.clockify_user_id,
        DATE_TRUNC('week', te.entry_date)::DATE                                    AS week_start,
        SUM(te.duration_hours)                                                     AS hours_logged,
        SUM(CASE WHEN te.billable THEN te.duration_hours ELSE 0 END)               AS billable_hours,
        SUM(CASE WHEN te.is_nb_productive = TRUE THEN te.duration_hours ELSE 0 END)  AS productive_nb_hours,
        SUM(CASE WHEN te.is_nb_non_productive = TRUE THEN te.duration_hours ELSE 0 END) AS nb_non_productive_hours
    FROM clockify_detailed_time_entries te
    WHERE te.entry_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '52 weeks'
    GROUP BY te.clockify_user_id, DATE_TRUNC('week', te.entry_date)::DATE
)
SELECT
    u.line_of_business,
    u.practice_alignment,
    w.week_start,
    EXTRACT(YEAR FROM w.week_start)::INTEGER AS year_num,
    EXTRACT(QUARTER FROM w.week_start)::INTEGER AS quarter_num,
    CONCAT('Q', EXTRACT(QUARTER FROM w.week_start)::INTEGER, ' ', EXTRACT(YEAR FROM w.week_start)::INTEGER) AS quarter_label,
    COUNT(DISTINCT u.clockify_user_id) AS headcount,
    SUM(u.weekly_capacity) AS total_capacity_hours,
    COALESCE(SUM(h.hours_logged), 0) AS total_hours_logged,
    COALESCE(SUM(h.billable_hours), 0) AS total_billable_hours,
    ROUND(
        (COALESCE(SUM(h.billable_hours), 0) / NULLIF(SUM(u.weekly_capacity), 0) * 100)::NUMERIC, 1
    ) AS billable_util_pct,
    ROUND((
        (COALESCE(SUM(h.billable_hours), 0) + COALESCE(SUM(h.productive_nb_hours), 0))
        / NULLIF(SUM(u.weekly_capacity), 0) * 100
    )::NUMERIC, 1) AS productive_util_pct,
    COALESCE(SUM(h.productive_nb_hours), 0) AS total_productive_nb_hours,
    COALESCE(SUM(h.nb_non_productive_hours), 0) AS total_nb_non_productive_hours,
    ROUND(
        (COALESCE(SUM(h.hours_logged), 0) / NULLIF(SUM(u.weekly_capacity), 0) * 100)::NUMERIC, 1
    ) AS total_util_pct,
    COUNT(DISTINCT CASE WHEN h.hours_logged >= u.weekly_capacity * 0.9 THEN u.clockify_user_id END) AS compliant_count,
    ROUND(
        (COUNT(DISTINCT CASE WHEN h.hours_logged >= u.weekly_capacity * 0.9 THEN u.clockify_user_id END)::NUMERIC /
         NULLIF(COUNT(DISTINCT u.clockify_user_id), 0) * 100), 1
    ) AS compliance_pct
FROM active_users u
CROSS JOIN (
    SELECT DISTINCT DATE_TRUNC('week', entry_date)::DATE AS week_start
    FROM clockify_detailed_time_entries
    WHERE entry_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '52 weeks'
) w
LEFT JOIN weekly_hours h
    ON u.clockify_user_id = h.clockify_user_id
    AND h.week_start = w.week_start
GROUP BY
    u.line_of_business,
    u.practice_alignment,
    w.week_start
ORDER BY
    w.week_start DESC,
    u.line_of_business,
    u.practice_alignment;


-- ============================================================
-- 3. vw_kpi_staff_weekly
-- ============================================================
DROP VIEW IF EXISTS vw_kpi_staff_weekly;
CREATE OR REPLACE VIEW vw_kpi_staff_weekly AS
WITH
active_users AS (
    SELECT
        u.clockify_user_id,
        u.name AS user_name,
        u.daily_capacity,
        u.daily_capacity * 5 AS weekly_capacity,
        COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.pod_assignment,     '{',''),'}',''),'"',''),chr(39),'')), ''), 'Not Assigned') AS pod_assignment,
        COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.practice_alignment, '{',''),'}',''),'"',''),chr(39),'')), ''), 'Not Assigned') AS practice_alignment,
        u.cloudelligent_title,
        u.location,
        u.employment_designation,
        COALESCE(m.line_of_business, 'Internal') AS line_of_business,
        u.created_at::DATE AS user_created_date
    FROM clockify_users u
    CROSS JOIN LATERAL (
        SELECT TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
            COALESCE(u.practice_alignment, ''),
            '{',''),'}',''),'"',''),chr(39),'')) AS pa_cleaned
    ) cleaned
    LEFT JOIN lob_practice_mapping m
        ON m.practice_alignment = cleaned.pa_cleaned
    WHERE u.status = 'active'
      AND u.daily_capacity > 0
      AND NOT COALESCE(u.reporting_excluded, FALSE)
      AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
      AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
),
week_spine AS (
    SELECT DISTINCT DATE_TRUNC('week', entry_date)::DATE AS week_start
    FROM clockify_detailed_time_entries
    WHERE entry_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '52 weeks'
      AND DATE_TRUNC('week', entry_date)::DATE < DATE_TRUNC('week', CURRENT_DATE)::DATE
),
user_weekly_hours AS (
    SELECT
        te.clockify_user_id,
        DATE_TRUNC('week', te.entry_date)::DATE AS week_start,
        SUM(te.duration_hours) AS hours_logged,
        SUM(CASE WHEN te.billable THEN te.duration_hours ELSE 0 END) AS billable_hours,
        SUM(CASE WHEN te.is_nb_productive = TRUE THEN te.duration_hours ELSE 0 END) AS nb_productive_hours,
        SUM(CASE WHEN te.is_nb_non_productive = TRUE THEN te.duration_hours ELSE 0 END) AS nb_non_productive_hours
    FROM clockify_detailed_time_entries te
    WHERE te.entry_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '52 weeks'
    GROUP BY te.clockify_user_id, DATE_TRUNC('week', te.entry_date)::DATE
)
SELECT
    u.user_name,
    u.pod_assignment,
    u.practice_alignment,
    u.line_of_business,
    u.cloudelligent_title,
    u.location,
    u.employment_designation,
    w.week_start,
    EXTRACT(YEAR FROM w.week_start)::INTEGER AS year_num,
    EXTRACT(QUARTER FROM w.week_start)::INTEGER AS quarter_num,
    CONCAT('Q', EXTRACT(QUARTER FROM w.week_start)::INTEGER, ' ', EXTRACT(YEAR FROM w.week_start)::INTEGER) AS quarter_label,
    u.weekly_capacity AS available_hours,
    COALESCE(h.hours_logged, 0) AS hours_logged,
    COALESCE(h.billable_hours, 0) AS billable_hours,
    COALESCE(h.nb_productive_hours, 0) AS nb_productive_hours,
    COALESCE(h.nb_non_productive_hours, 0) AS nb_non_productive_hours,
    GREATEST(u.weekly_capacity - COALESCE(h.hours_logged, 0), 0) AS non_logged_hours,
    ROUND((COALESCE(h.billable_hours, 0) / NULLIF(u.weekly_capacity, 0) * 100)::NUMERIC, 1) AS billable_util_pct,
    ROUND(((COALESCE(h.billable_hours, 0) + COALESCE(h.nb_productive_hours, 0)) / NULLIF(u.weekly_capacity, 0) * 100)::NUMERIC, 1) AS productive_util_pct,
    CASE WHEN COALESCE(h.hours_logged, 0) >= u.weekly_capacity * 0.9 THEN 'Compliant' ELSE 'Non-Compliant' END AS compliance_status,
    CASE WHEN COALESCE(h.hours_logged, 0) >= u.weekly_capacity * 0.9 THEN 1 ELSE 0 END AS is_compliant,
    NULL::NUMERIC AS ontime_pct_in_week,
    NULL::INTEGER AS projects_on_time_in_week,
    NULL::TEXT AS ontime_data_quality,
    NULL::INTEGER AS projects_closed_in_week
FROM active_users u
CROSS JOIN week_spine w
LEFT JOIN user_weekly_hours h
    ON u.clockify_user_id = h.clockify_user_id
    AND h.week_start = w.week_start
WHERE u.user_created_date <= w.week_start + 6
ORDER BY w.week_start DESC, u.user_name;
