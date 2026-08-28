-- Migration 045: Add time_submission field to clockify_users
-- Stores the Clockify custom field "Time Submission"
-- When set to 'No', the user is excluded from missing time tracking
ALTER TABLE clockify_users
    ADD COLUMN IF NOT EXISTS time_submission TEXT DEFAULT NULL;
