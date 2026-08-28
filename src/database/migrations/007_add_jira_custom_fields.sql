-- Migration 007: Add Jira custom fields for detailed project tracking
-- These fields come from Jira custom fields for project management

-- Add new columns to jira_issues table
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS project_type VARCHAR(100);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS project_manager VARCHAR(255);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS solution_architect VARCHAR(255);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS engineer VARCHAR(255);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS account_executive VARCHAR(255);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS csm VARCHAR(255);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS current_health VARCHAR(100);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS budget_hours DECIMAL(10,2);
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS planned_start DATE;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS planned_end DATE;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS sow_link TEXT;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS project_summary TEXT;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS what_we_did TEXT;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS what_we_will_do_next TEXT;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS impact TEXT;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS mitigation_plan TEXT;
ALTER TABLE jira_issues ADD COLUMN IF NOT EXISTS slippages TEXT;

-- Add indexes for commonly filtered fields
CREATE INDEX IF NOT EXISTS idx_jira_issues_project_type ON jira_issues(project_type);
CREATE INDEX IF NOT EXISTS idx_jira_issues_project_manager ON jira_issues(project_manager);
CREATE INDEX IF NOT EXISTS idx_jira_issues_current_health ON jira_issues(current_health);
