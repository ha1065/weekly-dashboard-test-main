-- Migration 053: vw_project_detail
-- Project detail view for QuickSight Sheet 5.
-- Actuals sourced from Clockify (system of record for all time).
-- SOW/budget hours sourced from Jira (ps_project_status.budget_hours).
-- Project names and classification sourced from Clockify via ps_project_mapping.

DROP VIEW IF EXISTS vw_project_detail;

CREATE VIEW vw_project_detail AS
WITH

-- Two-tier Clockify→PS name mapping (mirrors vw_project_hours_summary logic)
tier1 AS (
    SELECT DISTINCT ON (m.clockify_client_name, m.clockify_project_name)
        m.clockify_client_name,
        m.clockify_project_name,
        m.client_name        AS canonical_client_name,
        m.category
    FROM ps_project_mapping m
    WHERE m.is_active = TRUE
    ORDER BY m.clockify_client_name, m.clockify_project_name, m.priority ASC
),
tier2 AS (
    SELECT
        ps.client_name AS clockify_client_name,
        NULL           AS clockify_project_name,
        ps.client_name AS canonical_client_name,
        ps.category
    FROM ps_project_status ps
    WHERE NOT EXISTS (
        SELECT 1 FROM ps_project_mapping m
        WHERE m.client_name = ps.client_name AND m.is_active = TRUE
    )
),
mapping AS (
    SELECT * FROM tier1
    UNION ALL
    SELECT * FROM tier2
),

-- Clockify actual hours per project (all time, YTD)
clockify_actuals AS (
    SELECT
        COALESCE(m.canonical_client_name, te.client_name) AS canonical_client_name,
        te.project_name,
        SUM(te.duration_hours)                                          AS actual_hours_total,
        SUM(CASE WHEN te.billable THEN te.duration_hours ELSE 0 END)   AS actual_billable_hours,
        -- Last complete week hours
        SUM(CASE
            WHEN te.week_start = (DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '1 week')::DATE
            THEN te.duration_hours ELSE 0
        END)                                                            AS last_week_hours,
        MAX(te.entry_date)                                              AS last_entry_date
    FROM clockify_detailed_time_entries te
    LEFT JOIN mapping m
        ON LOWER(te.client_name) = LOWER(m.clockify_client_name)
    WHERE EXTRACT(YEAR FROM te.entry_date) = EXTRACT(YEAR FROM CURRENT_DATE)
    GROUP BY COALESCE(m.canonical_client_name, te.client_name), te.project_name
),

-- Active PS projects from Jira (status + schedule + health + SOW hours)
active_projects AS (
    SELECT
        ps.id,
        ps.issue_key,
        ps.client_name,
        ps.project_name,
        ps.category,
        ps.type,
        ps.stage,
        ps.project_manager,
        ps.technical_lead,
        ps.solution_architect,
        COALESCE(ps.current_health, ps.health_overall) AS current_health,
        ps.health_budget,
        ps.health_schedule,
        ps.health_scope,
        ps.planned_kickoff,
        ps.actual_kickoff,
        ps.planned_end,
        ps.expected_completion,
        ps.revised_completion,
        ps.actual_completion,
        ps.budget_hours,   -- SOW hours from Jira
        ps.status,
        ps.status_category
    FROM ps_project_status ps
    WHERE ps.status_category != 'Done'
       OR ps.actual_completion >= DATE_TRUNC('year', CURRENT_DATE)
)

SELECT
    ap.issue_key,
    ap.client_name,
    ap.project_name,
    ap.category,
    ap.type,
    ap.stage,
    ap.project_manager,
    ap.technical_lead,
    ap.solution_architect,
    ap.current_health,
    ap.health_budget,
    ap.health_schedule,
    ap.health_scope,
    ap.status,

    -- Schedule
    ap.planned_kickoff,
    ap.actual_kickoff,
    ap.planned_end,
    COALESCE(ap.revised_completion, ap.expected_completion, ap.planned_end) AS effective_end_date,
    ap.actual_completion,

    -- Days to planned end (negative = overdue)
    (COALESCE(ap.revised_completion, ap.expected_completion, ap.planned_end)
        - CURRENT_DATE)::INT                                            AS days_to_planned_end,

    -- SOW hours from Jira
    ap.budget_hours                                                     AS sow_hours,

    -- Actuals from Clockify (YTD)
    COALESCE(ca.actual_hours_total, 0)                                  AS actual_hours_ytd,
    COALESCE(ca.actual_billable_hours, 0)                               AS actual_billable_hours_ytd,
    COALESCE(ca.last_week_hours, 0)                                     AS last_week_hours,
    ca.last_entry_date,

    -- Budget burn % (Clockify actuals / Jira SOW hours)
    CASE
        WHEN ap.budget_hours > 0
        THEN ROUND((COALESCE(ca.actual_hours_total, 0) / ap.budget_hours * 100)::NUMERIC, 1)
        ELSE NULL
    END                                                                 AS budget_burn_pct,

    -- Schedule variance in days (negative = late)
    CASE
        WHEN ap.actual_completion IS NOT NULL AND ap.planned_end IS NOT NULL
        THEN (ap.planned_end - ap.actual_completion)::INT
        ELSE NULL
    END                                                                 AS schedule_variance_days

FROM active_projects ap
LEFT JOIN clockify_actuals ca
    ON LOWER(ap.client_name) = LOWER(ca.canonical_client_name)
    AND LOWER(ap.project_name) = LOWER(ca.project_name)
ORDER BY
    CASE ap.current_health
        WHEN 'Red'   THEN 1
        WHEN 'Amber' THEN 2
        WHEN 'Green' THEN 3
        ELSE 4
    END,
    days_to_planned_end ASC NULLS LAST;
