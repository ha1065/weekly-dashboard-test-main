-- Migration 101: Add resolution_date to ps_project_status
-- Captures Jira's system resolutiondate field — automatically set by Jira
-- when an issue transitions to a Done/Resolved status category.
-- Unlike actual_completion (custom field, PM-entered, 26% populated),
-- resolution_date is a system field populated for 100% of resolved issues.
-- Used as the primary close date for individual on-time delivery calculation.
ALTER TABLE ps_project_status
    ADD COLUMN IF NOT EXISTS resolution_date TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_ps_resolution_date
    ON ps_project_status(resolution_date)
    WHERE resolution_date IS NOT NULL;
