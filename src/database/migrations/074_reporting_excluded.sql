-- Migration 074: Add reporting_excluded flag to clockify_users
-- When TRUE, user is excluded from utilization metrics, compliance reports, and KPI calculations.
ALTER TABLE clockify_users
    ADD COLUMN IF NOT EXISTS reporting_excluded BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_clockify_users_reporting_excluded
    ON clockify_users (reporting_excluded) WHERE reporting_excluded = TRUE;
