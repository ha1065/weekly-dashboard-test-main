-- Migration 069: vw_utilization_history
-- Wraps vw_productive_utilization, adds month/quarter labels.
-- Powers Tab 13 (Productive Utilization) historical trend.
-- Depends on: vw_productive_utilization (existing)

DROP VIEW IF EXISTS vw_utilization_history;
CREATE VIEW vw_utilization_history AS
SELECT
    pu.*,
    TO_CHAR(pu.week_start, 'Mon YYYY')                          AS month_label,
    EXTRACT(YEAR FROM pu.week_start)::INTEGER                   AS year_num,
    EXTRACT(MONTH FROM pu.week_start)::INTEGER                  AS month_num,
    EXTRACT(QUARTER FROM pu.week_start)::INTEGER                AS quarter_num,
    CONCAT('Q', EXTRACT(QUARTER FROM pu.week_start)::INTEGER,
           ' ', EXTRACT(YEAR FROM pu.week_start)::INTEGER)      AS quarter_label
FROM vw_productive_utilization pu;
