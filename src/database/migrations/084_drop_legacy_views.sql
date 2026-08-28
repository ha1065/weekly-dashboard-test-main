-- Migration 084: Drop 10 legacy scaffold views from the original project setup.
-- These views fed the older quicksight-dashboards.yaml stack which was superseded
-- by coo-dashboards.yaml. None are referenced in coo-dashboards.yaml, lambda_handler.py,
-- or app.py.
--
-- PREREQUISITE: Confirm quicksight-dashboards.yaml stack is not actively used before
-- applying. Run: python scripts/check_all_spice.py and verify none of these dataset IDs
-- are refreshing: clockify-weekly-summary, clockify-resource-utilization,
-- clockify-project-tracking, clockify-client-summary, clockify-skill-area,
-- clockify-daily-trend, clockify-active-resources, clockify-monthly-summary,
-- vw-import-activity, clockify-practice-performance

DROP VIEW IF EXISTS vw_weekly_time_summary;
DROP VIEW IF EXISTS vw_resource_utilization;
DROP VIEW IF EXISTS vw_project_time_tracking;
DROP VIEW IF EXISTS vw_client_time_summary;
DROP VIEW IF EXISTS vw_skill_area_summary;
DROP VIEW IF EXISTS vw_daily_activity_trend;
DROP VIEW IF EXISTS vw_active_resources;
DROP VIEW IF EXISTS vw_monthly_summary;
DROP VIEW IF EXISTS vw_import_activity;
DROP VIEW IF EXISTS vw_practice_alignment_performance_12w;
