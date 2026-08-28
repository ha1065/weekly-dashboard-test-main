-- Migration: Remove duplicate forecast records
-- Keep the record with the lowest forecast_id for each unique combination

-- Delete duplicates, keeping only the first one (lowest forecast_id)
DELETE FROM ps_resource_forecasts
WHERE forecast_id IN (
    SELECT forecast_id
    FROM (
        SELECT forecast_id,
               ROW_NUMBER() OVER (
                   PARTITION BY user_name, week_start_date, client_name, project_name
                   ORDER BY forecast_id
               ) AS rn
        FROM ps_resource_forecasts
    ) duplicates
    WHERE rn > 1
);

-- Add a unique constraint to prevent future duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_ps_resource_forecasts_unique
ON ps_resource_forecasts(user_name, week_start_date, client_name, project_name);
