-- Migration 103: Fix NB Non-Productive classification consistency
-- 
-- Problem: vw_practice_kpi_weekly uses a simpler classification (project_type + is_overtime/is_presales)
-- that MISSES the ps_project_mapping mapped_clients fallback logic present in vw_productive_utilization.
-- Additionally, vw_kpi_staff_weekly does not exist and is needed for the KPI Tracking Dashboard.
--
-- Source of truth: vw_productive_utilization classifies NB Productive as:
--   billable=FALSE AND (
--     project_type IN ('Non Bill Productive','Overtime','Presales')
--     OR (project_type IS NULL AND client is in ps_project_mapping)
--     OR (project_type NOT IN the 4 known types AND client is in ps_project_mapping)
--   )
--
-- This migration:
--   1. Recreates vw_practice_kpi_weekly with mapped_clients fallback
--   2. Creates vw_kpi_staff_weekly (per-staff weekly KPI view for all 3 dashboard sheets)

-- ============================================================
-- 1. Fix vw_practice_kpi_weekly — add mapped_clients CTE
-- ============================================================
DROP VIEW IF EXISTS vw_practice_kpi_weekly;
CREATE OR REPLACE VIEW vw_practice_kpi_weekly AS
WITH
-- Mapped clients from ps_project_mapping (same CTE as vw_productive_utilization)
mapped_clients AS (
    SELECT DISTINCT LOWER(clockify_client_name) AS client_lower
    FROM ps_project_mapping
    WHERE is_active = TRUE
),
-- Active users with their LoB and practice alignment (stripped of braces)
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
-- Weekly hours per user with CORRECT NB classification (matching vw_productive_utilization)
weekly_hours AS (
    SELECT
        te.clockify_user_id,
        DATE_TRUNC('week', te.entry_date)::DATE        AS week_start,
        SUM(te.duration_hours)                         AS hours_logged,
        SUM(CASE WHEN te.billable THEN te.duration_hours
                 ELSE 0 END)                           AS billable_hours,
        -- NB Productive: uses mapped_clients fallback (consistent with vw_productive_utilization)
        SUM(CASE
                WHEN te.billable = FALSE
                 AND (
                     cp.project_type IN ('Non Bill Productive', 'Overtime', 'Presales')
                     OR (cp.project_type IS NULL AND mc.client_lower IS NOT NULL)
                     OR (cp.project_type NOT IN ('Non Bill Productive','Non Bill Non Productive','Overtime','Presales')
                         AND cp.project_type IS NOT NULL AND mc.client_lower IS NOT NULL)
                 )
                THEN te.duration_hours
                ELSE 0
            END)                                       AS productive_nb_hours,
        -- NB Non-Productive: inverse of above (consistent with vw_productive_utilization)
        SUM(CASE
                WHEN te.billable = FALSE
                 AND NOT (
                     cp.project_type IN ('Non Bill Productive', 'Overtime', 'Presales')
                     OR (cp.project_type IS NULL AND mc.client_lower IS NOT NULL)
                     OR (cp.project_type NOT IN ('Non Bill Productive','Non Bill Non Productive','Overtime','Presales')
                         AND cp.project_type IS NOT NULL AND mc.client_lower IS NOT NULL)
                 )
                THEN te.duration_hours
                ELSE 0
            END)                                       AS nb_non_productive_hours
    FROM clockify_detailed_time_entries te
    LEFT JOIN clockify_projects cp
        ON te.clockify_project_id = cp.clockify_project_id
    LEFT JOIN mapped_clients mc
        ON LOWER(te.client_name) = mc.client_lower
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
-- 2. Create vw_kpi_staff_weekly — per-staff KPI view
--    Used by KPI Tracking Dashboard all 3 sheets
-- ============================================================
DROP VIEW IF EXISTS vw_kpi_staff_weekly;
CREATE OR REPLACE VIEW vw_kpi_staff_weekly AS
WITH
-- Mapped clients from ps_project_mapping (same CTE as vw_productive_utilization)
mapped_clients AS (
    SELECT DISTINCT LOWER(clockify_client_name) AS client_lower
    FROM ps_project_mapping
    WHERE is_active = TRUE
),
-- Active users with cleaned fields
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
-- Week spine: all complete weeks in last 52 weeks
week_spine AS (
    SELECT DISTINCT DATE_TRUNC('week', entry_date)::DATE AS week_start
    FROM clockify_detailed_time_entries
    WHERE entry_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '52 weeks'
      AND DATE_TRUNC('week', entry_date)::DATE < DATE_TRUNC('week', CURRENT_DATE)::DATE
),
-- Per-user per-week hours with CORRECT NB classification
user_weekly_hours AS (
    SELECT
        te.clockify_user_id,
        DATE_TRUNC('week', te.entry_date)::DATE AS week_start,
        SUM(te.duration_hours) AS hours_logged,
        SUM(CASE WHEN te.billable THEN te.duration_hours ELSE 0 END) AS billable_hours,
        -- NB Productive (consistent with vw_productive_utilization)
        SUM(CASE
            WHEN te.billable = FALSE
             AND (
                 cp.project_type IN ('Non Bill Productive', 'Overtime', 'Presales')
                 OR (cp.project_type IS NULL AND mc.client_lower IS NOT NULL)
                 OR (cp.project_type NOT IN ('Non Bill Productive','Non Bill Non Productive','Overtime','Presales')
                     AND cp.project_type IS NOT NULL AND mc.client_lower IS NOT NULL)
             )
            THEN te.duration_hours ELSE 0
        END) AS nb_productive_hours,
        -- NB Non-Productive (consistent with vw_productive_utilization)
        SUM(CASE
            WHEN te.billable = FALSE
             AND NOT (
                 cp.project_type IN ('Non Bill Productive', 'Overtime', 'Presales')
                 OR (cp.project_type IS NULL AND mc.client_lower IS NOT NULL)
                 OR (cp.project_type NOT IN ('Non Bill Productive','Non Bill Non Productive','Overtime','Presales')
                     AND cp.project_type IS NOT NULL AND mc.client_lower IS NOT NULL)
             )
            THEN te.duration_hours ELSE 0
        END) AS nb_non_productive_hours
    FROM clockify_detailed_time_entries te
    LEFT JOIN clockify_projects cp
        ON te.clockify_project_id = cp.clockify_project_id
    LEFT JOIN mapped_clients mc
        ON LOWER(te.client_name) = mc.client_lower
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
    -- Utilization percentages
    ROUND((COALESCE(h.billable_hours, 0) / NULLIF(u.weekly_capacity, 0) * 100)::NUMERIC, 1) AS billable_util_pct,
    ROUND(((COALESCE(h.billable_hours, 0) + COALESCE(h.nb_productive_hours, 0)) / NULLIF(u.weekly_capacity, 0) * 100)::NUMERIC, 1) AS productive_util_pct,
    -- Compliance: did the user log >= 90% of capacity?
    CASE WHEN COALESCE(h.hours_logged, 0) >= u.weekly_capacity * 0.9 THEN 'Compliant' ELSE 'Non-Compliant' END AS compliance_status,
    CASE WHEN COALESCE(h.hours_logged, 0) >= u.weekly_capacity * 0.9 THEN 1 ELSE 0 END AS is_compliant
FROM active_users u
CROSS JOIN week_spine w
LEFT JOIN user_weekly_hours h
    ON u.clockify_user_id = h.clockify_user_id
    AND h.week_start = w.week_start
WHERE u.user_created_date <= w.week_start + 6
ORDER BY w.week_start DESC, u.user_name;
