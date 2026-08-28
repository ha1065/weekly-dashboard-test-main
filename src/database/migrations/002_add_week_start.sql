-- Migration: Add week_start column to clockify_detailed_time_entries
-- Run this on the existing database to apply schema changes

-- ============================================================
-- Step 1: Add week_start column to the time entries table
-- ============================================================
ALTER TABLE clockify_detailed_time_entries
ADD COLUMN IF NOT EXISTS week_start DATE;

-- ============================================================
-- Step 2: Backfill week_start from entry_date for existing rows
-- ============================================================
UPDATE clockify_detailed_time_entries
SET week_start = DATE_TRUNC('week', entry_date)::DATE
WHERE week_start IS NULL AND entry_date IS NOT NULL;

-- ============================================================
-- Step 3: Create index on week_start for query performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_time_entries_week_start
ON clockify_detailed_time_entries(week_start);

-- ============================================================
-- Step 4: Update vw_missing_time_submissions to use week_start
-- ============================================================
DROP VIEW IF EXISTS vw_missing_time_submissions;

CREATE VIEW vw_missing_time_submissions AS
WITH last_complete_week AS (
    SELECT (DATE_TRUNC('week', CURRENT_DATE)::DATE - 7)::DATE AS week_start_date
),
user_hours_last_week AS (
    SELECT
        te.clockify_user_id,
        SUM(te.duration_hours) AS total_hours,
        COUNT(*) AS entry_count
    FROM clockify_detailed_time_entries te
    WHERE te.week_start = (SELECT week_start_date FROM last_complete_week)
    GROUP BY te.clockify_user_id
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
)
SELECT
    u.clockify_user_id,
    u.name,
    u.email,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.pod_assignment, '{', ''), '}', ''), '"', ''), E'\\', '')) AS pod_assignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.practice_alignment, '{', ''), '}', ''), '"', ''), E'\\', '')) AS practice_alignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.skill_area, '{', ''), '}', ''), '"', ''), E'\\', '')) AS skill_area,
    u.location,
    u.daily_capacity,
    u.daily_capacity * 5 AS weekly_expected_hours,
    COALESCE(h.total_hours, 0) AS hours_submitted,
    COALESCE(h.entry_count, 0) AS entries_submitted,
    CASE WHEN COALESCE(h.total_hours, 0) = 0 THEN 'No Time Submitted' ELSE 'Complete' END AS submission_status,
    CASE
        WHEN COALESCE(h.total_hours, 0) = 0 THEN '0 Hours'
        WHEN COALESCE(h.total_hours, 0) < 20 THEN '1-19 Hours'
        WHEN COALESCE(h.total_hours, 0) < 30 THEN '20-29 Hours'
        ELSE '30+ Hours'
    END AS hours_bucket,
    (SELECT week_start_date FROM last_complete_week) AS week_start_date,
    (SELECT last_updated_date FROM last_clockify_import) AS last_updated_date,
    (SELECT last_updated_time FROM last_clockify_import) AS last_updated_time
FROM clockify_users u
LEFT JOIN user_hours_last_week h ON u.clockify_user_id = h.clockify_user_id
WHERE u.status = 'active'
  AND u.daily_capacity > 0
  AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
  AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
  AND u.created_at::DATE <= (SELECT week_start_date FROM last_complete_week) + INTERVAL '6 days'
  AND COALESCE(h.total_hours, 0) = 0
  AND NOT COALESCE(u.reporting_excluded, FALSE)
ORDER BY u.pod_assignment, u.name;

-- ============================================================
-- Migration complete
-- ============================================================
