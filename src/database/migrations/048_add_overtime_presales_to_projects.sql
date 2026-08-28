-- Migration 048: Add is_overtime and is_presales boolean flags to clockify_projects
-- These are Clockify yes/no custom fields used to classify projects as Non-Billable Productive
-- regardless of their project_type value.
ALTER TABLE clockify_projects
    ADD COLUMN IF NOT EXISTS is_overtime BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_presales BOOLEAN DEFAULT FALSE;
