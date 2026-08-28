-- Migration 036: Correct Happy Numbers row exclusions
--
-- Migration 034 excluded the wrong rows. The actual active project is
-- "Happy Numbers-Migration Assess" (project_name='Assess'), not "Assessment".
-- The "Assessment" row (from "HappyNumbers MAP Assessment") is stale.
--
-- Corrections:
--   1. Un-exclude 'Assess' row  (real project — should show)
--   2. Exclude 'Assessment' row (stale/old — should not show)
--   3. Normalize client_name for 'Assess' row to canonical 'Happy Numbers'

-- Step 1: un-exclude the real active project
UPDATE ps_project_status
SET    is_excluded = FALSE,
       client_name = 'Happy Numbers'
WHERE  LOWER(client_name) IN ('happy numbers-migration', 'happy numbers')
  AND  project_name = 'Assess';

-- Step 2: exclude the stale HappyNumbers MAP Assessment row
UPDATE ps_project_status
SET    is_excluded = TRUE
WHERE  project_name = 'Assessment'
  AND  LOWER(client_name) IN ('happy numbers', 'happynumbers map');
