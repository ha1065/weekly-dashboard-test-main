-- Migration 035: Fix HappyNumbers MAP client_name back to canonical 'Happy Numbers'
--
-- The Jira import (run 2026-03-17) re-parsed summary "HappyNumbers MAP Assessment"
-- and reset client_name from 'Happy Numbers' (migration 033) back to 'HappyNumbers MAP'.
-- import_jira_data.py has been updated to no longer overwrite client_name/project_name
-- for existing records, so this fix will now be durable.

UPDATE ps_project_status
SET    client_name = 'Happy Numbers'
WHERE  client_name = 'HappyNumbers MAP'
  AND  project_name = 'Assessment';
