-- Migration 039: Remove ps_project_status rows for Jira issues that no longer exist
-- CST-631 ("HappyNumbers MAP Assessment") and CST-632 ("Happy Numbers") were deleted
-- from Jira but remained as stale rows, causing Happy Numbers to appear 3x in the
-- Project Mapping tab. CST-633 ("Happy Numbers-Migration Assess") is the valid issue.

DELETE FROM ps_project_status WHERE issue_key IN ('CST-631', 'CST-632');

-- Clean up any orphaned mappings pointing only to these stale client/project combos
-- (only removes if no other active ps_project_status row exists for that client/project)
DELETE FROM ps_project_mapping
WHERE ps_client_name = 'Happy Numbers'
  AND ps_project_name IN ('Assessment', 'Numbers')
  AND NOT EXISTS (
      SELECT 1 FROM ps_project_status s
      WHERE LOWER(s.client_name) = LOWER(ps_project_mapping.ps_client_name)
        AND LOWER(COALESCE(s.project_name,'')) = LOWER(COALESCE(ps_project_mapping.ps_project_name,''))
  );
