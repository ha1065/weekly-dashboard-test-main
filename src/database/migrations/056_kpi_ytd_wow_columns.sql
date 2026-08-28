-- Migration 056: Add additional WoW delta columns to vw_kpi_ytd
-- Adds week-over-week deltas for productive_util, headcount, escalations, presales

DROP VIEW IF EXISTS vw_kpi_ytd;

CREATE VIEW vw_kpi_ytd AS
WITH ordered AS (
    SELECT *
    FROM kpi_weekly_snapshots
    WHERE week_start_date >= '2026-01-01'
    ORDER BY week_start_date
)
SELECT
    week_start_date,
    week_num,
    snapshot_taken_at,

    -- Raw KPIs
    billable_util_pct,
    productive_util_pct,
    time_compliance_pct,
    presales_hours,
    productive_nb_hours,
    total_available_hours,
    total_billable_hours,

    -- Targets (pass-through)
    target_billable_util_pct,
    target_productive_util_pct,
    target_time_compliance_pct,

    -- vs-target gaps
    ROUND((billable_util_pct   - target_billable_util_pct)::NUMERIC,   2) AS billable_util_vs_target,
    ROUND((productive_util_pct - target_productive_util_pct)::NUMERIC, 2) AS productive_util_vs_target,
    ROUND((time_compliance_pct - target_time_compliance_pct)::NUMERIC, 2) AS compliance_vs_target,

    -- Week-over-week deltas
    ROUND((billable_util_pct    - LAG(billable_util_pct)    OVER (ORDER BY week_start_date))::NUMERIC, 2) AS billable_util_wow,
    ROUND((productive_util_pct  - LAG(productive_util_pct)  OVER (ORDER BY week_start_date))::NUMERIC, 2) AS productive_util_wow,
    ROUND((time_compliance_pct  - LAG(time_compliance_pct)  OVER (ORDER BY week_start_date))::NUMERIC, 2) AS compliance_wow,
    ROUND((presales_hours       - LAG(presales_hours)        OVER (ORDER BY week_start_date))::NUMERIC, 2) AS presales_wow,
    (active_resource_count      - LAG(active_resource_count) OVER (ORDER BY week_start_date))             AS headcount_wow,
    (open_escalations           - LAG(open_escalations)      OVER (ORDER BY week_start_date))             AS escalations_wow,

    -- PS metrics
    ps_active_projects,
    ps_on_time_pct,
    ps_avg_duration_weeks,
    ps_projects_green,
    ps_projects_amber,
    ps_projects_red,
    ps_billable_hours,
    ps_budget_hours_total,
    ps_actual_hours_ytd,
    ROUND((ps_on_time_pct - target_ps_on_time_pct)::NUMERIC, 2)                                           AS ps_ontime_vs_target,
    ROUND((ps_billable_hours - LAG(ps_billable_hours) OVER (ORDER BY week_start_date))::NUMERIC, 2)       AS ps_billable_wow,
    target_ps_on_time_pct,
    target_ps_avg_duration_weeks,

    -- MC metrics
    mc_active_projects,
    mc_on_time_pct,
    mc_avg_duration_weeks,
    mc_projects_green,
    mc_projects_amber,
    mc_projects_red,
    mc_billable_hours,
    mc_budget_hours_total,
    mc_actual_hours_ytd,
    ROUND((mc_on_time_pct - target_mc_on_time_pct)::NUMERIC, 2)                                           AS mc_ontime_vs_target,
    ROUND((mc_billable_hours - LAG(mc_billable_hours) OVER (ORDER BY week_start_date))::NUMERIC, 2)       AS mc_billable_wow,
    target_mc_on_time_pct,

    -- Combined totals
    COALESCE(ps_projects_red,   0) + COALESCE(mc_projects_red,   0) AS total_projects_red,
    COALESCE(ps_projects_amber, 0) + COALESCE(mc_projects_amber, 0) AS total_projects_amber,
    COALESCE(ps_projects_green, 0) + COALESCE(mc_projects_green, 0) AS total_projects_green,
    COALESCE(ps_billable_hours, 0) + COALESCE(mc_billable_hours, 0) AS total_billable_hours_combined,

    -- Escalation metrics
    open_escalations,
    escalations_high_priority,
    escalations_med_priority,
    avg_escalation_days_open,
    escalations_resolved_ytd,

    -- Headcount
    active_resource_count

FROM ordered;
