-- Migration 062: Add reporting_manager column to clockify_users
-- Column referenced by ORM model but missing from table, causing import failures since May 15.
ALTER TABLE clockify_users
    ADD COLUMN IF NOT EXISTS reporting_manager VARCHAR(255);
