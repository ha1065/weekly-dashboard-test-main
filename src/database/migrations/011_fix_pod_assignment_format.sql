-- Migration: Fix pod_assignment format
-- Remove curly braces and quotes from pod_assignment field

-- Update pod_assignment to remove JSON formatting
UPDATE clockify_detailed_time_entries
SET pod_assignment = TRIM(BOTH '"' FROM TRIM(BOTH '{}' FROM pod_assignment))
WHERE pod_assignment IS NOT NULL
  AND (pod_assignment LIKE '{%}' OR pod_assignment LIKE '"%"');

-- Update specific malformed values
UPDATE clockify_detailed_time_entries
SET pod_assignment = 'No POD'
WHERE pod_assignment = '{"No POD"}' OR pod_assignment = '{No POD}' OR pod_assignment = '"No POD"';

UPDATE clockify_detailed_time_entries
SET pod_assignment = 'Free Agent'
WHERE pod_assignment = '{"Free Agent"}' OR pod_assignment = '{Free Agent}' OR pod_assignment = '"Free Agent"';

UPDATE clockify_detailed_time_entries
SET pod_assignment = 'Alpha'
WHERE pod_assignment = '{Alpha}' OR pod_assignment = '"Alpha"';

UPDATE clockify_detailed_time_entries
SET pod_assignment = 'Bravo'
WHERE pod_assignment = '{Bravo}' OR pod_assignment = '"Bravo"';

UPDATE clockify_detailed_time_entries
SET pod_assignment = 'SurePoint'
WHERE pod_assignment = '{SurePoint}' OR pod_assignment = '"SurePoint"';

UPDATE clockify_detailed_time_entries
SET pod_assignment = 'A2Z'
WHERE pod_assignment = '{A2Z}' OR pod_assignment = '"A2Z"';
