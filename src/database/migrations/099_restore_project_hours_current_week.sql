-- Migration 099: Restore vw_project_hours_current_week
-- This view was defined in migration 050 but may not have been applied.
-- It is required by the project-hours-current-week-prod QuickSight SPICE dataset.

DROP VIEW IF EXISTS vw_project_hours_current_week;
CREATE VIEW vw_project_hours_current_week AS
SELECT
    week_start_date,
    client_name,
    project_name,
    category,
    practice_alignment,
    total_hours,
    billable_hours,
    billable_pct,
    resource_count,
    avg_hours_4w,
    avg_hours_12w,
    pct_change_vs_4w,
    trend,
    performance_band,
    current_health,
    budget_hours,
    project_manager,
    solution_architect,
    escalation
FROM vw_project_hours_summary
WHERE week_start_date = DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '1 week';
