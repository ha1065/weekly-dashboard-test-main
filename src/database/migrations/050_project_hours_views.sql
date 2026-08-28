-- Migration 050: Project Hours Views for COO Dashboard
-- Creates vw_project_hours_summary, vw_project_hours_current_week,
-- and vw_category_hours_summary.
-- These power the Project Hours and Category tabs in coo-dashboards.

-- ============================================================
-- vw_project_hours_summary
-- Weekly hours per project with 4w/12w averages, trend,
-- delivery health enrichment, and escalation flag.
-- ============================================================
DROP VIEW IF EXISTS vw_project_hours_summary CASCADE;
CREATE VIEW vw_project_hours_summary AS
WITH

-- ----------------------------------------------------------------
-- Client/project name mapping: clockify → canonical (same logic
-- as vw_project_hours_by_assignment tier1/tier2)
-- ----------------------------------------------------------------
tier1 AS (
    SELECT DISTINCT ON (m.clockify_client_name, COALESCE(m.clockify_project_name, ''))
        m.ps_client_name        AS canonical_client,
        m.clockify_client_name  AS cw_client,
        m.clockify_project_name AS cw_project,
        m.category              AS category
    FROM ps_project_mapping m
    WHERE m.is_active = TRUE
    ORDER BY m.clockify_client_name,
             COALESCE(m.clockify_project_name, ''),
             (m.ps_project_name IS NULL),
             m.id
),
tier2 AS (
    SELECT
        pss.client_name  AS canonical_client,
        pss.client_name  AS cw_client,
        NULL::TEXT       AS cw_project,
        pss.category     AS category
    FROM ps_project_status pss
    WHERE NOT EXISTS (
        SELECT 1 FROM ps_project_mapping m2
        WHERE LOWER(m2.ps_client_name) = LOWER(pss.client_name)
          AND m2.category = pss.category
          AND m2.is_active = TRUE
    )
),
mapping AS (
    SELECT canonical_client, cw_client, cw_project, category FROM tier1
    UNION ALL
    SELECT canonical_client, cw_client, cw_project, category FROM tier2
),

-- ----------------------------------------------------------------
-- Weekly hours per (client, project, week)
-- Only look back 30 weeks — enough for 12-week averages
-- ----------------------------------------------------------------
weekly_hours AS (
    SELECT
        DATE_TRUNC('week', te.entry_date)::DATE       AS week_start_date,
        te.client_name                                AS clockify_client_name,
        te.project_name,
        COALESCE(mp.canonical_client, te.client_name) AS client_name,
        COALESCE(mp.category, 'Other')                AS category,
        NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
            COALESCE(cp.pod_assignment, ''),
            '{',''),'}',''),'"',''),'\','')), '')      AS pod_assignment,
        ROUND(SUM(te.duration_hours)::NUMERIC, 2)     AS total_hours,
        ROUND(SUM(CASE WHEN te.billable THEN te.duration_hours ELSE 0 END)::NUMERIC, 2)
                                                      AS billable_hours,
        COUNT(DISTINCT te.clockify_user_id)           AS resource_count,
        COUNT(*)                                      AS entry_count
    FROM clockify_detailed_time_entries te
    LEFT JOIN clockify_projects cp
           ON te.clockify_project_id = cp.clockify_project_id
    LEFT JOIN mapping mp
           ON LOWER(te.client_name) = LOWER(mp.cw_client)
          AND (mp.cw_project IS NULL
               OR LOWER(te.project_name) = LOWER(mp.cw_project))
    WHERE te.duration_hours > 0
      AND te.entry_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '30 weeks'
    GROUP BY
        DATE_TRUNC('week', te.entry_date)::DATE,
        te.client_name,
        te.project_name,
        COALESCE(mp.canonical_client, te.client_name),
        COALESCE(mp.category, 'Other'),
        NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
            COALESCE(cp.pod_assignment, ''),
            '{',''),'}',''),'"',''),'\','')), '')
),

-- ----------------------------------------------------------------
-- 4-week rolling average (weeks 2–5 before last complete week)
-- ----------------------------------------------------------------
avg_4w AS (
    SELECT
        client_name,
        project_name,
        AVG(total_hours) AS avg_hours_4w
    FROM weekly_hours
    WHERE week_start_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '5 weeks'
      AND week_start_date <  DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '1 week'
    GROUP BY client_name, project_name
),

-- ----------------------------------------------------------------
-- 12-week rolling average (weeks 2–13 before last complete week)
-- ----------------------------------------------------------------
avg_12w AS (
    SELECT
        client_name,
        project_name,
        AVG(total_hours) AS avg_hours_12w
    FROM weekly_hours
    WHERE week_start_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '13 weeks'
      AND week_start_date <  DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '1 week'
    GROUP BY client_name, project_name
),

-- ----------------------------------------------------------------
-- Prior week hours for trend direction (week 2 = 2 weeks ago)
-- ----------------------------------------------------------------
prior_week AS (
    SELECT client_name, project_name, total_hours AS prior_hours
    FROM weekly_hours
    WHERE week_start_date = DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '2 weeks'
),

-- ----------------------------------------------------------------
-- ps_project_status enrichment — health, dates, PM/SA
-- Join via mapping table first (clockify name → canonical Jira name),
-- then fall back to direct name match.  This fixes the 1% health
-- population rate caused by Clockify/Jira client name mismatches.
-- ----------------------------------------------------------------
ps_via_mapping AS (
    -- Tier 1: explicit ps_project_mapping entry
    SELECT DISTINCT ON (m.clockify_client_name, COALESCE(m.clockify_project_name,''))
        m.clockify_client_name  AS cw_client,
        m.clockify_project_name AS cw_project,
        p.client_name,
        p.project_name,
        p.category,
        p.status                AS jira_status,
        COALESCE(p.current_health, p.health_overall) AS current_health,
        p.health_overall,
        p.health_budget,
        p.health_scope,
        p.health_schedule,
        p.budget_hours,
        p.project_manager,
        p.solution_architect,
        p.planned_start,
        p.planned_end,
        p.actual_kickoff,
        p.actual_completion
    FROM ps_project_mapping m
    JOIN ps_project_status p
      ON LOWER(p.client_name)  = LOWER(m.ps_client_name)
     AND (m.ps_project_name IS NULL
          OR LOWER(p.project_name) = LOWER(m.ps_project_name))
    WHERE m.is_active = TRUE
      AND NOT COALESCE(p.is_excluded, FALSE)
    ORDER BY m.clockify_client_name,
             COALESCE(m.clockify_project_name,''),
             (m.ps_project_name IS NULL),
             m.id
),
ps_direct AS (
    -- Tier 2: direct name match (no mapping entry)
    SELECT DISTINCT ON (client_name, project_name)
        client_name             AS cw_client,
        project_name            AS cw_project,
        client_name,
        project_name,
        category,
        status                  AS jira_status,
        COALESCE(current_health, health_overall) AS current_health,
        health_overall,
        health_budget,
        health_scope,
        health_schedule,
        budget_hours,
        project_manager,
        solution_architect,
        planned_start,
        planned_end,
        actual_kickoff,
        actual_completion
    FROM ps_project_status
    WHERE NOT COALESCE(is_excluded, FALSE)
    ORDER BY client_name, project_name, synced_at DESC NULLS LAST
),

-- ----------------------------------------------------------------
-- Clients with open (non-resolved) escalations
-- ----------------------------------------------------------------
escalated_clients AS (
    SELECT DISTINCT LOWER(customer_name) AS customer_name_lower
    FROM escalations
    WHERE resolution_date IS NULL
      AND COALESCE(status_category, '') NOT IN ('Done', 'Resolved')
)

SELECT
    wh.week_start_date,
    wh.client_name,
    wh.clockify_client_name,
    wh.project_name,
    COALESCE(ps.category, wh.category)             AS category,
    CASE COALESCE(ps.category, wh.category)
        WHEN 'PS'     THEN 'Professional Services'
        WHEN 'MC'     THEN 'Managed Cloud'
        WHEN 'FinOps' THEN 'FinOps'
        ELSE COALESCE(ps.category, wh.category, 'Other')
    END                                             AS practice_alignment,
    wh.pod_assignment,
    wh.total_hours,
    wh.billable_hours,
    CASE WHEN wh.total_hours > 0
         THEN ROUND((wh.billable_hours / wh.total_hours * 100)::NUMERIC, 1)
         ELSE 0::NUMERIC
    END                                             AS billable_pct,
    wh.resource_count,
    wh.entry_count,
    ROUND(COALESCE(a4.avg_hours_4w,   0)::NUMERIC, 2) AS avg_hours_4w,
    ROUND(COALESCE(a12.avg_hours_12w, 0)::NUMERIC, 2) AS avg_hours_12w,
    CASE WHEN COALESCE(a4.avg_hours_4w, 0) > 0
         THEN ROUND(((wh.total_hours - a4.avg_hours_4w)
                     / a4.avg_hours_4w * 100)::NUMERIC, 1)
         ELSE 0::NUMERIC
    END                                             AS pct_change_vs_4w,
    CASE
        WHEN wh.total_hours > COALESCE(pw.prior_hours, 0) THEN 'Up'
        WHEN wh.total_hours < COALESCE(pw.prior_hours, 0) THEN 'Down'
        ELSE 'Stable'
    END                                             AS trend,
    CASE
        WHEN COALESCE(a4.avg_hours_4w, 0) = 0             THEN 'New'
        WHEN wh.total_hours > a4.avg_hours_4w * 1.10      THEN 'Above Average'
        WHEN wh.total_hours < a4.avg_hours_4w * 0.90      THEN 'Below Average'
        ELSE 'Average'
    END                                             AS performance_band,
    COALESCE(ps.jira_status, 'No Jira Project')     AS jira_status,
    ps.current_health,
    ps.health_overall,
    ps.health_budget,
    ps.health_scope,
    ps.health_schedule,
    ps.budget_hours,
    ps.project_manager,
    ps.solution_architect,
    ps.planned_start,
    ps.planned_end,
    ps.actual_kickoff,
    ps.actual_completion,
    CASE WHEN ec.customer_name_lower IS NOT NULL THEN 'Yes'
         ELSE 'No'
    END                                             AS escalation
FROM weekly_hours wh
LEFT JOIN avg_4w  a4  ON wh.client_name = a4.client_name
                      AND wh.project_name = a4.project_name
LEFT JOIN avg_12w a12 ON wh.client_name = a12.client_name
                      AND wh.project_name = a12.project_name
LEFT JOIN prior_week pw ON wh.client_name = pw.client_name
                        AND wh.project_name = pw.project_name
-- Join via mapping first, fall back to direct name match
LEFT JOIN ps_via_mapping ps
       ON LOWER(wh.clockify_client_name) = LOWER(ps.cw_client)
      AND (ps.cw_project IS NULL
           OR LOWER(wh.project_name) = LOWER(ps.cw_project))
-- Only use direct match when no mapping match found
LEFT JOIN ps_direct psd
       ON ps.cw_client IS NULL
      AND LOWER(wh.client_name) = LOWER(psd.cw_client)
      AND LOWER(wh.project_name) = LOWER(psd.cw_project)
LEFT JOIN escalated_clients ec
       ON LOWER(wh.client_name) = ec.customer_name_lower
ORDER BY wh.week_start_date DESC, wh.client_name, wh.project_name;


-- ============================================================
-- vw_project_hours_current_week
-- Subset of vw_project_hours_summary for the most recent
-- complete week only.  Faster SPICE import for KPI cards.
-- ============================================================
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


-- ============================================================
-- vw_category_hours_summary
-- Weekly hours rolled up to (category, practice_alignment).
-- Includes 4w/12w averages at the category level.
-- Powers the PS-vs-MC practice-level charts.
-- ============================================================
DROP VIEW IF EXISTS vw_category_hours_summary;
CREATE VIEW vw_category_hours_summary AS
WITH

weekly_category AS (
    SELECT
        week_start_date,
        category,
        practice_alignment,
        SUM(total_hours)    AS total_hours,
        SUM(billable_hours) AS billable_hours,
        -- approximate: sum of per-project counts may double-count users
        SUM(resource_count) AS resource_count,
        COUNT(DISTINCT project_name) AS project_count,
        COUNT(DISTINCT client_name)  AS client_count
    FROM vw_project_hours_summary
    GROUP BY week_start_date, category, practice_alignment
),

cat_avg_4w AS (
    SELECT
        category,
        practice_alignment,
        AVG(total_hours) AS avg_hours_4w
    FROM weekly_category
    WHERE week_start_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '5 weeks'
      AND week_start_date <  DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '1 week'
    GROUP BY category, practice_alignment
),

cat_avg_12w AS (
    SELECT
        category,
        practice_alignment,
        AVG(total_hours) AS avg_hours_12w
    FROM weekly_category
    WHERE week_start_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '13 weeks'
      AND week_start_date <  DATE_TRUNC('week', CURRENT_DATE)::DATE - INTERVAL '1 week'
    GROUP BY category, practice_alignment
)

SELECT
    wc.week_start_date,
    wc.category,
    wc.practice_alignment,
    wc.project_count,
    wc.client_count,
    ROUND(wc.total_hours::NUMERIC,    2)  AS total_hours,
    ROUND(wc.billable_hours::NUMERIC, 2)  AS billable_hours,
    CASE WHEN wc.total_hours > 0
         THEN ROUND((wc.billable_hours / wc.total_hours * 100)::NUMERIC, 1)
         ELSE 0::NUMERIC
    END                                   AS billable_pct,
    wc.resource_count,
    ROUND(COALESCE(a4.avg_hours_4w,   0)::NUMERIC, 2) AS avg_hours_4w,
    ROUND(COALESCE(a12.avg_hours_12w, 0)::NUMERIC, 2) AS avg_hours_12w
FROM weekly_category wc
LEFT JOIN cat_avg_4w  a4  ON wc.category = a4.category
                          AND wc.practice_alignment = a4.practice_alignment
LEFT JOIN cat_avg_12w a12 ON wc.category = a12.category
                          AND wc.practice_alignment = a12.practice_alignment
ORDER BY wc.week_start_date DESC, wc.category;
