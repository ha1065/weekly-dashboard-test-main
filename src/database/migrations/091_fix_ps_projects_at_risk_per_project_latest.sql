-- Migration 060: Fix vw_ps_projects_at_risk to show each project's most recent row
--
-- Previously the view filtered on the globally latest week_start, which excluded
-- Red/Yellow projects that hadn't been synced in the most recent week (e.g. projects
-- on 2026-05-11 were hidden when the global MAX was 2026-05-18).
--
-- Fix: use DISTINCT ON (client_name, project_name) ORDER BY week_start DESC so each
-- project contributes its own latest row before the health filter is applied.

DROP VIEW IF EXISTS vw_ps_projects_at_risk;

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
FROM (
    SELECT DISTINCT ON (client_name, project_name)
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
        last_week_hours,
        week_start
    FROM vw_ps_project_status
    WHERE category = 'PS'
    ORDER BY client_name, project_name, week_start DESC
) latest
WHERE health IN ('Red', 'Yellow');
