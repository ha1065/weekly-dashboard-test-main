-- Migration 059: Recreate vw_productive_utilization with time_submission='No' exclusion
-- This view was dropped during column rename operations and needs recreation

-- The view is defined in create_views.sql. This migration just ensures it exists.
-- Run apply_views after this migration to recreate it from the source file.

-- Placeholder: the actual view is too complex for a single migration.
-- Use Lambda apply_views mode or manual SQL execution.
SELECT 1;
