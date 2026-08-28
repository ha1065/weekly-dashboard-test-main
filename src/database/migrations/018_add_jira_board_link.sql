-- Migration 018: Add jira_board_link column to ps_project_status
ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS jira_board_link TEXT;
