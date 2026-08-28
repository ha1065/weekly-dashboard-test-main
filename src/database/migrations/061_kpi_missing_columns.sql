-- Migration 061: Add missing columns to kpi_weekly_snapshots
-- nb_nonproductive_hours and missing_time_count were written by kpi_snapshot.py
-- and referenced by vw_kpi_ytd (migration 060) but never added to the table.
ALTER TABLE kpi_weekly_snapshots
    ADD COLUMN IF NOT EXISTS nb_nonproductive_hours NUMERIC(10,2),
    ADD COLUMN IF NOT EXISTS missing_time_count     INTEGER;
