-- Migration 065: Rebuild vw_kpi_ytd with all *_prev LAG columns
-- Ensures the view is current in production with every _prev column
-- referenced by the COO dashboard KPI tiles (from coo-dashboards.yaml):
--   billable_util_prev, productive_util_prev, compliance_prev,
--   presales_prev, productive_nb_prev, nb_nonproductive_prev,
--   missing_time_prev, headcount_prev, escalations_prev,
--   ps_active_prev, ps_green_prev, ps_red_prev, ps_billable_prev,
--   mc_active_prev, mc_green_prev, mc_red_prev, mc_billable_prev

DROP VIEW IF EXISTS vw_kpi_ytd;

CREATE VIEW vw_kpi_ytd AS
WITH ordered AS (
    SELECT *
    FROM kpi_weekly_snapshots
    WHERE week_start_date >= '2026-01-01'
      AND week_start_date < DATE_TRUNC('week', CURRENT_DATE)::DATE
    ORDER BY week_start_date
)
SELECT
    week_start_date,
    week_num,
    snapshot_taken_at,
    -- Current week values
    billable_util_pct,
    productive_util_pct,
    time_compliance_pct,
    presales_hours,
    productive_nb_hours,
    nb_nonproductive_hours,
    total_available_hours,
    total_billable_hours,
    missing_time_count,
    target_billable_util_pct,
    target_productive_util_pct,
    target_time_compliance_pct,
    -- vs target
    ROUND((billable_util_pct   - target_billable_util_pct)::NUMERIC,   2) AS billable_util_vs_target,
    ROUND((productive_util_pct - target_productive_util_pct)::NUMERIC, 2) AS productive_util_vs_target,
    ROUND((time_compliance_pct - target_time_compliance_pct)::NUMERIC, 2) AS compliance_vs_target,
    -- WoW deltas
    ROUND((billable_util_pct   - LAG(billable_util_pct)   OVER (ORDER BY week_start_date))::NUMERIC, 2) AS billable_util_wow,
    ROUND((productive_util_pct - LAG(productive_util_pct) OVER (ORDER BY week_start_date))::NUMERIC, 2) AS productive_util_wow,
    ROUND((time_compliance_pct - LAG(time_compliance_pct) OVER (ORDER BY week_start_date))::NUMERIC, 2) AS compliance_wow,
    ROUND((presales_hours      - LAG(presales_hours)       OVER (ORDER BY week_start_date))::NUMERIC, 2) AS presales_wow,
    (active_resource_count     - LAG(active_resource_count) OVER (ORDER BY week_start_date))             AS headcount_wow,
    (open_escalations          - LAG(open_escalations)      OVER (ORDER BY week_start_date))             AS escalations_wow,
    ROUND((productive_nb_hours    - LAG(productive_nb_hours)    OVER (ORDER BY week_start_date))::NUMERIC, 2) AS productive_nb_wow,
    ROUND((nb_nonproductive_hours - LAG(nb_nonproductive_hours) OVER (ORDER BY week_start_date))::NUMERIC, 2) AS nb_nonproductive_wow,
    -- Prior week values (_prev) for KPI tile TargetValues
    LAG(billable_util_pct)      OVER (ORDER BY week_start_date) AS billable_util_prev,
    LAG(productive_util_pct)    OVER (ORDER BY week_start_date) AS productive_util_prev,
    LAG(time_compliance_pct)    OVER (ORDER BY week_start_date) AS compliance_prev,
    LAG(presales_hours)         OVER (ORDER BY week_start_date) AS presales_prev,
    LAG(productive_nb_hours)    OVER (ORDER BY week_start_date) AS productive_nb_prev,
    LAG(nb_nonproductive_hours) OVER (ORDER BY week_start_date) AS nb_nonproductive_prev,
    LAG(missing_time_count)     OVER (ORDER BY week_start_date) AS missing_time_prev,
    LAG(active_resource_count)  OVER (ORDER BY week_start_date) AS headcount_prev,
    LAG(open_escalations)       OVER (ORDER BY week_start_date) AS escalations_prev,
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
    LAG(ps_active_projects)  OVER (ORDER BY week_start_date) AS ps_active_prev,
    LAG(ps_projects_green)   OVER (ORDER BY week_start_date) AS ps_green_prev,
    LAG(ps_projects_red)     OVER (ORDER BY week_start_date) AS ps_red_prev,
    LAG(ps_billable_hours)   OVER (ORDER BY week_start_date) AS ps_billable_prev,
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
    LAG(mc_active_projects)  OVER (ORDER BY week_start_date) AS mc_active_prev,
    LAG(mc_projects_green)   OVER (ORDER BY week_start_date) AS mc_green_prev,
    LAG(mc_projects_red)     OVER (ORDER BY week_start_date) AS mc_red_prev,
    LAG(mc_billable_hours)   OVER (ORDER BY week_start_date) AS mc_billable_prev,
    -- Totals
    COALESCE(ps_projects_red,   0) + COALESCE(mc_projects_red,   0) AS total_projects_red,
    COALESCE(ps_projects_amber, 0) + COALESCE(mc_projects_amber, 0) AS total_projects_amber,
    COALESCE(ps_projects_green, 0) + COALESCE(mc_projects_green, 0) AS total_projects_green,
    COALESCE(ps_billable_hours, 0) + COALESCE(mc_billable_hours, 0) AS total_billable_hours_combined,
    -- Escalations
    open_escalations,
    escalations_high_priority,
    escalations_med_priority,
    avg_escalation_days_open,
    escalations_resolved_ytd,
    active_resource_count
FROM ordered;
