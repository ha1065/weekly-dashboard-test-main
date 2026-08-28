-- Migration 042: Re-seed stage snapshots with corrected Done filter.
-- Excludes Done projects that have no completion date in the current calendar year
-- (i.e. stale historical projects with status=Done but no 2026 dates).
-- Only Done projects where COALESCE(actual_completion, revised_completion, expected_completion)
-- falls in the current year are counted.

-- Re-seed current week (2026-03-23)
DELETE FROM ps_stage_weekly_snapshot WHERE week_start = '2026-03-23';

INSERT INTO ps_stage_weekly_snapshot (week_start, stage, category, project_count)
SELECT
    '2026-03-23'::date  AS week_start,
    p.status            AS stage,
    p.category,
    COUNT(*)            AS project_count
FROM ps_project_status p
WHERE p.status IS NOT NULL
  AND p.category IN ('PS', 'MC')
  AND (p.issue_type IS NULL OR p.issue_type NOT LIKE '%Managed Services%')
  AND (
    p.status != 'Done'
    OR EXTRACT(YEAR FROM COALESCE(p.actual_completion, p.revised_completion, p.expected_completion))
       = EXTRACT(YEAR FROM CURRENT_DATE)
  )
GROUP BY p.status, p.category
ON CONFLICT (week_start, stage, category) DO UPDATE
    SET project_count = EXCLUDED.project_count,
        captured_at   = NOW();

-- Re-seed previous week (2026-03-17) using projects with week_start <= 2026-03-16
DELETE FROM ps_stage_weekly_snapshot WHERE week_start = '2026-03-17';

INSERT INTO ps_stage_weekly_snapshot (week_start, stage, category, project_count)
SELECT
    '2026-03-17'::date  AS week_start,
    p.status            AS stage,
    p.category,
    COUNT(*)            AS project_count
FROM ps_project_status p
WHERE p.status IS NOT NULL
  AND p.category IN ('PS', 'MC')
  AND (p.issue_type IS NULL OR p.issue_type NOT LIKE '%Managed Services%')
  AND p.week_start <= '2026-03-16'
  AND (
    p.status != 'Done'
    OR EXTRACT(YEAR FROM COALESCE(p.actual_completion, p.revised_completion, p.expected_completion))
       = EXTRACT(YEAR FROM CURRENT_DATE)
  )
GROUP BY p.status, p.category
ON CONFLICT (week_start, stage, category) DO UPDATE
    SET project_count = EXCLUDED.project_count,
        captured_at   = NOW();
