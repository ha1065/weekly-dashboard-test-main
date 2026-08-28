DROP VIEW IF EXISTS vw_ps_projects_at_risk CASCADE;

CREATE OR REPLACE VIEW vw_ps_projects_at_risk AS
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
WHERE health IN ('Red', 'Yellow');
