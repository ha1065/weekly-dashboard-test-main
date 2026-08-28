-- Migration 021: Add employment_designation to ps_resource_forecasts and history
-- Backfill from clockify_users by matching on user name

DO $$ BEGIN
    -- Add to ps_resource_forecasts
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecasts'
          AND column_name = 'employment_designation'
    ) THEN
        ALTER TABLE ps_resource_forecasts ADD COLUMN employment_designation VARCHAR(100);
    END IF;

    -- Add to ps_resource_forecast_history
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecast_history'
          AND column_name = 'employment_designation'
    ) THEN
        ALTER TABLE ps_resource_forecast_history ADD COLUMN employment_designation VARCHAR(100);
    END IF;
END $$;

-- Backfill ps_resource_forecasts from clockify_users
UPDATE ps_resource_forecasts f
SET employment_designation = u.employment_designation
FROM clockify_users u
WHERE LOWER(f.user_name) = LOWER(u.name)
  AND f.employment_designation IS NULL
  AND u.employment_designation IS NOT NULL;

-- Backfill ps_resource_forecast_history from clockify_users
UPDATE ps_resource_forecast_history h
SET employment_designation = u.employment_designation
FROM clockify_users u
WHERE LOWER(h.user_name) = LOWER(u.name)
  AND h.employment_designation IS NULL
  AND u.employment_designation IS NOT NULL;
