-- Migration 063: Change ps_project_status unique constraint from jira_issue_id alone
-- to (jira_issue_id, week_start) to support true weekly snapshots.
--
-- Before: one row per issue (overwritten on every import)
-- After:  one row per (issue, week) — re-running the same week upserts; new weeks insert

-- Drop the old single-column unique constraint
ALTER TABLE ps_project_status DROP CONSTRAINT IF EXISTS ps_project_status_jira_issue_id_key;

-- Add composite unique constraint for weekly snapshot history
ALTER TABLE ps_project_status ADD CONSTRAINT ps_project_status_issue_week_key
    UNIQUE (jira_issue_id, week_start);
