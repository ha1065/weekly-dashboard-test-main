-- Migration 059: Fix vw_ps_projects_at_risk to filter category = 'PS'
-- vw_ps_project_status contains both PS and MC rows. Without the category
-- filter, MC projects leaked into the PS at-risk view on sheet-ps-delivery.

DROP VIEW IF EXISTS vw_ps_projects_at_risk CASCADE;

CREATE OR REPLACE VIEW vw_ps_projects_at_risk AS
SELECT
    client_name,
    project_name,
    project_manager,
    type,
    stage,
    health,
    health_budget,
    health_schedule,
    escalation,
    budget_hours,
    actual_hours,
    budget_percent_used,
    last_week_hours
FROM vw_ps_project_status
WHERE week_start = (SELECT MAX(week_start) FROM vw_ps_project_status)
  AND health IN ('Red', 'Yellow')
  AND category = 'PS';
