-- Migration 034: Add is_excluded flag to ps_project_status
--
-- Adds a manual exclusion flag so stale/artifact rows can be hidden from
-- the PS status view without being deleted. The Jira import upsert never
-- touches this column, so exclusions survive re-imports.
--
-- Also excludes the two Happy Numbers artifact rows that result from old
-- Jira summary mis-parsing:
--   project_name='Numbers'  (from summary "Happy Numbers" → pattern 4 split)
--   project_name='Assess'   (from summary "Happy Numbers-Migration Assess")
-- The canonical active row (project_name='Assessment', In Progress) is kept.

-- Step 1: add the column
ALTER TABLE ps_project_status
    ADD COLUMN IF NOT EXISTS is_excluded BOOLEAN DEFAULT FALSE;

-- Step 2: mark the two stale Happy Numbers artifact rows as excluded
UPDATE ps_project_status
SET    is_excluded = TRUE
WHERE  client_name = 'Happy Numbers'
  AND  project_name IN ('Numbers', 'Assess');

-- Step 3: recreate the view to pick up the new filter
-- (run create_views.sql separately, or the Lambda run_migration mode will
--  call it automatically after applying this migration)
