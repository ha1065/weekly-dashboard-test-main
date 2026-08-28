-- Migration: Copy data from forecasted_hours_per_week to forecasted_hours
-- The migration 005 created both columns, but data is in the old column
-- This migration is idempotent and can be run multiple times safely

-- Only proceed if the old column still exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ps_resource_forecasts'
        AND column_name = 'forecasted_hours_per_week'
    ) THEN
        -- Copy data from old column to new column
        UPDATE ps_resource_forecasts
        SET forecasted_hours = COALESCE(forecasted_hours_per_week, 0)
        WHERE forecasted_hours = 0 AND forecasted_hours_per_week IS NOT NULL;

        -- Drop the old column now that data is copied
        ALTER TABLE ps_resource_forecasts DROP COLUMN forecasted_hours_per_week CASCADE;
    END IF;
END $$;
