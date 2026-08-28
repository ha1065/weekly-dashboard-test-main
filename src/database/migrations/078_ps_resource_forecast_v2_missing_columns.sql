-- Migration 078: Add missing columns to ps_resource_forecast_v2
ALTER TABLE ps_resource_forecast_v2
    ADD COLUMN IF NOT EXISTS level VARCHAR(100),
    ADD COLUMN IF NOT EXISTS jira_remaining_tickets INTEGER,
    ADD COLUMN IF NOT EXISTS jira_velocity_per_week NUMERIC(10,2),
    ADD COLUMN IF NOT EXISTS jira_weeks_remaining NUMERIC(10,2);
