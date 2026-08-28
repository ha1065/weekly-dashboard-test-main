-- Migration 071: Deduplicate ps_project_status and add UNIQUE constraint on jira_issue_id
-- HIGH RISK: dedup step must succeed before constraint is added.
-- Keeps the most recently synced row per jira_issue_id.

-- Step 1: Remove duplicates (keep highest id per jira_issue_id)
DELETE FROM ps_project_status
WHERE id NOT IN (
    SELECT MAX(id)
    FROM ps_project_status
    GROUP BY jira_issue_id
);

-- Step 2: Add unique constraint
ALTER TABLE ps_project_status
    ADD CONSTRAINT IF NOT EXISTS uq_ps_project_status_jira_issue_id
    UNIQUE (jira_issue_id);
