-- Migration 062: COALESCE escalation field in vw_ps_project_status
-- Change: TRIM(p.escalation) → COALESCE(TRIM(p.escalation), 'None')
-- Consistent with health fields which use COALESCE(..., 'Not Assigned').
-- vw_ps_projects_at_risk and vw_project_detail depend on vw_ps_project_status,
-- so they are dropped first and recreated in dependency order.

DROP VIEW IF EXISTS vw_ps_projects_at_risk CASCADE;
DROP VIEW IF EXISTS vw_project_detail CASCADE;
DROP VIEW IF EXISTS vw_ps_project_status CASCADE;

-- ============================================================
-- 1. vw_ps_project_status (base view)
-- ============================================================
CREATE VIEW vw_ps_project_status AS
WITH last_sync AS (
    SELECT MAX(synced_at) AS last_synced_at FROM ps_project_status
),
-- Actual hours from Clockify, using mapping table when available
ps_actual_hours AS (
    SELECT
        p.jira_issue_id,
        COALESCE(
            -- First: task-name match for projects where Clockify uses tasks per client (e.g. 5x5x5)
            (SELECT SUM(te.duration_hours)
             FROM ps_project_mapping m
             JOIN clockify_detailed_time_entries te
                 ON LOWER(te.project_name) = LOWER(m.clockify_project_name)
                 AND LOWER(te.task_name) = LOWER(p.client_name)
             WHERE m.is_active = TRUE
               AND LOWER(m.ps_client_name) = LOWER(p.client_name)
               AND m.clockify_project_name IS NOT NULL
               AND te.task_name IS NOT NULL
               AND te.entry_date >= DATE_TRUNC('year', CURRENT_DATE)),
            -- Second: use explicit mapping from ps_project_mapping (client+project level)
            (SELECT SUM(te.duration_hours)
             FROM ps_project_mapping m
             JOIN clockify_detailed_time_entries te
                 ON LOWER(te.client_name) = LOWER(m.clockify_client_name)
                 AND (m.clockify_project_name IS NULL
                      OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
             WHERE m.is_active = TRUE
               AND LOWER(m.ps_client_name) = LOWER(p.client_name)
               AND (m.ps_project_name IS NULL
                    OR LOWER(m.ps_project_name) = LOWER(p.project_name))
               AND te.entry_date >= DATE_TRUNC('year', CURRENT_DATE)),
            -- Third: direct client+project name match
            (SELECT SUM(te.duration_hours)
             FROM clockify_detailed_time_entries te
             WHERE LOWER(te.client_name) = LOWER(p.client_name)
               AND LOWER(te.project_name) = LOWER(p.project_name)
               AND te.entry_date >= DATE_TRUNC('year', CURRENT_DATE)),
            -- Fourth: all hours for matching client
            (SELECT SUM(te.duration_hours)
             FROM clockify_detailed_time_entries te
             WHERE LOWER(te.client_name) = LOWER(p.client_name)
               AND te.entry_date >= DATE_TRUNC('year', CURRENT_DATE))
        ) AS actual_hours
    FROM ps_project_status p
),
-- Last week's hours from Clockify, using mapping table when available
ps_last_week_hours AS (
    SELECT
        p.jira_issue_id,
        COALESCE(
            -- First: use explicit mapping from ps_project_mapping
            (SELECT SUM(te.duration_hours)
             FROM ps_project_mapping m
             JOIN clockify_detailed_time_entries te
                 ON LOWER(te.client_name) = LOWER(m.clockify_client_name)
                 AND (m.clockify_project_name IS NULL
                      OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
             WHERE m.is_active = TRUE
               AND LOWER(m.ps_client_name) = LOWER(p.client_name)
               AND (m.ps_project_name IS NULL
                    OR LOWER(m.ps_project_name) = LOWER(p.project_name))
               AND te.entry_date >= (DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days')::DATE
               AND te.entry_date < DATE_TRUNC('week', CURRENT_DATE)::DATE),
            -- Second: direct client+project name match
            (SELECT SUM(te.duration_hours)
             FROM clockify_detailed_time_entries te
             WHERE LOWER(te.client_name) = LOWER(p.client_name)
               AND LOWER(te.project_name) = LOWER(p.project_name)
               AND te.entry_date >= (DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days')::DATE
               AND te.entry_date < DATE_TRUNC('week', CURRENT_DATE)::DATE),
            -- Third: all hours for matching client
            (SELECT SUM(te.duration_hours)
             FROM clockify_detailed_time_entries te
             WHERE LOWER(te.client_name) = LOWER(p.client_name)
               AND te.entry_date >= (DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days')::DATE
               AND te.entry_date < DATE_TRUNC('week', CURRENT_DATE)::DATE)
        ) AS last_week_hours
    FROM ps_project_status p
),
-- Clockify client/project names from the explicit mapping table
ps_clockify_names AS (
    SELECT DISTINCT ON (LOWER(m.ps_client_name), LOWER(COALESCE(m.ps_project_name, '')))
        LOWER(m.ps_client_name)                    AS ps_client_key,
        LOWER(COALESCE(m.ps_project_name, ''))     AS ps_project_key,
        m.clockify_client_name,
        m.clockify_project_name
    FROM ps_project_mapping m
    WHERE m.is_active = TRUE
      AND m.category = 'PS'
    ORDER BY LOWER(m.ps_client_name),
             LOWER(COALESCE(m.ps_project_name, '')),
             m.id DESC
),
-- Actual Clockify client name from time entries (preserves Clockify casing for unmapped projects)
ps_clockify_direct AS (
    SELECT DISTINCT ON (LOWER(te.client_name))
        LOWER(te.client_name)  AS client_key,
        te.client_name         AS clockify_client_name
    FROM clockify_detailed_time_entries te
    ORDER BY LOWER(te.client_name), te.entry_date DESC
),
-- Clockify project display name for mappings where clockify_project_name is NULL.
-- Picks the Clockify project with the most hours for the mapped client this year.
-- Used so the tracker shows the real Clockify project name instead of the Jira-parsed one.
ps_clockify_project_display AS (
    SELECT DISTINCT ON (ps_client_key, ps_project_key)
        ps_client_key,
        ps_project_key,
        clockify_project_name
    FROM (
        SELECT
            LOWER(m.ps_client_name)                AS ps_client_key,
            LOWER(COALESCE(m.ps_project_name, '')) AS ps_project_key,
            te.project_name                        AS clockify_project_name,
            SUM(te.duration_hours)                 AS total_hours
        FROM ps_project_mapping m
        JOIN clockify_detailed_time_entries te
            ON LOWER(te.client_name) = LOWER(m.clockify_client_name)
        WHERE m.is_active = TRUE
          AND m.category = 'PS'
          AND m.clockify_project_name IS NULL
          AND te.entry_date >= DATE_TRUNC('year', CURRENT_DATE)::DATE
        GROUP BY LOWER(m.ps_client_name), LOWER(COALESCE(m.ps_project_name, '')), te.project_name
    ) t
    ORDER BY ps_client_key, ps_project_key, total_hours DESC
),
-- Remaining forecast hours (future weeks only), using mapping table when available
ps_remaining_forecast AS (
    SELECT
        p.jira_issue_id,
        COALESCE(
            -- First: use explicit mapping from ps_project_mapping
            (SELECT SUM(f.forecasted_hours)
             FROM ps_project_mapping m
             JOIN ps_resource_forecasts f
                 ON LOWER(f.client_name) = LOWER(m.clockify_client_name)
                 AND (m.clockify_project_name IS NULL
                      OR LOWER(f.project_name) = LOWER(m.clockify_project_name))
             WHERE m.is_active = TRUE
               AND LOWER(m.ps_client_name) = LOWER(p.client_name)
               AND (m.ps_project_name IS NULL
                    OR LOWER(m.ps_project_name) = LOWER(p.project_name))
               AND f.week_start_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE),
            -- Second: direct client name match
            (SELECT SUM(f.forecasted_hours)
             FROM ps_resource_forecasts f
             WHERE LOWER(f.client_name) = LOWER(p.client_name)
               AND f.week_start_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE)
        ) AS remaining_forecast_hours
    FROM ps_project_status p
)
SELECT
    -- Client and project info (parsed from summary)
    p.client_name,
    p.project_name,
    -- Clockify names: explicit mapping → actual Clockify name from time entries → Jira name
    COALESCE(cn.clockify_client_name,  cd.clockify_client_name,  p.client_name)  AS clockify_client_name,
    COALESCE(cn.clockify_project_name, cpd.clockify_project_name, p.project_name) AS clockify_project_name,
    p.summary AS description,
    p.issue_key,
    p.jira_project_key,

    -- Project classification
    p.project_type AS type,
    p.status AS stage,  -- DISCOVER AND ALIGN, BUILD AND IMPLEMENT, etc.
    p.status_category,
    p.issue_type,
    p.category,         -- PS / MC
    p.priority,

    -- Team members
    p.project_manager,
    p.solution_architect AS technical_lead,
    p.engineer AS assistant_lead,
    p.account_executive,
    p.csm,
    p.assignee_name,

    -- Health status fields (Red/Yellow/Green / Not Assigned)
    COALESCE(p.health_overall, 'Not Assigned') AS health,
    COALESCE(p.health_budget,  'Not Assigned') AS health_budget,
    COALESCE(p.health_scope,   'Not Assigned') AS health_scope,
    COALESCE(p.health_schedule,'Not Assigned') AS health_schedule,
    p.schedule_score,  -- On Time/Late
    p.current_health,
    COALESCE(TRIM(p.escalation), 'None') AS escalation,
    p.impact,
    p.risks_blockers,

    -- Budget vs Actual
    p.budget_hours,
    ah.actual_hours,
    lw.last_week_hours,
    CASE
        WHEN p.budget_hours > 0 AND ah.actual_hours IS NOT NULL
        THEN ROUND((ah.actual_hours / p.budget_hours * 100)::NUMERIC, 1)
        ELSE NULL
    END AS budget_percent_used,

    -- Forecast-based projections
    rf.remaining_forecast_hours,
    CASE
        WHEN ah.actual_hours IS NOT NULL OR rf.remaining_forecast_hours IS NOT NULL
        THEN ROUND((COALESCE(ah.actual_hours, 0) + COALESCE(rf.remaining_forecast_hours, 0))::NUMERIC, 1)
        ELSE NULL
    END AS projected_ending_budget,
    CASE
        WHEN p.budget_hours > 0 AND (ah.actual_hours IS NOT NULL OR rf.remaining_forecast_hours IS NOT NULL)
        THEN ROUND(((COALESCE(ah.actual_hours, 0) + COALESCE(rf.remaining_forecast_hours, 0)) / p.budget_hours * 100)::NUMERIC, 1)
        ELSE NULL
    END AS projected_ending_percent,

    -- Date fields - Planning
    p.planned_start AS start_date,
    p.planned_end AS end_date,
    p.planned_kickoff,
    p.sow_signing_date,
    p.expected_completion,
    p.revised_completion,
    p.resource_assignment_date,
    p.due_date,

    -- Date fields - Actual completion by phase
    p.actual_kickoff,
    p.actual_completion,
    p.internal_prep_completion,
    p.discover_align_completion,
    p.design_review_completion,
    p.build_implement_completion,
    p.launch_enable_completion,

    -- Calculated date metrics
    CASE
        WHEN p.expected_completion IS NOT NULL
        THEN p.expected_completion - CURRENT_DATE
        ELSE NULL
    END AS days_to_completion,
    CASE
        WHEN p.planned_kickoff IS NOT NULL AND p.expected_completion IS NOT NULL
        THEN p.expected_completion - p.planned_kickoff
        ELSE NULL
    END AS total_duration_days,

    -- Narrative fields
    p.project_summary AS summary_text,
    p.what_we_did,
    p.what_we_will_do_next,
    p.mitigation_plan,
    p.slippages AS planned_vs_actual,

    -- Links
    p.sow_link,
    p.jira_board_link,

    -- Dates and metadata
    p.created_date,
    p.updated_date,
    p.week_start,
    TO_CHAR(p.week_start, 'Mon DD') AS week_label,

    -- Sync metadata
    (SELECT last_synced_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago' FROM last_sync)::DATE AS last_updated_date,
    TO_CHAR((SELECT last_synced_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago' FROM last_sync), 'HH:MI AM') AS last_updated_time
FROM ps_project_status p
LEFT JOIN ps_actual_hours ah ON p.jira_issue_id = ah.jira_issue_id
LEFT JOIN ps_last_week_hours lw ON p.jira_issue_id = lw.jira_issue_id
LEFT JOIN ps_remaining_forecast rf ON p.jira_issue_id = rf.jira_issue_id
LEFT JOIN ps_clockify_names cn
    ON LOWER(p.client_name) = cn.ps_client_key
   AND (cn.ps_project_key = '' OR cn.ps_project_key = LOWER(COALESCE(p.project_name, '')))
LEFT JOIN ps_clockify_direct cd ON LOWER(p.client_name) = cd.client_key
LEFT JOIN ps_clockify_project_display cpd
    ON LOWER(p.client_name) = cpd.ps_client_key
   AND (cpd.ps_project_key = '' OR cpd.ps_project_key = LOWER(COALESCE(p.project_name, '')))
WHERE NOT (
    p.status_category = 'Done'
    AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE)
)
AND NOT COALESCE(p.is_excluded, FALSE)
ORDER BY
    p.updated_date DESC;

-- ============================================================
-- 2. vw_ps_projects_at_risk (depends on vw_ps_project_status)
-- ============================================================
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

-- ============================================================
-- 3. vw_project_detail (depends on vw_ps_project_status)
-- ============================================================
CREATE VIEW vw_project_detail AS
SELECT
    type,
    client_name,
    project_name,
    project_manager,
    technical_lead,
    stage,
    health                                                      AS current_health,
    health_budget,
    health_schedule,
    planned_kickoff,
    actual_kickoff,
    COALESCE(revised_completion, expected_completion, end_date) AS effective_end_date,
    COALESCE(budget_hours, 0)                                   AS sow_hours,
    COALESCE(actual_hours, 0)                                   AS actual_hours_ytd,
    COALESCE(last_week_hours, 0)                                AS last_week_hours,
    CASE
        WHEN COALESCE(budget_hours, 0) > 0
        THEN ROUND((COALESCE(actual_hours, 0) / budget_hours * 100)::NUMERIC, 1)
        ELSE 0
    END                                                         AS budget_burn_pct,
    days_to_completion                                          AS days_to_planned_end,
    CASE
        WHEN actual_kickoff IS NOT NULL AND planned_kickoff IS NOT NULL
        THEN (actual_kickoff - planned_kickoff)
        ELSE NULL
    END                                                         AS schedule_variance_days
FROM vw_ps_project_status;
