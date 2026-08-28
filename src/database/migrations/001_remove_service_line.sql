-- Migration: Remove service_line column and update schema
-- Run this on the existing database to apply schema changes
-- This migration is idempotent and can be run multiple times safely

-- Check if service_line column exists before attempting to drop it
DO $$
BEGIN
    -- Only proceed if service_line column exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clockify_detailed_time_entries'
        AND column_name = 'service_line'
    ) THEN
        -- Remove service_line from clockify_users if it exists
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'clockify_users' AND column_name = 'service_line') THEN
            ALTER TABLE clockify_users DROP COLUMN service_line;
        END IF;

        -- Remove service_line from clockify_detailed_time_entries if it exists
        ALTER TABLE clockify_detailed_time_entries DROP COLUMN service_line;
    END IF;
END $$;

-- ============================================================
-- Step 2: Drop old views that reference service_line
-- ============================================================
DROP VIEW IF EXISTS vw_service_line_performance_12w;

-- ============================================================
-- Step 3: Recreate all views with practice_alignment
-- ============================================================

-- View 1: Weekly Time Summary by Practice Alignment and Location
CREATE OR REPLACE VIEW vw_weekly_time_summary AS
SELECT
    DATE_TRUNC('week', entry_date)::DATE AS week_start_date,
    DATE_TRUNC('week', entry_date)::DATE + INTERVAL '6 days' AS week_end_date,
    practice_alignment,
    location,
    COUNT(DISTINCT clockify_user_id) AS unique_resources,
    COUNT(*) AS total_entries,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours,
    SUM(CASE WHEN NOT billable THEN duration_hours ELSE 0 END) AS non_billable_hours,
    AVG(duration_hours) AS avg_hours_per_entry
FROM clockify_detailed_time_entries
GROUP BY DATE_TRUNC('week', entry_date)::DATE, practice_alignment, location;

-- View 2: Resource Utilization Summary
CREATE OR REPLACE VIEW vw_resource_utilization AS
SELECT
    DATE_TRUNC('week', te.entry_date)::DATE AS week_start_date,
    te.clockify_user_id,
    te.user_name,
    u.cloudelligent_title,
    u.practice_alignment,
    u.skill_area,
    u.pod_assignment,
    u.location,
    u.employment_designation,
    u.daily_capacity,
    u.daily_capacity * 5 AS weekly_capacity,
    SUM(te.duration_hours) AS actual_hours,
    ROUND((SUM(te.duration_hours) / NULLIF(u.daily_capacity * 5, 0) * 100)::NUMERIC, 2) AS utilization_percent,
    SUM(CASE WHEN te.billable THEN te.duration_hours ELSE 0 END) AS billable_hours,
    ROUND((SUM(CASE WHEN te.billable THEN te.duration_hours ELSE 0 END) / NULLIF(SUM(te.duration_hours), 0) * 100)::NUMERIC, 2) AS billable_percent
FROM clockify_detailed_time_entries te
JOIN clockify_users u ON te.clockify_user_id = u.clockify_user_id
GROUP BY
    DATE_TRUNC('week', te.entry_date)::DATE,
    te.clockify_user_id,
    te.user_name,
    u.cloudelligent_title,
    u.practice_alignment,
    u.skill_area,
    u.pod_assignment,
    u.location,
    u.employment_designation,
    u.daily_capacity;

-- View 3: Project Time Tracking
CREATE OR REPLACE VIEW vw_project_time_tracking AS
SELECT
    DATE_TRUNC('week', entry_date)::DATE AS week_start_date,
    project_name,
    client_name,
    practice_alignment,
    COUNT(DISTINCT clockify_user_id) AS resources_assigned,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours,
    COUNT(*) AS entry_count,
    MIN(entry_date) AS first_entry_date,
    MAX(entry_date) AS last_entry_date
FROM clockify_detailed_time_entries
GROUP BY
    DATE_TRUNC('week', entry_date)::DATE,
    project_name,
    client_name,
    practice_alignment;

-- View 4: Client Time Summary
CREATE OR REPLACE VIEW vw_client_time_summary AS
SELECT
    DATE_TRUNC('week', entry_date)::DATE AS week_start_date,
    client_name,
    practice_alignment,
    COUNT(DISTINCT project_name) AS active_projects,
    COUNT(DISTINCT clockify_user_id) AS resources_working,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours,
    COUNT(*) AS total_entries
FROM clockify_detailed_time_entries
WHERE client_name IS NOT NULL
GROUP BY
    DATE_TRUNC('week', entry_date)::DATE,
    client_name,
    practice_alignment;

-- View 5: Skill Area Distribution
CREATE OR REPLACE VIEW vw_skill_area_summary AS
SELECT
    DATE_TRUNC('week', entry_date)::DATE AS week_start_date,
    skill_area,
    practice_alignment,
    pod_assignment,
    location,
    COUNT(DISTINCT clockify_user_id) AS unique_resources,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours
FROM clockify_detailed_time_entries
WHERE skill_area IS NOT NULL
GROUP BY
    DATE_TRUNC('week', entry_date)::DATE,
    skill_area,
    practice_alignment,
    pod_assignment,
    location;

-- View 6: Daily Activity Trend
CREATE OR REPLACE VIEW vw_daily_activity_trend AS
SELECT
    entry_date,
    EXTRACT(DOW FROM entry_date) AS day_of_week,
    TO_CHAR(entry_date, 'Day') AS day_name,
    practice_alignment,
    location,
    COUNT(DISTINCT clockify_user_id) AS active_resources,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours,
    COUNT(*) AS entry_count
FROM clockify_detailed_time_entries
GROUP BY entry_date, practice_alignment, location;

-- View 7: Resource Directory (Active Users)
CREATE OR REPLACE VIEW vw_active_resources AS
SELECT
    u.clockify_user_id,
    u.name,
    u.email,
    u.cloudelligent_title,
    u.practice_alignment,
    u.skill_area,
    u.pod_assignment,
    u.location,
    u.employment_designation,
    u.daily_capacity,
    u.status,
    u.updated_at AS last_profile_update,
    COALESCE(recent.last_entry_date, NULL) AS last_time_entry_date,
    COALESCE(recent.hours_last_30_days, 0) AS hours_last_30_days
FROM clockify_users u
LEFT JOIN (
    SELECT
        clockify_user_id,
        MAX(entry_date) AS last_entry_date,
        SUM(CASE WHEN entry_date >= CURRENT_DATE - INTERVAL '30 days' THEN duration_hours ELSE 0 END) AS hours_last_30_days
    FROM clockify_detailed_time_entries
    GROUP BY clockify_user_id
) recent ON u.clockify_user_id = recent.clockify_user_id
WHERE u.status = 'active';

-- View 9: Practice Alignment Performance (Last 12 Weeks)
CREATE OR REPLACE VIEW vw_practice_alignment_performance_12w AS
SELECT
    DATE_TRUNC('week', entry_date)::DATE AS week_start_date,
    practice_alignment,
    COUNT(DISTINCT clockify_user_id) AS unique_resources,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours,
    ROUND((SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) / NULLIF(SUM(duration_hours), 0) * 100)::NUMERIC, 2) AS billable_percent,
    COUNT(DISTINCT project_name) AS active_projects,
    COUNT(DISTINCT client_name) AS active_clients
FROM clockify_detailed_time_entries
WHERE entry_date >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY DATE_TRUNC('week', entry_date)::DATE, practice_alignment
ORDER BY week_start_date DESC, practice_alignment;

-- View 10: Monthly Summary (for historical trending)
CREATE OR REPLACE VIEW vw_monthly_summary AS
SELECT
    DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
    TO_CHAR(entry_date, 'YYYY-MM') AS year_month,
    practice_alignment,
    location,
    COUNT(DISTINCT clockify_user_id) AS unique_resources,
    SUM(duration_hours) AS total_hours,
    SUM(CASE WHEN billable THEN duration_hours ELSE 0 END) AS billable_hours,
    COUNT(DISTINCT project_name) AS active_projects,
    COUNT(DISTINCT client_name) AS active_clients
FROM clockify_detailed_time_entries
GROUP BY DATE_TRUNC('month', entry_date)::DATE, TO_CHAR(entry_date, 'YYYY-MM'), practice_alignment, location;

-- ============================================================
-- Migration complete
-- ============================================================
