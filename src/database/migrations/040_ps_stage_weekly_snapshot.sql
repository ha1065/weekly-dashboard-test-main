-- Migration 040: PS/MC stage weekly snapshot for week-over-week trend KPIs
CREATE TABLE IF NOT EXISTS ps_stage_weekly_snapshot (
    id             SERIAL PRIMARY KEY,
    week_start     DATE         NOT NULL,
    stage          VARCHAR(100) NOT NULL,
    category       VARCHAR(10)  NOT NULL,
    project_count  INTEGER      NOT NULL DEFAULT 0,
    captured_at    TIMESTAMP    DEFAULT NOW(),
    UNIQUE (week_start, stage, category)
);

CREATE INDEX IF NOT EXISTS idx_stage_snap_week ON ps_stage_weekly_snapshot(week_start);
CREATE INDEX IF NOT EXISTS idx_stage_snap_cat  ON ps_stage_weekly_snapshot(category);

-- Seed this week's snapshot from current ps_project_status state
INSERT INTO ps_stage_weekly_snapshot (week_start, stage, category, project_count)
SELECT
    DATE_TRUNC('week', CURRENT_DATE)::DATE AS week_start,
    p.status                               AS stage,
    p.category,
    COUNT(*)                               AS project_count
FROM ps_project_status p
WHERE p.status IS NOT NULL
  AND p.category IN ('PS', 'MC')
  AND (p.issue_type IS NULL OR p.issue_type NOT LIKE '%Managed Services%')
GROUP BY p.status, p.category
ON CONFLICT (week_start, stage, category) DO UPDATE
    SET project_count = EXCLUDED.project_count,
        captured_at   = NOW();
