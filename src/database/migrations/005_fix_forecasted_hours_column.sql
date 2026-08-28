-- Migration: Fix forecasted_hours column name mismatch
-- The model uses 'forecasted_hours' but database may have 'forecasted_hours_per_week'
-- Use RENAME instead of DROP to preserve view dependencies

DO $$
BEGIN
    -- Check if old column exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecasts'
        AND column_name = 'forecasted_hours_per_week'
    ) THEN
        -- Rename the column (this preserves view dependencies)
        ALTER TABLE ps_resource_forecasts RENAME COLUMN forecasted_hours_per_week TO forecasted_hours;
    ELSE
        -- Old column doesn't exist, ensure new column exists
        ALTER TABLE ps_resource_forecasts ADD COLUMN IF NOT EXISTS forecasted_hours FLOAT DEFAULT 0;
    END IF;
END $$;

-- Ensure forecasted_hours has NOT NULL constraint with default
ALTER TABLE ps_resource_forecasts ALTER COLUMN forecasted_hours SET DEFAULT 0;
ALTER TABLE ps_resource_forecasts ALTER COLUMN forecasted_hours SET NOT NULL;
