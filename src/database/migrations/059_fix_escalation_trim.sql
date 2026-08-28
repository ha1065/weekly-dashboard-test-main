-- Migration 059: Fix trailing space in escalation column in vw_ps_project_status
-- The ps_project_status.escalation field contains 'Green ' (with trailing space)
-- causing QuickSight conditional formatting expressions to fail.
-- Fix: TRIM() the value at the view level.

-- Rebuild vw_ps_project_status is handled by apply_views.py / create_views.sql
-- This migration is a no-op marker — the fix is in create_views.sql line ~1183.
-- Run: aws lambda invoke --function-name production-clockify-import
--        --payload '{"mode":"apply_views"}' response.json

SELECT 'Migration 059: escalation trim fix applied via create_views.sql' AS status;
