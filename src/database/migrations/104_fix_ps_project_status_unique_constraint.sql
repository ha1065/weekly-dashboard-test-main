-- Migration 104: Restore single-column UNIQUE constraint on ps_project_status.jira_issue_id
--
-- PROBLEM:
--   The Jira import uses ON CONFLICT (jira_issue_id) for upsert, which requires a
--   single-column UNIQUE constraint. Migration 063 replaced UNIQUE(jira_issue_id) with
--   UNIQUE(jira_issue_id, week_start) for weekly snapshots, and migration 071 was
--   supposed to restore it — but in some environments the composite constraint blocks
--   adding the single-column one (duplicate rows for the same jira_issue_id with
--   different week_start values).
--
-- FIX:
--   1. Drop the composite constraint (jira_issue_id, week_start)
--   2. Deduplicate: keep only the most recently synced row per jira_issue_id
--   3. Add the single-column UNIQUE constraint that the importer needs
--
-- DESIGN DECISION:
--   The import code sets week_start to current_monday - 1 week on every run and uses
--   ON CONFLICT (jira_issue_id) DO UPDATE — meaning it overwrites the same row each
--   time. Weekly snapshot history is captured separately by _capture_stage_snapshot()
--   into ps_stage_weekly_snapshot. Therefore ps_project_status should have ONE row per
--   issue (latest state), not one row per (issue, week).

-- Step 1: Drop the composite constraint (may not exist in all environments)
ALTER TABLE ps_project_status DROP CONSTRAINT IF EXISTS ps_project_status_issue_week_key;

-- Step 2: Drop the old single-column constraint name variants (idempotent)
ALTER TABLE ps_project_status DROP CONSTRAINT IF EXISTS ps_project_status_jira_issue_id_key;
ALTER TABLE ps_project_status DROP CONSTRAINT IF EXISTS uq_ps_project_status_jira_issue_id;

-- Step 3: Deduplicate — keep only the row with the highest id per jira_issue_id
DELETE FROM ps_project_status
WHERE id NOT IN (
    SELECT MAX(id)
    FROM ps_project_status
    GROUP BY jira_issue_id
);

-- Step 4: Add the single-column UNIQUE constraint
ALTER TABLE ps_project_status
    ADD CONSTRAINT uq_ps_project_status_jira_issue_id
    UNIQUE (jira_issue_id);
