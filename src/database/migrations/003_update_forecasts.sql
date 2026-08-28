-- Migration: Update ps_resource_forecasts table to match weekly forecasting template
-- Run this on the existing database to apply schema changes

-- ============================================================
-- Step 1: Add new columns to ps_resource_forecasts
-- ============================================================
ALTER TABLE ps_resource_forecasts
ADD COLUMN IF NOT EXISTS project_type VARCHAR(100);

ALTER TABLE ps_resource_forecasts
ADD COLUMN IF NOT EXISTS pm_name VARCHAR(255);

ALTER TABLE ps_resource_forecasts
ADD COLUMN IF NOT EXISTS stage VARCHAR(100);

ALTER TABLE ps_resource_forecasts
ADD COLUMN IF NOT EXISTS actual_hours FLOAT DEFAULT 0;

ALTER TABLE ps_resource_forecasts
ADD COLUMN IF NOT EXISTS comments TEXT;

-- Add forecasted_hours if it doesn't exist (for fresh installs)
ALTER TABLE ps_resource_forecasts
ADD COLUMN IF NOT EXISTS forecasted_hours FLOAT DEFAULT 0;

-- ============================================================
-- Step 2: Copy data from old column name if it exists
-- ============================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecasts'
        AND column_name = 'forecasted_hours_per_week'
    ) THEN
        UPDATE ps_resource_forecasts
        SET forecasted_hours = forecasted_hours_per_week
        WHERE forecasted_hours IS NULL OR forecasted_hours = 0;

        ALTER TABLE ps_resource_forecasts DROP COLUMN forecasted_hours_per_week;
    END IF;
END $$;

-- ============================================================
-- Step 3: Copy notes to comments if notes column exists
-- ============================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecasts'
        AND column_name = 'notes'
    ) THEN
        UPDATE ps_resource_forecasts
        SET comments = notes
        WHERE comments IS NULL;

        ALTER TABLE ps_resource_forecasts DROP COLUMN notes;
    END IF;
END $$;

-- ============================================================
-- Step 4: Make columns nullable as needed
-- ============================================================
DO $$
BEGIN
    -- Make clockify_user_id nullable if it's not already
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecasts'
        AND column_name = 'clockify_user_id'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE ps_resource_forecasts ALTER COLUMN clockify_user_id DROP NOT NULL;
    END IF;

    -- Make project_name nullable if it's not already
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecasts'
        AND column_name = 'project_name'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE ps_resource_forecasts ALTER COLUMN project_name DROP NOT NULL;
    END IF;
END $$;

-- ============================================================
-- Step 5: Create indexes for common query patterns
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_forecasts_week_start ON ps_resource_forecasts(week_start_date);
CREATE INDEX IF NOT EXISTS idx_forecasts_pm ON ps_resource_forecasts(pm_name);
CREATE INDEX IF NOT EXISTS idx_forecasts_client ON ps_resource_forecasts(client_name);
CREATE INDEX IF NOT EXISTS idx_forecasts_user ON ps_resource_forecasts(user_name);

-- ============================================================
-- Step 6: Create view for forecast vs actual comparison
-- ============================================================
CREATE OR REPLACE VIEW vw_forecast_vs_actual AS
WITH forecast_data AS (
    SELECT
        f.week_start_date,
        f.user_name,
        f.client_name,
        f.project_name,
        f.project_type,
        f.pm_name,
        f.stage,
        f.forecasted_hours,
        f.actual_hours AS forecast_actual_hours
    FROM ps_resource_forecasts f
),
actual_data AS (
    SELECT
        te.week_start,
        te.user_name,
        te.client_name,
        te.project_name,
        SUM(te.duration_hours) AS actual_hours
    FROM clockify_detailed_time_entries te
    WHERE te.week_start IS NOT NULL
    GROUP BY te.week_start, te.user_name, te.client_name, te.project_name
)
SELECT
    COALESCE(f.week_start_date, a.week_start) AS week_start_date,
    COALESCE(f.user_name, a.user_name) AS user_name,
    COALESCE(f.client_name, a.client_name) AS client_name,
    COALESCE(f.project_name, a.project_name) AS project_name,
    f.project_type,
    f.pm_name,
    f.stage,
    COALESCE(f.forecasted_hours, 0) AS forecasted_hours,
    COALESCE(a.actual_hours, 0) AS actual_hours,
    COALESCE(a.actual_hours, 0) - COALESCE(f.forecasted_hours, 0) AS variance_hours,
    CASE
        WHEN COALESCE(f.forecasted_hours, 0) > 0
        THEN ROUND(((COALESCE(a.actual_hours, 0) / f.forecasted_hours) * 100)::NUMERIC, 1)
        ELSE NULL
    END AS actual_pct_of_forecast
FROM forecast_data f
FULL OUTER JOIN actual_data a
    ON f.week_start_date = a.week_start
    AND LOWER(f.user_name) = LOWER(a.user_name)
    AND LOWER(COALESCE(f.client_name, '')) = LOWER(COALESCE(a.client_name, ''))
    AND LOWER(COALESCE(f.project_name, '')) = LOWER(COALESCE(a.project_name, ''))
ORDER BY week_start_date DESC, user_name, client_name, project_name;

-- ============================================================
-- Migration complete
-- ============================================================
