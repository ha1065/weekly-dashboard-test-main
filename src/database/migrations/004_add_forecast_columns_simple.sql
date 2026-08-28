-- Migration: Add missing columns to ps_resource_forecasts (simple version)
-- This uses simple ALTER TABLE statements without DO $$ blocks

ALTER TABLE ps_resource_forecasts ADD COLUMN IF NOT EXISTS project_type VARCHAR(100);
ALTER TABLE ps_resource_forecasts ADD COLUMN IF NOT EXISTS pm_name VARCHAR(255);
ALTER TABLE ps_resource_forecasts ADD COLUMN IF NOT EXISTS stage VARCHAR(100);
ALTER TABLE ps_resource_forecasts ADD COLUMN IF NOT EXISTS actual_hours FLOAT DEFAULT 0;
ALTER TABLE ps_resource_forecasts ADD COLUMN IF NOT EXISTS comments TEXT;
ALTER TABLE ps_resource_forecasts ADD COLUMN IF NOT EXISTS forecasted_hours FLOAT DEFAULT 0;

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_forecasts_week_start ON ps_resource_forecasts(week_start_date);
CREATE INDEX IF NOT EXISTS idx_forecasts_pm ON ps_resource_forecasts(pm_name);
CREATE INDEX IF NOT EXISTS idx_forecasts_client ON ps_resource_forecasts(client_name);
CREATE INDEX IF NOT EXISTS idx_forecasts_user ON ps_resource_forecasts(user_name);
