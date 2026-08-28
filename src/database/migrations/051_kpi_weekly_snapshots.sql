-- Migration 051: KPI Weekly Snapshots Table + vw_kpi_ytd View
-- Creates the kpi_weekly_snapshots table (one row per week, populated by
-- kpi_snapshot.py Lambda integration) and the vw_kpi_ytd view that
-- derives vs-target and week-over-week delta columns.
-- Seeds NULL placeholder rows for every week from 2026-01-05 to today.

-- ============================================================
-- kpi_weekly_snapshots table
-- One row per Monday week_start_date.
-- Targets are stored per-row so they can be adjusted over time.
-- ============================================================
CREATE TABLE IF NOT EXISTS kpi_weekly_snapshots (

    -- Identity
    week_start_date              DATE        PRIMARY KEY,
    week_num                     INTEGER,          -- ISO week number
    snapshot_taken_at            TIMESTAMPTZ,      -- when kpi_snapshot.py ran

    -- --------------------------------------------------------
    -- Utilization KPIs  (computed from clockify time entries)
    -- --------------------------------------------------------
    billable_util_pct            NUMERIC(6,2),
    productive_util_pct          NUMERIC(6,2),
    time_compliance_pct          NUMERIC(6,2),
    presales_hours               NUMERIC(10,2),
    productive_nb_hours          NUMERIC(10,2),    -- non-bill productive
    total_available_hours        NUMERIC(10,2),    -- capacity hours for week
    total_billable_hours         NUMERIC(10,2),

    -- --------------------------------------------------------
    -- Targets  (defaulted; override per-row when targets change)
    -- --------------------------------------------------------
    target_billable_util_pct     NUMERIC(6,2)  DEFAULT 75.0,
    target_productive_util_pct   NUMERIC(6,2)  DEFAULT 80.0,
    target_time_compliance_pct   NUMERIC(6,2)  DEFAULT 95.0,

    -- --------------------------------------------------------
    -- PS metrics  (Professional Services)
    -- --------------------------------------------------------
    ps_active_projects           INTEGER,
    ps_on_time_pct               NUMERIC(6,2),
    ps_avg_duration_weeks        NUMERIC(6,2),
    ps_projects_green            INTEGER,
    ps_projects_amber            INTEGER,
    ps_projects_red              INTEGER,
    ps_billable_hours            NUMERIC(10,2),
    ps_budget_hours_total        NUMERIC(10,2),
    ps_actual_hours_ytd          NUMERIC(10,2),
    target_ps_on_time_pct        NUMERIC(6,2)  DEFAULT 90.0,
    target_ps_avg_duration_weeks NUMERIC(6,2)  DEFAULT 12.0,

    -- --------------------------------------------------------
    -- MC metrics  (Managed Cloud)
    -- --------------------------------------------------------
    mc_active_projects           INTEGER,
    mc_on_time_pct               NUMERIC(6,2),
    mc_avg_duration_weeks        NUMERIC(6,2),
    mc_projects_green            INTEGER,
    mc_projects_amber            INTEGER,
    mc_projects_red              INTEGER,
    mc_billable_hours            NUMERIC(10,2),
    mc_budget_hours_total        NUMERIC(10,2),
    mc_actual_hours_ytd          NUMERIC(10,2),
    target_mc_on_time_pct        NUMERIC(6,2)  DEFAULT 90.0,

    -- --------------------------------------------------------
    -- Escalation metrics
    -- --------------------------------------------------------
    open_escalations             INTEGER,
    escalations_high_priority    INTEGER,
    escalations_med_priority     INTEGER,
    avg_escalation_days_open     NUMERIC(6,2),
    escalations_resolved_ytd     INTEGER,

    -- --------------------------------------------------------
    -- Resource headcount
    -- --------------------------------------------------------
    active_resource_count        INTEGER,

    created_at                   TIMESTAMPTZ DEFAULT NOW(),
    updated_at                   TIMESTAMPTZ DEFAULT NOW()
);

-- Index for time-range queries
CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_week
    ON kpi_weekly_snapshots (week_start_date);


-- ============================================================
-- vw_kpi_ytd
-- Thin view over kpi_weekly_snapshots that adds:
--   * vs-target gap columns
--   * week-over-week delta columns (using LAG)
-- ============================================================
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
    ROUND((billable_util_pct  - target_billable_util_pct)::NUMERIC,  2) AS billable_util_vs_target,
    ROUND((productive_util_pct - target_productive_util_pct)::NUMERIC, 2) AS productive_util_vs_target,
    ROUND((time_compliance_pct - target_time_compliance_pct)::NUMERIC, 2) AS compliance_vs_target,

    -- Week-over-week deltas (LAG over ordered weeks)
    ROUND((billable_util_pct   - LAG(billable_util_pct)   OVER (ORDER BY week_start_date))::NUMERIC, 2) AS billable_util_wow,
    ROUND((time_compliance_pct - LAG(time_compliance_pct) OVER (ORDER BY week_start_date))::NUMERIC, 2) AS compliance_wow,

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
    ROUND((ps_on_time_pct - target_ps_on_time_pct)::NUMERIC, 2) AS ps_ontime_vs_target,
    ROUND((ps_billable_hours - LAG(ps_billable_hours) OVER (ORDER BY week_start_date))::NUMERIC, 2) AS ps_billable_wow,
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
    ROUND((mc_on_time_pct - target_mc_on_time_pct)::NUMERIC, 2) AS mc_ontime_vs_target,
    ROUND((mc_billable_hours - LAG(mc_billable_hours) OVER (ORDER BY week_start_date))::NUMERIC, 2) AS mc_billable_wow,
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


-- ============================================================
-- Seed NULL placeholder rows for every week Mon 2026-01-05
-- through the current week.  kpi_snapshot.py will backfill
-- the actual values.
-- ============================================================
INSERT INTO kpi_weekly_snapshots (week_start_date, week_num)
SELECT
    d::DATE                                AS week_start_date,
    EXTRACT(WEEK FROM d::DATE)::INTEGER    AS week_num
FROM generate_series(
    '2026-01-05'::DATE,
    CURRENT_DATE,
    '7 days'::INTERVAL
) AS d
ON CONFLICT (week_start_date) DO NOTHING;
