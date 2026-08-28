-- Migration 096: Expand vw_ps_projects_at_risk to catch all at-risk projects
--
-- Previously the view only surfaced projects with health IN ('Red', 'Yellow').
-- This missed projects that are at risk due to budget overrun, schedule issues,
-- or escalations even when the overall health color is Green.
--
-- New filter includes any project where:
--   - Overall, budget, or schedule health is Red/Yellow
--   - budget_percent_used > 100
--   - escalation has a non-trivial value (not None/Green/empty)

DROP VIEW IF EXISTS vw_ps_projects_at_risk CASCADE;

CREATE VIEW vw_ps_projects_at_risk AS
SELECT
    client_name,
    project_name,
    project_manager,
    type,
    stage,
    status_category,
    health,
    health_budget,
    health_schedule,
    escalation,
    budget_hours,
    actual_hours,
    budget_percent_used,
    last_week_hours
FROM (
    SELECT DISTINCT ON (client_name, project_name)
        client_name,
        project_name,
        project_manager,
        type,
        stage,
        status_category,
        health,
        health_budget,
        health_schedule,
        escalation,
        budget_hours,
        actual_hours,
        budget_percent_used,
        last_week_hours,
        week_start
    FROM vw_ps_project_status
    WHERE category = 'PS'
      AND status_category != 'Done'
    ORDER BY client_name, project_name, week_start DESC
) latest
WHERE (
    health IN ('Red', 'Yellow')
    OR health_budget IN ('Red', 'Yellow')
    OR health_schedule IN ('Red', 'Yellow')
    OR budget_percent_used > 100
    OR (escalation IS NOT NULL AND UPPER(TRIM(escalation)) NOT IN ('NONE', 'GREEN', ''))
)
  AND status_category != 'Done';
