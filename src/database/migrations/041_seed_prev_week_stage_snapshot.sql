-- Migration 041: Backfill previous week (2026-03-17) stage snapshot
-- Uses ps_project_status rows with week_start <= 2026-03-16 as the
-- best available approximation of last week's stage distribution.
INSERT INTO ps_stage_weekly_snapshot (week_start, stage, category, project_count)
SELECT
    '2026-03-17'::date      AS week_start,
    p.status                AS stage,
    p.category,
    COUNT(*)                AS project_count
FROM ps_project_status p
WHERE p.status IS NOT NULL
  AND p.category IN ('PS', 'MC')
  AND (p.issue_type IS NULL OR p.issue_type NOT LIKE '%Managed Services%')
  AND p.week_start <= '2026-03-16'
GROUP BY p.status, p.category
ON CONFLICT (week_start, stage, category) DO UPDATE
    SET project_count = EXCLUDED.project_count,
        captured_at   = NOW();
